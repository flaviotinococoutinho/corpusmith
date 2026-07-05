// Inbox de ingestão (v0.11): dropzone + nota rápida + tabela densa com
// stepper de pipeline ao vivo (page.stage via SSE) e destino compilado.
import { useCallback, useEffect, useRef, useState } from "react";
import { client } from "../lib/client";
import { live } from "../lib/live";

const STAGES = ["produce", "normalize", "reconcile", "write", "done"] as const;
const STAGE_ICON: Record<string, string> = {
  produce: "📥", normalize: "🧹", reconcile: "🔀", write: "✍️", done: "✅",
};

function Stepper({ stage }: { stage: string }) {
  const at = STAGES.indexOf(stage as any);
  return (
    <span className="font-mono text-xs" title={stage}>
      {STAGES.map((s, i) => (
        <span key={s} className={i <= at ? "" : "opacity-25"}>
          {STAGE_ICON[s]}</span>))}
    </span>
  );
}

export function InboxPanel() {
  const [items, setItems] = useState<any[]>([]);
  const [note, setNote] = useState("");
  const [noteTitle, setNoteTitle] = useState("");
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  // job em andamento: jobId → {source, stage}
  const [running, setRunning] = useState<Record<string, any>>({});
  const fileInput = useRef<HTMLInputElement>(null);

  const load = () => client.inbox().then(r => setItems(r.items));
  useEffect(() => {
    load();
    live.start();
    return live.onEvent(e => {
      const d = e.data ?? {};
      if (e.type === "compile.extracting" && d.id) {
        setRunning(r => ({ ...r, [d.id]: { source: d.source, stage: "produce" } }));
      } else if (e.type === "page.stage" && d.id) {
        setRunning(r => r[d.id]
          ? { ...r, [d.id]: { ...r[d.id], stage: d.stage } } : r);
        if (d.stage === "done") setTimeout(load, 400);
      } else if (["compile.done", "consolidate.done", "job.failed",
                  "source.ingested"].includes(e.type)) {
        if (e.type === "job.failed" && d.id)
          setRunning(r => { const { [d.id]: _, ...rest } = r; return rest; });
        setTimeout(load, 400);
      }
    });
  }, []);

  const ingestText = async (filename: string, content: string,
                            compile = true) => {
    setBusy(true);
    try { await client.ingest({ filename, content, compile }); }
    finally { setBusy(false); load(); }
  };

  const ingestFiles = useCallback(async (files: FileList | File[]) => {
    setBusy(true);
    try {
      for (const f of Array.from(files)) {
        const isText = /\.(md|txt)$/i.test(f.name);
        if (isText) {
          await client.ingest({ filename: f.name, content: await f.text(),
                                compile: true });
        } else {
          const buf = new Uint8Array(await f.arrayBuffer());
          let bin = "";
          buf.forEach(b => { bin += String.fromCharCode(b); });
          await client.ingest({ filename: f.name,
                                content_base64: btoa(bin), compile: true });
        }
      }
    } finally { setBusy(false); load(); }
  }, []);

  const stageBySource: Record<string, string> = {};
  for (const r of Object.values(running))
    if (r.source) stageBySource[r.source] = r.stage;

  const compile = (path: string) =>
    client.enqueue("compile_source", { path }).then(load);

  const pending = items.filter(i => i.status !== "compilado").length;

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-start gap-4">
        {/* dropzone */}
        <div
          className={`flex-1 border-2 border-dashed rounded p-6 text-center
            text-sm cursor-pointer transition-colors ${
            dragging ? "border-blue-400 bg-blue-50" : "border-neutral-300"}`}
          onClick={() => fileInput.current?.click()}
          onDragOver={e => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={e => { e.preventDefault(); setDragging(false);
                         ingestFiles(e.dataTransfer.files); }}>
          📥 Arraste .md/.txt/.pdf/.epub aqui — ou clique para escolher.
          <div className="text-xs text-neutral-400 mt-1">
            Ingestão grava em raw/ e já enfileira a compilação.</div>
          <input ref={fileInput} type="file" multiple hidden
                 accept=".md,.txt,.pdf,.epub"
                 onChange={e => e.target.files && ingestFiles(e.target.files)} />
        </div>
        {/* nota rápida */}
        <div className="w-80 border rounded p-3 space-y-2">
          <div className="text-sm font-medium">📝 Nota rápida</div>
          <input className="border rounded w-full p-1 text-sm"
                 placeholder="Título" value={noteTitle}
                 onChange={e => setNoteTitle(e.target.value)} />
          <textarea className="border rounded w-full p-2 text-xs h-20"
                    placeholder="Captura barata: vai para o inbox e entra na consolidação por recorrência."
                    value={note} onChange={e => setNote(e.target.value)} />
          <button className="border rounded px-2 py-1 text-xs"
                  disabled={busy || !note || !noteTitle}
                  onClick={() => {
                    ingestText(`${noteTitle}.md`,
                               `# ${noteTitle}\n\n${note}\n`, false);
                    setNote(""); setNoteTitle("");
                  }}>Capturar (sem compilar)</button>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <h2 className="font-semibold">
          Inbox (raw/) · {pending} pendente(s)</h2>
        <span className="space-x-2">
          <button className="border rounded px-2 py-1 text-xs"
                  onClick={() => client.enqueue("consolidate_inbox", {})
                    .then(() => setTimeout(load, 800))}>
            🧩 Consolidar recorrentes</button>
          <button className="border rounded px-2 py-1 text-xs"
                  onClick={load}>atualizar</button>
        </span>
      </div>
      <table className="w-full text-sm">
        <thead><tr className="text-left text-neutral-500">
          <th>Fonte</th><th>Priv.</th><th>Tam.</th><th>Modificado</th>
          <th>Status / pipeline</th><th>→ Página</th><th /></tr></thead>
        <tbody>{items.map(i => (
          <tr key={i.path} className="border-t align-top">
            <td className="font-mono text-xs py-1">{i.path}</td>
            <td>{i.privacy === "local_only" ? "🔒" : "🌐"}</td>
            <td className="text-xs text-neutral-500">
              {(i.bytes / 1024).toFixed(1)} kB</td>
            <td className="text-xs text-neutral-500">{i.modified}</td>
            <td>
              {stageBySource[i.path]
                ? <Stepper stage={stageBySource[i.path]} />
                : <>{{ novo: "🆕", stale: "🟡",
                       compilado: "✅" }[i.status as string]} {i.status}</>}
            </td>
            <td className="font-mono text-xs text-neutral-500">
              {i.page ?? "—"}</td>
            <td>{i.status !== "compilado" && !stageBySource[i.path] &&
              <button className="border rounded px-2 py-1 text-xs"
                      onClick={() => compile(i.path)}>
                {i.status === "stale" ? "Recompilar" : "Compilar"}</button>}</td>
          </tr>))}</tbody>
      </table>
      {!items.length && <p className="text-neutral-400 text-sm">
        Inbox vazio — arraste um arquivo ou capture uma nota.</p>}
    </div>
  );
}

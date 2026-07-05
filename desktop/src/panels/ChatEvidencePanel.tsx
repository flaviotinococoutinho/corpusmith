import { useState } from "react";
import { client } from "../lib/client";
import { PromoteDialog } from "./PromoteDialog";

export function ChatEvidencePanel() {
  const [q, setQ] = useState("");
  const [deep, setDeep] = useState(false);
  const [local, setLocal] = useState(false);
  const [r, setR] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [promote, setPromote] = useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    try { setR(await client.ask(q, deep, local)); } finally { setBusy(false); }
  };

  return (
    <div className="flex h-full">
      <div className="flex-1 p-4 space-y-3 overflow-auto">
        <div className="flex gap-2">
          <input className="flex-1 border rounded px-3 py-2" value={q}
                 placeholder="Pergunte à sua base…"
                 onChange={e => setQ(e.target.value)}
                 onKeyDown={e => e.key === "Enter" && run()} />
          <button className="border rounded px-3" disabled={busy || !q}
                  onClick={run}>{busy ? "…" : "Perguntar"}</button>
        </div>
        <label className="text-xs mr-4">
          <input type="checkbox" checked={deep}
                 onChange={e => setDeep(e.target.checked)} /> deep (reranker)
        </label>
        <label className="text-xs">
          <input type="checkbox" checked={local}
                 onChange={e => setLocal(e.target.checked)} /> somente local
        </label>
        {r && (
          <article className="prose prose-sm max-w-none">
            {r.blocked && <p className="text-red-600 text-xs">
              ⛔ bloqueada pelo Harness (citações)</p>}
            <p className="text-xs text-neutral-500">
              via {r.via}{r.blocked ? "" : " · citada"}</p>
            <pre className="whitespace-pre-wrap text-sm">{r.answer}</pre>
            {!r.blocked && (
              <button className="border rounded px-2 py-1 text-xs"
                      onClick={() => setPromote(r.answer)}>
                ⭐ Promover para memória</button>)}
            {r.gaps?.length > 0 && (
              <p className="text-xs">Lacunas: {r.gaps.join("; ")}</p>)}
          </article>)}
      </div>
      <aside className="w-80 border-l p-3 overflow-auto text-sm">
        <h3 className="font-medium mb-2">Evidências</h3>
        {r?.evidence?.map((e: any, i: number) => (
          <div key={i} className="mb-3 border rounded p-2">
            <div className="font-mono text-xs">
              [{i + 1}] {e.page}{e.stale && <span className="text-amber-600"> · STALE</span>}
            </div>
            <div className="text-xs text-neutral-500 truncate">← {e.resource}</div>
            <p className="text-xs line-clamp-4">{e.body}</p>
            <button className="text-xs underline"
                    onClick={() => setPromote(e.body)}>promover trecho</button>
          </div>))}
        {!r && <p className="text-neutral-400 text-xs">
          As páginas OKF e fontes usadas na resposta aparecem aqui, numeradas.</p>}
      </aside>
      {promote && <PromoteDialog content={promote} source={`chat:${new Date()
        .toISOString().slice(0, 10)}`} onClose={() => setPromote(null)} />}
    </div>
  );
}

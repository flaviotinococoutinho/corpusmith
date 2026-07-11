import { useState } from "react";
import { client } from "../lib/client";
import { PromoteDialog } from "./PromoteDialog";

export function ChatEvidencePanel() {
  const [q, setQ] = useState("");
  const [deep, setDeep] = useState(false);
  const [local, setLocal] = useState(false);
  const [r, setR] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [promote, setPromote] = useState<{ content: string; kind?: string } | null>(null);
  const [voted, setVoted] = useState(false);
  const [correcting, setCorrecting] = useState(false);
  const [note, setNote] = useState("");

  const run = async () => {
    setBusy(true);
    setVoted(false); setCorrecting(false); setNote("");
    try { setR(await client.ask(q, deep, local)); } finally { setBusy(false); }
  };

  // v0.8 §11.2: desfecho de consulta alimenta heat/overlay (reflect)
  const vote = async (verdict: string, n?: string) => {
    await client.outcome({
      ask_id: r?.ask_id, verdict, note: n,
      pages: (r?.evidence ?? []).map((e: any) => e.page),
    });
    setVoted(true); setCorrecting(false);
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
        {r?.abstained && (
          <div className="border border-amber-300 bg-amber-50 rounded p-3 text-sm">
            <p className="font-medium">🤷 Sem cobertura na base</p>
            <ul className="text-xs list-disc ml-5 my-1">
              {r.gaps?.map((g: string) => <li key={g}>{g}</li>)}
            </ul>
            {r.cold_matches?.length > 0 && (
              <div className="my-2 border-t pt-2">
                <p className="text-xs font-medium">❄️ Memória fria compatível
                  — recicle e pergunte de novo:</p>
                {r.cold_matches.map((m: any) => (
                  <div key={m.page} className="flex items-center gap-2 text-xs">
                    <span className="font-mono flex-1 truncate">{m.page}</span>
                    <button className="border rounded px-1"
                            onClick={() => client.recycle(m.page).then(run)}>
                      ♻️ reciclar</button>
                  </div>))}
              </div>)}
            <button className="border rounded px-2 py-1 text-xs"
                    onClick={() => setPromote({ content: q, kind: "question" })}>
              ➕ Capturar como pergunta aberta</button>
          </div>)}
        {r && !r.abstained && (
          <article className="prose prose-sm max-w-none">
            {r.blocked && <p className="text-red-600 text-xs">
              ⛔ bloqueada pelo Harness (citações)</p>}
            <p className="text-xs text-neutral-500">
              via {r.via}{r.blocked ? "" : " · citada"}
              {r.as_of && <span className="ml-2 border rounded px-1">
                📅 como em {r.as_of}</span>}
              {r.uncertainty > 0.85 && <span
                className="ml-2 border border-amber-400 rounded px-1 text-amber-600">
                ~ incerta ({Math.round(r.uncertainty * 100)}%)</span>}
              {r.strategy && <span className="ml-2 border rounded px-1"
                title={r.cognitive?.declared
                  ? `adaptada à carga declarada ${r.cognitive.load}/5`
                  : "estratégia escolhida pelo crédito Hedge"}>
                🧭 {r.strategy}</span>}</p>
            {r.trajectory?.length > 0 && (
              <p className="text-xs text-neutral-500 font-mono">
                {r.trajectory.map((t: any) =>
                  `${t.dir} → ${t.picked.map((p: string) =>
                    p.split("/").pop()).join(", ")}`).join(" · ")}</p>)}
            <pre className="whitespace-pre-wrap text-sm">{r.answer}</pre>
            {!r.blocked && (
              <button className="border rounded px-2 py-1 text-xs mr-2"
                      onClick={() => setPromote({ content: r.answer })}>
                ⭐ Promover para memória</button>)}
            {!voted ? (
              <span className="text-xs">
                <button className="border rounded px-2 py-1 mr-1"
                        onClick={() => vote("useful")}>✅ útil</button>
                <button className="border rounded px-2 py-1 mr-1"
                        onClick={() => vote("dead_end")}>🚫 beco</button>
                <button className="border rounded px-2 py-1"
                        onClick={() => setCorrecting(true)}>✏️ corrigi</button>
              </span>
            ) : <span className="text-xs text-neutral-500">desfecho registrado ✓</span>}
            {correcting && (
              <div className="mt-2">
                <textarea className="border rounded w-full p-2 text-xs h-20"
                          placeholder="O que estava errado? (vira memória no inbox)"
                          value={note} onChange={e => setNote(e.target.value)} />
                <button className="border rounded px-2 py-1 text-xs"
                        disabled={!note}
                        onClick={() => vote("corrected", note)}>enviar correção</button>
              </div>)}
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
                    onClick={() => setPromote({ content: e.body })}>promover trecho</button>
          </div>))}
        {!r && <p className="text-neutral-400 text-xs">
          As páginas OKF e fontes usadas na resposta aparecem aqui, numeradas.</p>}
      </aside>
      {promote && <PromoteDialog content={promote.content}
        initialKind={promote.kind}
        source={`chat:${new Date().toISOString().slice(0, 10)}`}
        onClose={() => setPromote(null)} />}
    </div>
  );
}

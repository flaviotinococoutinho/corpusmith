// ProcessesPanel (Parte V §9.2): fila de jobs + feed de eventos ao vivo.
import { useEffect, useRef, useState } from "react";
import { client } from "../lib/client";
import { DaemonUnavailable } from "./DaemonUnavailable";

// Os OITO estados da fila (runtime/queue.py:25-28). A tabela tinha quatro, e
// os quatro que faltavam são justamente os que o usuário precisa reconhecer
// para agir: `retry_scheduled` (vai voltar sozinho — esperar), `dead_lettered`
// (esgotou as tentativas — só reexecução manual), `cancelled` e
// `cancel_requested` (pedido feito, o worker honra no boundary).
const STATE_ICON: Record<string, string> = {
  queued: "⏳", leased: "▶️", done: "✅", failed: "❌",
  retry_scheduled: "🔁", dead_lettered: "⚰️",
  cancelled: "🚫", cancel_requested: "🛑",
};

// `cancel` aceita queued/retry_scheduled (vira `cancelled` na hora) e leased
// (vira `cancel_requested`, cooperativo). `retry_manual` aceita
// failed/dead_lettered/cancelled. Fora disso o backend responde 409 — a UI
// não oferece o botão para não prometer o que a fila recusa.
const CANCELAVEL = new Set(["queued", "retry_scheduled", "leased"]);
const REEXECUTAVEL = new Set(["failed", "dead_lettered", "cancelled"]);

const PIPELINE = ["produce", "normalize", "reconcile", "write", "done"];

const RUN_ICON: Record<string, string> = {
  running: "▶️", done: "✅", partial: "🟡", failed: "❌",
};

export function ProcessesPanel() {
  const [jobs, setJobs] = useState<any[]>([]);
  const [feed, setFeed] = useState<any[]>([]);
  // jobId → último estágio da pipeline (page.stage)
  const [stages, setStages] = useState<Record<string, string>>({});
  const [pipes, setPipes] = useState<any[]>([]);
  const [runs, setRuns] = useState<any[]>([]);
  const esRef = useRef<EventSource | null>(null);

  const load = () => {
    client.jobs().then(r => setJobs(r.jobs));
    client.pipelines().then(r => setPipes(r.pipelines)).catch(() => {});
    client.pipelineRuns().then(r => setRuns(r.runs)).catch(() => {});
  };

  const [erro, setErro] = useState<unknown>(null);
  const [acaoErro, setAcaoErro] = useState<string | null>(null);

  /** Cancelar/reexecutar erram com 409 quando a fila mudou de estado entre a
   *  renderização e o clique — e é o caso comum, não a borda: um job `leased`
   *  vira `done` sozinho. Mostrar o motivo e recarregar é a resposta honesta;
   *  engolir deixaria o botão parecendo inerte. */
  const agir = (p: Promise<unknown>) => {
    setAcaoErro(null);
    p.then(load).catch(e => { setAcaoErro(String(e)); load(); });
  };

  useEffect(() => {
    client.connect().then(() => {
      load();
      esRef.current = client.events(e => {
        setFeed(f => [e, ...f].slice(0, 40));
        const d = e.data ?? {};
        if (e.type === "page.stage" && d.id)
          setStages(s => ({ ...s, [d.id]: d.stage }));
        if (String(e.type).startsWith("job.") ||
            String(e.type).startsWith("pipeline.")) load();
      });
    }).catch(setErro);              // F0: falha do daemon vira estado visível
    return () => esRef.current?.close();
  }, []);

  if (erro) return <DaemonUnavailable error={erro} onRetry={load} />;
  return (
    <div className="flex h-full text-sm">
      <div className="flex-1 p-4 overflow-auto">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold">Processos</h2>
          <button className="border rounded px-2 py-1 text-xs" onClick={load}>
            atualizar</button>
        </div>

        <section className="border rounded p-3 mb-4">
          <h3 className="font-medium text-sm mb-2">🔗 Pipelines
            <span className="text-xs text-neutral-400 ml-2">
              orquestração como dado — estágios são jobs; erro por estágio
              decide parar ou seguir</span></h3>
          {pipes.map(p => (
            <div key={p.name} className="flex items-center gap-2 text-xs mb-1">
              <button className="border rounded px-2"
                      title={p.description}
                      onClick={() => client.runPipeline(p.name).then(load)}>
                ▶ {p.name}</button>
              <span className="font-mono text-neutral-500 flex-1 truncate">
                {p.stages.map((s: any) => s.job).join(" → ")}</span>
              {p.last_run && (
                <span title={p.last_run.trace_id}>
                  {RUN_ICON[p.last_run.state] ?? ""} {p.last_run.state}</span>)}
              {p.builtin && <span className="text-neutral-400">builtin</span>}
            </div>))}
          {!!runs.length && (
            <div className="mt-2 pt-2 border-t text-xs space-y-1
                            max-h-24 overflow-auto">
              {runs.slice(0, 6).map(r => (
                <div key={r.id} className="font-mono truncate"
                     title={r.stages.map((s: any) =>
                       `${s.job}:${s.state}${s.error ? ` (${s.error})` : ""}`)
                       .join(" · ")}>
                  {RUN_ICON[r.state]} {r.pipeline} #{r.id}{" "}
                  {r.stages.map((s: any) =>
                    s.state === "done" ? "●" : s.state === "failed"
                      ? "✕" : "○").join("")}{" "}
                  <span className="text-neutral-400">{r.trace_id}</span>
                </div>))}
            </div>)}
        </section>
        {acaoErro && (
          <p className="text-xs text-red-600 mb-1">{acaoErro}</p>)}
        <table className="w-full text-xs">
          <thead><tr className="text-left text-neutral-500">
            <th>Job</th><th>Tipo</th><th>Estado</th><th>Tent.</th><th>Erro</th>
            <th>Ações</th></tr></thead>
          <tbody>{jobs.map(j => (
            <tr key={j.id} className="border-t">
              <td className="font-mono">{j.id}</td>
              <td>{j.type}</td>
              <td>{STATE_ICON[j.state] ?? ""} {j.state}
                {j.state === "leased" && stages[j.id] && (
                  <span className="ml-1 font-mono text-neutral-500"
                        title={stages[j.id]}>
                    {PIPELINE.map(s => PIPELINE.indexOf(s) <=
                      PIPELINE.indexOf(stages[j.id]) ? "●" : "○").join("")}
                  </span>)}
              </td>
              <td>{j.attempts}</td>
              <td className="text-red-600">{j.error?.slice(0, 80)}</td>
              <td className="whitespace-nowrap">
                {/* Reexecuta ESTE job (`/jobs/{id}/retry`, que zera tentativas
                    e devolve ao `queued`). Antes o botão chamava `enqueue`
                    com o mesmo payload: criava um job NOVO, deixando o antigo
                    `failed` para sempre e quebrando a contagem de tentativas
                    e o dedupe. */}
                {REEXECUTAVEL.has(j.state) && (
                  <button className="border rounded px-1 mr-1 text-neutral-700"
                          title="reexecutar este job (zera tentativas)"
                          onClick={() => agir(client.retryJob(j.id))}>↻</button>)}
                {CANCELAVEL.has(j.state) && (
                  <button className="border rounded px-1 text-neutral-700"
                          title={j.state === "leased"
                            ? "pedir cancelamento (o worker honra ao concluir o passo)"
                            : "cancelar agora"}
                          onClick={() => agir(client.cancelJob(j.id))}>✕</button>)}
              </td>
            </tr>))}</tbody>
        </table>
        {!jobs.length && <p className="text-neutral-400 mt-4">Fila vazia.</p>}
      </div>
      <aside className="w-96 border-l p-3 overflow-auto">
        <h3 className="font-medium mb-2">Eventos</h3>
        {feed.map(e => (
          <div key={e.seq} className="mb-1 text-xs font-mono">
            <span className="text-neutral-400">#{e.seq}</span> {e.type}{" "}
            <span className="text-neutral-500">
              {JSON.stringify(e.data).slice(0, 80)}</span>
          </div>))}
        {!feed.length && <p className="text-neutral-400 text-xs">
          Eventos do daemon aparecem aqui em tempo real (SSE).</p>}
      </aside>
    </div>
  );
}

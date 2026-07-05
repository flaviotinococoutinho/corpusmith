// ProcessesPanel (Parte V §9.2): fila de jobs + feed de eventos ao vivo.
import { useEffect, useRef, useState } from "react";
import { client } from "../lib/client";

const STATE_ICON: Record<string, string> = {
  queued: "⏳", leased: "▶️", done: "✅", failed: "❌",
};

const PIPELINE = ["produce", "normalize", "reconcile", "write", "done"];

export function ProcessesPanel() {
  const [jobs, setJobs] = useState<any[]>([]);
  const [feed, setFeed] = useState<any[]>([]);
  // jobId → último estágio da pipeline (page.stage)
  const [stages, setStages] = useState<Record<string, string>>({});
  const esRef = useRef<EventSource | null>(null);

  const load = () => client.jobs().then(r => setJobs(r.jobs));

  useEffect(() => {
    client.connect().then(() => {
      load();
      esRef.current = client.events(e => {
        setFeed(f => [e, ...f].slice(0, 40));
        const d = e.data ?? {};
        if (e.type === "page.stage" && d.id)
          setStages(s => ({ ...s, [d.id]: d.stage }));
        if (String(e.type).startsWith("job.")) load();
      });
    });
    return () => esRef.current?.close();
  }, []);

  return (
    <div className="flex h-full text-sm">
      <div className="flex-1 p-4 overflow-auto">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold">Processos</h2>
          <button className="border rounded px-2 py-1 text-xs" onClick={load}>
            atualizar</button>
        </div>
        <table className="w-full text-xs">
          <thead><tr className="text-left text-neutral-500">
            <th>Job</th><th>Tipo</th><th>Estado</th><th>Tent.</th><th>Erro</th></tr></thead>
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

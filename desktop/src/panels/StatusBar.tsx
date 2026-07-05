// Barra de status global (v0.11): daemon · jobs · orçamento · ticker de
// eventos — o pulso do runtime sempre visível, em qualquer painel.
import { useEffect, useState } from "react";
import { live, DaemonStatus, LiveEvent } from "../lib/live";

const EVENT_LABEL: Record<string, string> = {
  "job.started": "▶️ job iniciado",
  "job.done": "✅ job concluído",
  "job.failed": "❌ job falhou",
  "page.stage": "⚙️ pipeline",
  "compile.done": "📄 compilado",
  "consolidate.done": "🧩 consolidado",
  "memory.promoted": "⭐ promovido",
  "source.ingested": "📥 ingerido",
  "supersede.dependents": "🔗 dependentes",
  "reflect.done": "🪞 reflect",
};

export function StatusBar() {
  const [status, setStatus] = useState<DaemonStatus | null>(live.status);
  const [tick, setTick] = useState<LiveEvent | null>(live.lastEvent);
  useEffect(() => {
    live.start();
    const offS = live.onStatus(setStatus);
    const offE = live.onEvent(setTick);
    return () => { offS(); offE(); };
  }, []);
  const busy = (status?.pending_jobs ?? 0) > 0;
  return (
    <footer className="h-7 border-t bg-neutral-50 flex items-center gap-4
                       px-3 text-xs text-neutral-600 shrink-0">
      <span className="flex items-center gap-1">
        <span className={`inline-block w-2 h-2 rounded-full ${
          status ? "bg-green-500" : "bg-red-400"}`} />
        {status ? "daemon" : "offline"}
      </span>
      <span className={busy ? "text-blue-600" : ""}>
        {busy ? `⏳ ${status!.pending_jobs} job(s)` : "fila vazia"}
      </span>
      {status && <span>💰 US$ {status.budget_left_usd.toFixed(2)}</span>}
      <span className="flex-1 truncate text-neutral-400 font-mono">
        {tick && `${EVENT_LABEL[tick.type] ?? tick.type} · ${
          JSON.stringify(tick.data?.page ?? tick.data?.source ??
                         tick.data?.stage ?? "")}`}
      </span>
    </footer>
  );
}

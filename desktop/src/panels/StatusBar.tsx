// Barra de status global (v0.11): daemon · jobs · orçamento · ticker de
// eventos — o pulso do runtime sempre visível, em qualquer painel.
// v0.16: + saúde profunda (instância, RSS, disco, integridade das stacks).
import { useEffect, useState } from "react";
import { client } from "../lib/client";
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
  const [health, setHealth] = useState<any>(null);
  useEffect(() => {
    live.start();
    const offS = live.onStatus(setStatus);
    const offE = live.onEvent(setTick);
    const probe = () =>
      client.healthFull().then(setHealth).catch(() => setHealth(null));
    // F0: sem o .catch, um daemon ausente gerava rejeição não tratada e a
    // barra continuava exibindo o último estado conhecido
    client.connect().then(probe).catch(() => setHealth(null));
    const timer = setInterval(probe, 30_000);
    return () => { offS(); offE(); clearInterval(timer); };
  }, []);
  const busy = (status?.pending_jobs ?? 0) > 0;
  const stacksOk = health && Object.values(health.stacks ?? {})
    .every((s: any) => !s.present || s.integrity === "ok");
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
      {health && (
        // F-UI: o badge acusava o problema e não oferecia ato nenhum — o
        // usuário via vermelho e não tinha para onde ir. Agora leva à aba
        // que mostra os findings e oferece o reparo, pelo mesmo evento de
        // navegação que a fila "Próxima ação" usa.
        <button
          title={`instância ${health.instance.id} · ${
            health.process.rss_mb} MB · integridade ${
            stacksOk ? "ok" : "PROBLEMA"} — clique para ver os invariantes`}
          className={`hover:underline ${stacksOk ? "" : "text-red-600"}`}
          onClick={() => window.dispatchEvent(
            new CustomEvent("bc:navigate", { detail: "doctor" }))}>
          🩺 {stacksOk ? "ok" : "stacks!"} · 💾{" "}
          {(health.resources.disk_free_mb / 1024).toFixed(1)} GB
        </button>)}
      <span className="flex-1 truncate text-neutral-400 font-mono">
        {tick && `${EVENT_LABEL[tick.type] ?? tick.type} · ${
          JSON.stringify(tick.data?.page ?? tick.data?.source ??
                         tick.data?.stage ?? "")}`}
      </span>
    </footer>
  );
}

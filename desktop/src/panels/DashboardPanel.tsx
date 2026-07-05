import { useEffect, useState } from "react";
import { client } from "../lib/client";   // singleton: export const client = new DaemonClient()

export function DashboardPanel() {
  const [d, setD] = useState<any>(null);
  useEffect(() => { client.connect().then(() => client.dashboard().then(setD)); }, []);
  if (!d) return <div className="p-6">Carregando estado da memória…</div>;
  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <h1 className="text-xl font-semibold">Sua wiki agora</h1>
      <div className="grid grid-cols-3 gap-3 text-sm">
        {[["Páginas OKF", d.pages], ["Chunks indexados", d.chunks],
          ["Decisões", d.decisions], ["Stale", d.stale_count],
          ["Órfãos", d.orphan_count], ["Jobs pendentes", d.pending_jobs],
          ["Orçamento API (US$)", d.budget_left_usd]].map(([l, v]) => (
          <div key={String(l)} className="border rounded p-3">
            <div className="text-2xl font-semibold">{v as any}</div>
            <div className="text-neutral-500">{l}</div>
          </div>))}
      </div>
      <section>
        <h2 className="font-medium mb-2">Ações recomendadas</h2>
        <ol className="list-decimal ml-5 space-y-1 text-sm">
          {d.recommended_actions.map((a: string) => <li key={a}>{a}</li>)}
          {!d.recommended_actions.length && <li>Nada pendente 🎉</li>}
        </ol>
      </section>
      {d.stale.length > 0 && (
        <section>
          <h2 className="font-medium mb-2">Stale para revisar</h2>
          <ul className="text-sm space-y-1">
            {d.stale.map((p: string) => <li key={p} className="font-mono">{p}</li>)}
          </ul>
        </section>)}
    </div>
  );
}

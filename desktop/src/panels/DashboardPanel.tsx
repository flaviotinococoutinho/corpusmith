import { useEffect, useState } from "react";
import { client } from "../lib/client";   // singleton: export const client = new DaemonClient()

function BarList({ data, unit }: { data: [string, number][]; unit?: string }) {
  const max = Math.max(1, ...data.map(([, n]) => n));
  return (
    <div className="space-y-1">
      {data.map(([label, n]) => (
        <div key={label} className="flex items-center gap-2 text-xs">
          <span className="w-36 truncate text-neutral-500">{label}</span>
          <span className="flex-1 h-3 bg-neutral-100 rounded">
            <span className="block h-3 rounded bg-neutral-400"
                  style={{ width: `${(100 * n) / max}%` }} />
          </span>
          <span className="w-10 text-right tabular-nums">{n}{unit}</span>
        </div>))}
      {!data.length && <div className="text-xs text-neutral-400">(vazio)</div>}
    </div>
  );
}

export function DashboardPanel() {
  const [d, setD] = useState<any>(null);
  const [cand, setCand] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [cold, setCold] = useState<any>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const loadCold = () => client.cold().then(setCold).catch(() => setCold(null));
  useEffect(() => {
    client.connect().then(() => {
      client.dashboard().then(setD);
      client.reflectCand().then(setCand).catch(() => setCand(null));
      client.stats().then(setStats).catch(() => setStats(null));
      loadCold();
    });
  }, []);
  const freeze = (path: string) =>
    client.freeze(path)
      .then(r => { setNotice(`🧊 congelada: ${r.page}`); loadCold(); })
      .catch(e => setNotice(`⛔ veto: ${e.message}`));
  const recycle = (path: string) =>
    client.recycle(path)
      .then(r => { setNotice(`♻️ reciclada: ${r.page}`); loadCold(); });
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
      {stats && (
        <section className="grid grid-cols-3 gap-4">
          <div>
            <h2 className="font-medium mb-2 text-sm">Páginas por tipo</h2>
            <BarList data={stats.by_type.slice(0, 8)} />
          </div>
          <div>
            <h2 className="font-medium mb-2 text-sm">
              Distribuição de heat (BLA)</h2>
            <BarList data={stats.heat_buckets.map(
              (n: number, i: number) =>
                [`${(i * 0.2).toFixed(1)}–${((i + 1) * 0.2).toFixed(1)}`, n])} />
          </div>
          <div>
            <h2 className="font-medium mb-2 text-sm">Desfechos (14d)</h2>
            <BarList data={[["✅ útil", stats.outcomes.useful],
                            ["🚫 beco", stats.outcomes.dead_end],
                            ["✏️ corrigido", stats.outcomes.corrected]]} />
            {stats.outcomes_per_day.length > 0 && (
              <div className="flex items-end gap-px h-8 mt-2"
                   title="desfechos por dia">
                {stats.outcomes_per_day.map((p: any) => (
                  <span key={p.day}
                        className="flex-1 bg-neutral-300 rounded-t"
                        style={{ height: `${Math.min(100, p.n * 20)}%` }} />
                ))}
              </div>)}
          </div>
        </section>)}
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
      {notice && <p className="text-sm border rounded p-2 bg-neutral-50">
        {notice}</p>}
      {cand && (cand.promote.length > 0 || cand.archive.length > 0
                || cand.contested.length > 0) && (
        <section className="grid grid-cols-3 gap-3 text-sm">
          <div className="border rounded p-3">
            <h3 className="font-medium mb-1">🔥 Candidatos a promoção</h3>
            {cand.promote.length ? cand.promote.map((c: any) => (
              <div key={c.path} className="font-mono text-xs">{c.path}</div>))
              : <div className="text-neutral-400 text-xs">(nenhuma)</div>}
          </div>
          <div className="border rounded p-3">
            <h3 className="font-medium mb-1">🧊 Candidatos a congelar</h3>
            {cand.archive.length ? cand.archive.map((c: any) => (
              <div key={c.path} className="flex items-center gap-1 text-xs">
                <span className="font-mono flex-1 truncate">{c.path}</span>
                <button className="border rounded px-1"
                        title="mover para a base fria (gates validam)"
                        onClick={() => freeze(c.path)}>🧊</button>
              </div>))
              : <div className="text-neutral-400 text-xs">(nenhuma)</div>}
          </div>
          <div className="border rounded p-3">
            <h3 className="font-medium mb-1">⚔️ Contestadas</h3>
            {cand.contested.length ? cand.contested.map((p: string) => (
              <div key={p} className="font-mono text-xs">{p}</div>))
              : <div className="text-neutral-400 text-xs">(nenhuma)</div>}
          </div>
        </section>)}
      {cold && cold.count > 0 && (
        <section className="border rounded p-3 text-sm">
          <h3 className="font-medium mb-1">
            ❄️ Base fria · {cold.count} memória(s) ·{" "}
            {cold.compression_saved}% compactado ·{" "}
            {cold.recycles} reciclagem(ns)</h3>
          {cold.entries.slice(0, 8).map((e: any) => (
            <div key={e.page} className="flex items-center gap-2 text-xs">
              <span className="font-mono flex-1 truncate">{e.page}</span>
              <span className="text-neutral-400">
                P(recall) {e.recall_p?.toFixed(3) ?? "—"} ·{" "}
                {(e.packed / 1024).toFixed(1)}/{(e.body_bytes / 1024).toFixed(1)} kB</span>
              <button className="border rounded px-1"
                      onClick={() => recycle(e.page)}>♻️ reciclar</button>
            </div>))}
        </section>)}
    </div>
  );
}

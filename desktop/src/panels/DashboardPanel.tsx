import { useEffect, useState } from "react";
import { client } from "../lib/client";   // singleton: export const client = new DaemonClient()
import { DaemonUnavailable } from "./DaemonUnavailable";
import { CurationDialog } from "./CurationDialog";
import type { CurationActOffer, NextActionItem, NextActionsQueue }
  from "../lib/daemonClient";

// R3 (v1.8): action.type → aba onde a ação se realiza. Um clique leva o
// curador à superfície certa; o deep-link à página fica para uma fase
// seguinte (ADR-40). A fila é a ÚNICA chamada-para-ação (UX-1).
const ACTION_TAB: Record<string, string> = {
  answer: "ask", compile: "inbox", link: "graph",
  "resolve-contradiction": "quality", resolve: "wiki",
  review: "wiki", read: "wiki",
};
const navigate = (tab: string) =>
  window.dispatchEvent(new CustomEvent("bc:navigate", { detail: tab }));

// Padrões COMPUTADOS: relações derivadas que o job recomputa, não páginas.
// Veredito sobre página é ato de curadoria (vai ao frontmatter); veredito
// sobre padrão vai para `pattern_verdicts`, com `until` e sem DELETE.
// F4-PR3b: `factual_conflict` é padrão computado como os outros dois, e
// PRECISA estar aqui — sem isto o item de maior densidade da fila nasce sem
// botão de adiar/rejeitar, e "o produto escuta" regride justo no item novo.
// `NextActionItem.kind` é `string`, então `tsc --noEmit` NÃO acusa a falta.
const PADROES = new Set(["bridge", "contradiction", "factual_conflict"]);

function NextActionsQueue({ onApplied }: { onApplied(): void }) {
  const [q, setQ] = useState<NextActionsQueue | null>(null);
  // F1-PR6: o clique abre o ATO quando o item declara ofertas; quando não
  // declara (question/inbox/review/stale/low_yield), continua navegando —
  // trocar tudo por dialog regrediria 5 dos 7 kinds para "sem destino".
  const [aberto, setAberto] = useState<CurationActOffer | null>(null);
  // F0/P-11: antes, pendente E erro caíam no MESMO `null` ⇒ a única
  // chamada-para-ação do produto desaparecia em silêncio enquanto o
  // backend varre o bundle (16-40 s a 2.000 páginas). Agora há três
  // estados distintos: carregando, falhou, vazia.
  const [falhou, setFalhou] = useState(false);
  const carregar = () => {
    setFalhou(false);
    client.nextActions().then(setQ).catch(() => setFalhou(true));
  };
  useEffect(carregar, []);

  /** As páginas que formam o padrão — a chave do veredito sai DELAS, nunca
   *  do rótulo de comunidade (que é um número de época e muda a cada job). */
  const paginasDo = (a: NextActionItem): string[] =>
    a.action.type === "link"
      ? [a.action.src as string, a.action.dst as string]
      : (a.action.pages as string[] | undefined) ?? [a.target];

  const julgar = (a: NextActionItem, status: "rejected" | "deferred",
                  until?: number) =>
    client.patternVerdict({ kind: a.kind, pages: paginasDo(a), status, until })
      .then(carregar)
      .catch(() => setFalhou(true));
  if (falhou)
    return <section><h2 className="font-medium mb-2">Próxima ação</h2>
      <p className="text-sm text-neutral-500">
        não foi possível montar a fila{" "}
        <button className="underline" onClick={carregar}>tentar de novo</button>
      </p></section>;
  if (!q)
    return <section><h2 className="font-medium mb-2">Próxima ação</h2>
      <p className="text-sm text-neutral-400 animate-pulse">
        calculando valor e custo…</p></section>;
  if (!q.actions.length)
    return <section><h2 className="font-medium mb-2">Próxima ação</h2>
      <p className="text-sm text-neutral-500">Nada pendente 🎉</p></section>;
  return (
    <section>
      <div className="flex items-baseline justify-between mb-2">
        <h2 className="font-medium">Próxima ação</h2>
        <span className="text-xs text-neutral-400">
          {q.total} item(ns){q.truncated ? ` · top ${q.actions.length}` : ""} ·
          ranqueado por valor/custo</span>
      </div>
      <ol className="space-y-1 text-sm">
        {q.actions.map((a: NextActionItem, i: number) => (
          <li key={i}
              className="flex items-center gap-3 border rounded px-3 py-2
                         hover:bg-neutral-50">
            <button className="flex-1 text-left"
                    title={a.acts.length ? a.acts[0].label
                      : `ir para ${ACTION_TAB[a.action.type] ?? "wiki"}`}
                    onClick={() => a.acts.length
                      ? setAberto(a.acts[0])
                      : navigate(ACTION_TAB[a.action.type] ?? "wiki")}>
              <div className="flex items-center gap-2">
                <span className="px-1.5 py-0.5 rounded text-[11px]
                                 bg-neutral-100 text-neutral-600 shrink-0">
                  {a.origin}</span>
                <span className="font-medium truncate">{a.title}</span>
              </div>
              <div className="text-xs text-neutral-500 mt-0.5">{a.reason}</div>
            </button>
            {a.acts.slice(1).map((o, j) => (
              <button key={j} className="border rounded px-1.5 py-0.5
                                         text-[11px] shrink-0"
                      title={o.label}
                      onClick={() => setAberto(o)}>{o.act}</button>))}
            {/* F3-PR2: padrão COMPUTADO (ponte, contradição) aceita veredito.
                Sem ele, "já olhei, é falso positivo" não tinha onde ser dito
                e o item de maior VoI voltava ao topo todo dia. Página não
                entra aqui: veredito sobre canônico é ato de curadoria. */}
            {PADROES.has(a.kind) && (
              <div className="flex gap-1 shrink-0">
                <button className="border rounded px-1.5 py-0.5 text-[11px]"
                        title="adiar por 30 dias — volta depois"
                        onClick={() => julgar(a, "deferred",
                                              Date.now() / 1000 + 30 * 86400)}>
                  adiar</button>
                <button className="border rounded px-1.5 py-0.5 text-[11px]"
                        title="não vale a pena — some até alguém reabrir"
                        onClick={() => julgar(a, "rejected")}>dispensar</button>
              </div>)}
            <div className="text-right text-xs tabular-nums shrink-0">
              <div title="valor de informação">VoI {a.value.toFixed(2)}</div>
              <div className="text-neutral-400"
                   title="custo estimado">~{a.cost_min} min</div>
            </div>
          </li>))}
      </ol>
      {aberto && (
        <CurationDialog offer={aberto} onClose={() => setAberto(null)}
                        onApplied={() => { carregar(); onApplied(); }} />)}
    </section>
  );
}

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
  const [erro, setErro] = useState<unknown>(null);
  const loadCold = () => client.cold().then(setCold).catch(() => setCold(null));
  useEffect(() => {
    client.connect().then(() => {
      client.dashboard().then(setD);
      client.reflectCand().then(setCand).catch(() => setCand(null));
      client.stats().then(setStats).catch(() => setStats(null));
      loadCold();
    }).catch(setErro);          // F0: sem isto o painel ficava em
  }, []);                       // "Carregando…" como estado TERMINAL
  const freeze = (path: string) =>
    client.freeze(path)
      .then(r => { setNotice(`🧊 congelada: ${r.page}`); loadCold(); })
      .catch(e => setNotice(`⛔ veto: ${e.message}`));
  const recycle = (path: string) =>
    client.recycle(path)
      .then(r => { setNotice(`♻️ reciclada: ${r.page}`); loadCold(); });
  if (erro) return <DaemonUnavailable error={erro}
                     onRetry={() => client.dashboard().then(setD)} />;
  if (!d) return <div className="p-6">Carregando estado da memória…</div>;
  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <h1 className="text-xl font-semibold">Seu corpus agora</h1>
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
      <NextActionsQueue
        onApplied={() => client.dashboard().then(setD)} />
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
                || cand.low_yield.length > 0) && (
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
            <h3 className="font-medium mb-1">🪫 Baixo rendimento</h3>
            {cand.low_yield.length ? cand.low_yield.map((p: string) => (
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

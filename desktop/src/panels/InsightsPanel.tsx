// 📈 Indicadores (Fase 5): gaps · topologia · atividade · classificadores ·
// tracing de consultas — cada item com a ação de curadoria mais provável.
import { useEffect, useState } from "react";
import { client } from "../lib/client";

function Section({ title, children }: { title: string; children: any }) {
  return (
    <section className="border rounded p-3">
      <h3 className="font-medium text-sm mb-2">{title}</h3>
      {children}
    </section>
  );
}

function Bars({ data }: { data: [string, number][] }) {
  const max = Math.max(1, ...data.map(([, n]) => n));
  return (
    <div className="space-y-1">
      {data.map(([l, n]) => (
        <div key={l} className="flex items-center gap-2 text-xs">
          <span className="w-32 truncate text-neutral-500">{l}</span>
          <span className="flex-1 h-3 bg-neutral-100 rounded">
            <span className="block h-3 rounded bg-neutral-400"
                  style={{ width: `${(100 * n) / max}%` }} /></span>
          <span className="w-8 text-right tabular-nums">{n}</span>
        </div>))}
      {!data.length && <span className="text-xs text-neutral-400">(vazio)</span>}
    </div>
  );
}

export function InsightsPanel() {
  const [ins, setIns] = useState<any>(null);
  const [traces, setTraces] = useState<any[]>([]);
  const [detail, setDetail] = useState<any>(null);
  const load = () => {
    client.insights().then(setIns);
    client.traces().then(r => setTraces(r.traces));
  };
  useEffect(() => { client.connect().then(load); }, []);
  if (!ins) return <div className="p-6">Calculando indicadores…</div>;
  const g = ins.gaps, t = ins.topology;
  return (
    <div className="p-4 grid grid-cols-2 gap-3 text-sm">
      <Section title="🕳 Gaps epistêmicos">
        <div className="text-xs space-y-2">
          <div><b>{g.questions.length}</b> pergunta(s) aberta(s)
            {g.questions.slice(0, 4).map((p: string) => (
              <div key={p} className="font-mono truncate">{p}</div>))}</div>
          <div><b>{g.orphans.length}</b> órfã(s) · <b>{g.contested.length}</b>{" "}
            contestada(s) · <b>{g.stale.length}</b> stale ·{" "}
            <b>{g.cold_count}</b> na base fria</div>
          {g.contested.slice(0, 3).map((p: string) => (
            <div key={p} className="flex items-center gap-1">
              <span className="font-mono flex-1 truncate">⚔️ {p}</span>
              <button className="border rounded px-1"
                      onClick={() => client.markStale(p).then(load)}>
                🟡 stale</button></div>))}
          <div className="pt-1 border-t">Eval:{" "}
            {g.eval.length ? g.eval.map((e: any) =>
              `${e.category} ${e.passed}/${e.total}`).join(" · ")
              : "nunca rodado"}
            <button className="border rounded px-1 ml-2"
                    onClick={() => client.enqueue("eval_memory", {})}>
              ▶ rodar</button></div>
        </div>
      </Section>
      <Section title="🗺 Topologia">
        <div className="text-xs space-y-1">
          <div>{t.nodes} nós · {t.edges} arestas · {t.components}{" "}
            componente(s) · grau médio {t.avg_degree}</div>
          <div>maior componente cobre <b>{t.largest_component_pct}%</b> da base</div>
          {t.bridges.map((b: any) => (
            <div key={b.src + b.dst} className="font-mono truncate">
              🌉 {b.src} ↔ {b.dst} <span className="text-neutral-400">
                peso {b.weight}</span></div>))}
          {!t.bridges.length && <div className="text-neutral-400">
            sem pontes frágeis (rode o job leiden)</div>}
          <button className="border rounded px-1 mt-1"
                  onClick={() => client.enqueue("leiden", {})}>
            ▶ recomputar comunidades/pontes</button>
        </div>
      </Section>
      <Section title="📊 Classificadores">
        <div className="grid grid-cols-2 gap-3">
          <div><div className="text-xs text-neutral-500 mb-1">por origem</div>
            <Bars data={ins.classifiers.by_origin.slice(0, 6)} /></div>
          <div><div className="text-xs text-neutral-500 mb-1">por confiança</div>
            <Bars data={ins.classifiers.by_confidence.slice(0, 6)} /></div>
        </div>
      </Section>
      <Section title="⚡ Atividade (14d)">
        <div className="flex items-end gap-px h-12 mb-2"
             title="eventos por dia">
          {ins.activity.events_per_day.map((d: any) => (
            <span key={d.day} className="flex-1 bg-neutral-300 rounded-t"
                  title={`${d.day}: ${d.n}`}
                  style={{ height: `${Math.min(100, d.n * 4)}%` }} />))}
        </div>
        <Bars data={ins.activity.top_events.map(
          (e: any) => [e.type, e.n]).slice(0, 6)} />
      </Section>
      <Section title="🔬 Tracing de consultas">
        <div className="text-xs space-y-1 max-h-56 overflow-auto">
          {traces.map(tr => (
            <div key={tr.ask_id}>
              <button className="font-mono underline"
                      onClick={() => client.trace(tr.ask_id).then(setDetail)}>
                {tr.ask_id}</button>{" "}
              · {tr.pages} pág · [{tr.streams}]
              {tr.verdict && <span> · {{
                useful: "✅", dead_end: "🚫",
                corrected: "✏️" }[tr.verdict as string]}</span>}
            </div>))}
          {!traces.length && <span className="text-neutral-400">
            faça consultas para ver a proveniência aqui</span>}
        </div>
      </Section>
      {detail && (
        <Section title={`🔬 ${detail.ask_id}`}>
          <div className="text-xs space-y-1">
            {detail.pages.map((p: any) => (
              <div key={p.page} className="font-mono truncate">
                {p.page} ← [{p.streams.join(", ")}]</div>))}
            <div className="pt-1 border-t">pesos atuais:{" "}
              {Object.entries(detail.stream_weights).map(([s, w]: any) =>
                `${s}=${w.toFixed(2)}`).join(" · ") || "(default 1.0)"}</div>
            {detail.outcome && <div>desfecho: {detail.outcome.verdict}</div>}
          </div>
        </Section>)}
    </div>
  );
}

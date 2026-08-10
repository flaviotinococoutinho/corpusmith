// 📈 Indicadores (Fase 5): gaps · topologia · atividade · classificadores ·
// tracing de consultas — cada item com a ação de curadoria mais provável.
import { useEffect, useState } from "react";
import { client } from "../lib/client";
import { DaemonUnavailable } from "./DaemonUnavailable";

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

const STRUCTURE_LABEL: Record<string, string> = {
  incipiente: "🌱 incipiente", disperso: "🏝 disperso (ilhas)",
  focado: "🎯 focado (1–2 temas dominam)",
  diverso: "🌐 diverso (temas equilibrados e ligados)",
};

export function InsightsPanel() {
  const [ins, setIns] = useState<any>(null);
  const [traces, setTraces] = useState<any[]>([]);
  const [detail, setDetail] = useState<any>(null);
  const [gaps, setGaps] = useState<any>(null);
  const [notice, setNotice] = useState("");
  const load = () => {
    client.insights().then(setIns);
    client.traces().then(r => setTraces(r.traces));
    client.gaps().then(setGaps).catch(() => {});
  };
  const [erro, setErro] = useState<unknown>(null);
  useEffect(() => { client.connect().then(load).catch(setErro); }, []);
  if (erro) return <DaemonUnavailable error={erro} onRetry={load} />;
  if (!ins) return <div className="p-6">Calculando indicadores…</div>;
  const g = ins.gaps, t = ins.topology;
  const f = ins.freshness;
  return (
    <div className="p-4 grid grid-cols-2 gap-3 text-sm">
      {notice && <p className="col-span-2 text-xs border rounded p-2
        bg-neutral-50">{notice}</p>}
      {/* X2: os indicadores derivam do MAPA — sem o carimbo, um painel
          computado sobre um mapa velho parecia atual. O grafo já tinha o
          badge; os demais artefatos derivados não. */}
      {f && (
        <p className="col-span-2 text-xs text-neutral-500">
          {f.computed_at
            ? <>mapa de {new Date(f.computed_at * 1000).toLocaleString()}
                {" · partição por "}{f.partition_backend}
                {f.partition_backend === "components" &&
                  <span className="text-amber-700"> (sem [ml] — componentes
 conexos, não Leiden)</span>}</>
            : <span className="text-amber-700">⏳ mapa nunca computado — os
 indicadores usam grau e componentes brutos</span>}
        </p>)}
      <Section title="🔗 Lacunas estruturais (fios ausentes do discurso)">
        <div className="text-xs space-y-2">
          <p className="text-neutral-400">
            Dois temas grandes que quase nunca se conectam — a pergunta-ponte
            é o que mais agrega ao entendimento (déficit vs. o esperado por
            acaso, modelo de configuração).</p>
          {gaps?.gaps?.length ? gaps.gaps.map((gp: any) => (
            <div key={gp.rep_a + gp.rep_b} className="border rounded p-2">
              <div className="font-medium">{gp.title_a} ↔ {gp.title_b}
                <span className="text-neutral-400 ml-2">déficit {
                  gp.deficit} · esperava {gp.expected}, tem {gp.actual}</span>
              </div>
              <div className="italic text-neutral-600">"{gp.question}"</div>
              <button className="border rounded px-1 mt-1"
                onClick={() => client.promote({
                  kind: "question", title: gp.question,
                  content: `# ${gp.question}\n\nPergunta-ponte entre `
                    + `**${gp.title_a}** (${gp.rep_a}) e **${gp.title_b}** `
                    + `(${gp.rep_b}) — temas que a memória mantém separados.`,
                  tags: ["ponte"] }).then(() => {
                    setNotice(`❓ pergunta-ponte capturada: ${gp.question}`);
                    load(); })}>
                ➕ capturar como pergunta</button>
            </div>)) : <span className="text-neutral-400">
            sem lacunas (rode o job leiden p/ comunidades, ou a base ainda
            é pequena/coesa)</span>}
          {gaps?.articulators?.length > 0 && (
            <div className="pt-1 border-t">Articuladores (intermediação):{" "}
              {gaps.articulators.slice(0, 5).map((a: any) =>
                a.title).join(" · ")}</div>)}
        </div>
      </Section>
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
          {t.structure && <div>estrutura do discurso:{" "}
            <b>{STRUCTURE_LABEL[t.structure] ?? t.structure}</b>{" "}
            <span className="text-neutral-400">({t.communities} comunidade(s),
            uniformidade {t.evenness})</span></div>}
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

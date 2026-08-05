// QualityPanel.tsx — o "CI visual" da base (+ eval de memória, v0.8 §10/§11.2;
// + contratos epistêmicos, v1.6 ADR-38)
import { useEffect, useState } from "react";
import { client } from "../lib/client";

const EVAL_CATS = ["extract", "multi_session", "temporal", "update", "abstain"];

// badge por status de avaliação — linguagem operacional, não filosófica
const EVAL_BADGE: Record<string, [string, string]> = {
  evaluated: ["avaliado", "bg-green-100 text-green-700"],
  partially_evaluated: ["parcial", "bg-amber-100 text-amber-700"],
  unevaluated: ["não avaliado", "bg-neutral-200 text-neutral-600"],
  drifted: ["drifted", "bg-red-100 text-red-700"],
  invalidated: ["invalidado", "bg-red-100 text-red-700"],
};

function EpistemicsSection() {
  const [data, setData] = useState<any>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [detail, setDetail] = useState<any>(null);
  useEffect(() => { client.epistemics().then(setData).catch(() => {}); }, []);
  useEffect(() => {
    if (open) client.epistemicsMechanism(open).then(setDetail);
    else setDetail(null);
  }, [open]);
  if (!data) return null;
  return (
    <section>
      <h3 className="font-medium mb-2">🔬 Contratos epistêmicos
        <span className="text-neutral-400 text-xs ml-2">
          (o que cada mecanismo pode legitimamente alegar — epistemics.toml)
        </span>
        {!data.lint?.ok &&
          <span className="ml-2 bg-red-600 text-white rounded px-1 text-xs">
            lint com erros</span>}
      </h3>
      <table className="w-full text-xs">
        <thead><tr className="text-left text-neutral-500">
          <th>Mecanismo</th><th>Garantia (relativa)</th>
          <th>Avaliação</th><th>Fallback</th></tr></thead>
        <tbody>{(data.mechanisms ?? []).map((m: any) => {
          const [label, cls] = EVAL_BADGE[m.evaluation_status] ??
            EVAL_BADGE.unevaluated;
          return (
            <tr key={m.mechanism_id} className="border-t align-top cursor-pointer"
                onClick={() => setOpen(open === m.mechanism_id ? null
                                        : m.mechanism_id)}>
              <td className="font-mono py-1">{m.mechanism_id}
                {m.high_impact &&
                  <span className="ml-1 text-red-600" title="alto impacto">●</span>}
              </td>
              <td>{m.guarantee_kind}
                <div className="text-neutral-400">{m.guarantee_relative_to}</div>
              </td>
              <td><span className={`rounded px-1 ${cls}`}>{label}</span></td>
              <td className="font-mono">{(m.fallback ?? []).join(", ") || "—"}</td>
            </tr>);
        })}</tbody>
      </table>
      {detail && (
        <div className="mt-2 border rounded p-3 text-xs space-y-2 bg-neutral-50">
          <div className="font-medium">{detail.title}</div>
          <div><b>Decisão:</b> {detail.decision}</div>
          <div><b>Vieses indutivos:</b>
            <ul className="list-disc ml-4">{detail.inductive_biases.map(
              (t: string, i: number) => <li key={i}>{t}</li>)}</ul></div>
          <div><b>Pressupostos:</b>
            <ul className="list-disc ml-4">{detail.assumptions.map(
              (t: string, i: number) => <li key={i}>{t}</li>)}</ul></div>
          <div><b>Failure modes conhecidos:</b>
            <ul className="list-disc ml-4">{detail.known_failure_modes.map(
              (t: string, i: number) => <li key={i}>{t}</li>)}</ul></div>
          <div><b>Não interprete como:</b>
            <ul className="list-disc ml-4">{(detail.misinterpretations ?? []).map(
              (t: string, i: number) => <li key={i}>{t}</li>)}</ul></div>
          <div><b>Escopo avaliado:</b> {detail.evaluations?.length
            ? detail.evaluations.map((e: any) =>
                `${e.dataset} (n=${e.sample_size}; ` +
                `${(e.query_categories ?? []).join(", ")})`).join(" · ")
            : "nenhuma avaliação registrada — não há evidência de " +
              "generalização"}</div>
          <div><b>Fora de escopo:</b> {(detail.evaluations?.[0]?.out_of_scope
            ?? detail.validity_scope ?? []).join(" · ")}</div>
        </div>)}
      {/* G-10: a tabela acima só mostra o que EXISTE. Um contrato prometido
          por `docs/14` e nunca escrito era invisível aqui — o painel contava
          15 mecanismos e o leitor não tinha como saber quantos faltavam. */}
      {(data.lint?.findings ?? []).some(
        (f: any) => f.code === "epistemic.mechanism_promised") && (
        <div className="mt-2 text-xs text-amber-700">
          <b>Contratos devidos e ainda não escritos:</b>
          <ul className="list-disc ml-4">
            {(data.lint.findings ?? [])
              .filter((f: any) => f.code === "epistemic.mechanism_promised")
              .map((f: any) => (
                <li key={f.mechanism_id}>
                  <span className="font-mono">{f.mechanism_id}</span>
                  {" — "}{f.message}
                </li>))}
          </ul>
        </div>)}
    </section>
  );
}

export function QualityPanel() {
  const [q, setQ] = useState<any>(null);
  useEffect(() => { client.quality().then(setQ); }, []);
  if (!q) return <div className="p-6">Rodando lint…</div>;
  const sevColor: any = { error: "text-red-600", warn: "text-amber-600",
                          info: "text-neutral-500" };
  const evalBy: Record<string, any> = {};
  for (const c of q.eval ?? []) evalBy[c.category] = c;
  return (
    <div className="p-4 space-y-4 text-sm">
      <div className="flex gap-4">
        {[["Erros", q.errors], ["Warnings", q.warnings],
          ["Órfãos", q.orphan_count], ["Stale", q.stale_count],
          ["Privacy coverage", q.privacy_coverage + "%"]].map(([l, v]) => (
          <div key={String(l)} className="border rounded p-3">
            <div className="text-xl font-semibold">{v as any}</div>
            <div className="text-neutral-500 text-xs">{l}</div>
          </div>))}
      </div>
      <section>
        <h3 className="font-medium mb-2">Eval de memória (LongMemEval local)</h3>
        <div className="flex gap-3">
          {EVAL_CATS.map(cat => {
            const c = evalBy[cat];
            const pct = c && c.total ? Math.round(100 * c.passed / c.total) : null;
            return (
              <div key={cat} className="w-32">
                <div className="text-xs text-neutral-500">{cat}</div>
                <div className="h-2 bg-neutral-200 rounded">
                  <div className={`h-2 rounded ${pct === null ? "" :
                    pct >= 80 ? "bg-green-500" : pct >= 50 ? "bg-amber-500"
                    : "bg-red-500"}`} style={{ width: `${pct ?? 0}%` }} />
                </div>
                <div className="text-xs">{c ? `${c.passed}/${c.total}` : "—"}</div>
              </div>);
          })}
        </div>
        {q.eval_metrics && (
          <p className="text-xs text-neutral-500 mt-2">
            📐 recall@5 médio {q.eval_metrics.mean_recall_at_5 ?? "—"} ·
            {" "}MRR médio {q.eval_metrics.mean_mrr ?? "—"} ·
            {" "}taxa geral {q.eval_metrics.overall_pass_rate ?? "—"}
            {" "}({q.eval_metrics.graded_cases ?? 0} casos ranqueados —
            do Generalization Envelope mais recente)</p>)}
      </section>
      {q.bridges?.length > 0 && (
        <section>
          <h3 className="font-medium mb-1">🌉 Pontes frágeis do grafo
            <span className="text-neutral-400 text-xs ml-2">
              (blocos ligados por um fio fraco — linke mais)</span></h3>
          {q.bridges.map((b: any) => (
            <div key={b.src + b.dst} className="text-xs font-mono">
              {b.src} ↔ {b.dst}
              <span className="text-neutral-400"> · peso {b.weight}
                {" "}· lados {b.small_side}/{b.large_side}</span>
            </div>))}
        </section>)}
      <table className="w-full text-xs">
        <thead><tr className="text-left text-neutral-500">
          <th>Sev</th><th>Camada</th><th>Regra</th><th>Página</th><th>Detalhe</th></tr></thead>
        <tbody>{q.findings.map((f: any, i: number) => (
          <tr key={i} className="border-t">
            <td className={sevColor[f.severity]}>{f.severity}</td>
            <td>{f.okf_conformance ? "OKF" : "política"}</td>
            <td className="font-mono">{f.rule}
              {f.rule === "policy.identifier_invalid" &&
                <span className="ml-1 bg-red-600 text-white rounded px-1">
                  checksum</span>}</td>
            <td className="font-mono">{f.path}</td>
            <td>{f.message}</td>
          </tr>))}</tbody>
      </table>
      <EpistemicsSection />
    </div>
  );
}

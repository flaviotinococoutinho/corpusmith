// QualityPanel.tsx — o "CI visual" da base (+ eval de memória, v0.8 §10/§11.2)
import { useEffect, useState } from "react";
import { client } from "../lib/client";

const EVAL_CATS = ["extract", "multi_session", "temporal", "update", "abstain"];

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
    </div>
  );
}

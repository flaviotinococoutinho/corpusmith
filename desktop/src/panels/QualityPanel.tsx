// QualityPanel.tsx — o "CI visual" da base
import { useEffect, useState } from "react";
import { client } from "../lib/client";

export function QualityPanel() {
  const [q, setQ] = useState<any>(null);
  useEffect(() => { client.quality().then(setQ); }, []);
  if (!q) return <div className="p-6">Rodando lint…</div>;
  const sevColor: any = { error: "text-red-600", warn: "text-amber-600",
                          info: "text-neutral-500" };
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
      <table className="w-full text-xs">
        <thead><tr className="text-left text-neutral-500">
          <th>Sev</th><th>Camada</th><th>Regra</th><th>Página</th><th>Detalhe</th></tr></thead>
        <tbody>{q.findings.map((f: any, i: number) => (
          <tr key={i} className="border-t">
            <td className={sevColor[f.severity]}>{f.severity}</td>
            <td>{f.okf_conformance ? "OKF" : "política"}</td>
            <td className="font-mono">{f.rule}</td>
            <td className="font-mono">{f.path}</td>
            <td>{f.message}</td>
          </tr>))}</tbody>
      </table>
    </div>
  );
}

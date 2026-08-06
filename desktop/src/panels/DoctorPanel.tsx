// 🩺 Integridade — F-UI.
//
// `GET /system/doctor` e `POST /system/doctor/repair` existem desde a F0, e
// `daemonClient` declarava os dois métodos desde então. Nenhum painel os
// chamava: `grep '\.doctor(' desktop/src` devolvia zero fora do cliente. Os
// INV-001..006 — índice órfão, índice obsoleto, supersedida vazando para a
// recuperação, mapa de padrões velho, dois temas canônicos vivos, derivação
// atrasada — eram o único verificador de integridade do produto e só existiam
// via `llmwiki doctor` no terminal.
//
// O usuário do app via `🩺 stacks!` em vermelho na StatusBar: sabia que algo
// tinha quebrado e não tinha por onde agir, embora três dos seis se resolvam
// com um POST. Esta tela é esse POST.
import { useCallback, useEffect, useState } from "react";
import { client } from "../lib/client";
import type { DoctorReport } from "../lib/daemonClient";

// `REPAIRABLE` do backend (usecases/diagnose.py:49). Duplicado aqui de
// propósito e por ora: o relatório não diz quais findings o reparo alcança, e
// prometer reparo de um INV que o POST não toca seria pior que não prometer.
const REPARAVEIS = new Set(["INV-001", "INV-002", "INV-003"]);

const ESTADO_LABEL: Record<string, string> = {
  fresh: "fresca", stale: "atrasada",
  stale_upstream: "fonte acima mudou", absent: "nunca computada",
};

export function DoctorPanel() {
  const [rel, setRel] = useState<DoctorReport | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [reparando, setReparando] = useState(false);

  const carregar = useCallback(() => {
    setErro(null);
    client.doctor().then(setRel).catch(e => setErro(String(e)));
  }, []);
  useEffect(carregar, [carregar]);

  const reparar = () => {
    setReparando(true);
    setErro(null);
    client.doctorRepair()
      .then(setRel)
      .catch(e => setErro(String(e)))
      .finally(() => setReparando(false));
  };

  if (erro) return (
    <div className="p-6 text-sm text-red-600">
      não foi possível consultar o doctor: {erro}
      <button className="ml-2 underline" onClick={carregar}>tentar de novo</button>
    </div>);
  if (!rel) return <div className="p-6 text-sm">verificando invariantes…</div>;

  const temReparavel = rel.findings.some(f => REPARAVEIS.has(f.inv));
  return (
    <div className="p-6 space-y-4">
      <header className="flex items-center gap-3">
        <h2 className="text-lg font-medium">🩺 Integridade</h2>
        <span className={`rounded px-2 py-0.5 text-xs ${rel.ok
          ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"}`}>
          {rel.ok ? "todos os invariantes valem"
                  : `${rel.counts.error} erro(s) · ${rel.counts.warn} aviso(s)`}
        </span>
        <button className="text-xs underline" onClick={carregar}>reverificar</button>
      </header>

      <p className="text-xs text-neutral-500 max-w-2xl">
        Os invariantes verificam a relação entre o bundle canônico e as
        projeções que derivam dele. Um aviso não é defeito: derivação atrasada
        continua servível — o erro é a projeção que contradiz a autoridade.
      </p>

      {rel.findings.length === 0 && (
        <div className="text-sm text-neutral-500">Nenhum achado.</div>)}

      <ul className="space-y-2">
        {rel.findings.map((f, i) => (
          <li key={i} className="border rounded p-3 text-sm">
            <div className="flex items-center gap-2">
              <span className={`font-mono text-xs rounded px-1 ${
                f.severity === "error" ? "bg-red-100 text-red-700"
                                       : "bg-amber-100 text-amber-800"}`}>
                {f.inv}
              </span>
              {REPARAVEIS.has(f.inv)
                ? <span className="text-xs text-green-700">reparável aqui</span>
                : <span className="text-xs text-neutral-400">
                    exige ato específico</span>}
            </div>
            <div className="mt-1">{f.message}</div>
            {f.hint && <div className="text-xs text-neutral-500 mt-1">{f.hint}</div>}
          </li>))}
      </ul>

      <div className="flex items-center gap-3">
        <button
          className="px-3 py-1.5 rounded bg-neutral-900 text-white text-sm
                     disabled:opacity-40"
          disabled={!temReparavel || reparando}
          onClick={reparar}>
          {reparando ? "reconstruindo o índice…" : "Reparar o que é reparável"}
        </button>
        <span className="text-xs text-neutral-500">
          {temReparavel
            ? "reconstrói o index.db INTEIRO a partir do bundle — só o full purga órfão nunca rastreado"
            : "nada reparável por reconstrução do índice"}
        </span>
      </div>

      {rel.repaired && (
        <div className="text-xs text-green-700">
          índice reconstruído ({rel.repaired.mode}
          {rel.repaired.pages != null && `, ${rel.repaired.pages} páginas`}).
        </div>)}

      {rel.derivations && Object.keys(rel.derivations).length > 0 && (
        <section>
          <h3 className="text-sm font-medium mb-1">Cadeia de derivações</h3>
          <table className="text-xs">
            <tbody>
              {Object.entries(rel.derivations).map(([nome, d]) => (
                <tr key={nome} className="border-t">
                  <td className="font-mono pr-3 py-1">{nome}</td>
                  <td className={`pr-3 ${d.state === "fresh"
                    ? "text-green-700" : "text-amber-700"}`}>
                    {ESTADO_LABEL[d.state] ?? d.state}
                  </td>
                  <td className="text-neutral-500">{d.reason}</td>
                </tr>))}
            </tbody>
          </table>
        </section>)}
    </div>
  );
}

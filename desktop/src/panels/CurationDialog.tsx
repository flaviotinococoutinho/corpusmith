// CurationDialog (F1-PR6) — o clique da fila abre o ATO, com preview.
//
// Até aqui o clique projetava um dict de 2-4 chaves numa string de aba:
// lia `action.type` e jogava fora `src`/`dst`/`pages`. Os dois itens do
// topo da fila — contradição (VoI 0.85) e ponte frágil (maior densidade) —
// já carregavam exatamente os parâmetros que os atos exigem.
//
// Duas armadilhas do fluxo, ambas verificadas no backend:
// 1. preview BLOQUEADO volta 200 com `blocked:true`, NUNCA 422 — no
//    dry-run o `return` precede o `raise`. Aplicar assim é falha
//    garantida, então o botão desabilita e os findings explicam;
// 2. o 409 do undo é levantado dentro do `_plan()`, ou seja acontece já
//    no PRIMEIRO passo — o erro tem de ser tratado no preview também.
//
// O dialog NÃO fecha sozinho no sucesso: a resposta traz o commit sha, a
// única prova visível de que o ato virou história no Git (que é a
// autoridade — `curation_acts` é índice).
import { useEffect, useState } from "react";
import { client } from "../lib/client";
import type { CurationActOffer, CurationPreview, Finding }
  from "../lib/daemonClient";
import { CurationError } from "../lib/daemonClient";

function Diff({ texto }: { texto: string }) {
  if (!texto.trim())
    return <p className="text-xs text-neutral-500">
      nada muda nesta página (NOOP)</p>;
  return (
    <pre className="text-[11px] leading-tight overflow-x-auto bg-neutral-50
                    border rounded p-2">
      {texto.split("\n").map((linha, i) => (
        <div key={i} className={
          linha.startsWith("+") ? "text-green-700"
            : linha.startsWith("-") ? "text-red-700"
              : linha.startsWith("@@") ? "text-blue-600" : ""}>
          {linha}
        </div>))}
    </pre>
  );
}

function Findings({ itens }: { itens: Finding[] }) {
  if (!itens.length) return null;
  return (
    <ul className="text-xs space-y-1">
      {itens.map((f, i) => (
        <li key={i} className={f.severity === "error" ? "text-red-700"
          : f.severity === "warn" ? "text-amber-700" : "text-neutral-500"}>
          <span className="font-mono">{f.rule}</span> · {f.path}: {f.message}
        </li>))}
    </ul>
  );
}

export function CurationDialog(
  { offer, onClose, onApplied }:
  { offer: CurationActOffer; onClose(): void; onApplied(): void },
) {
  const [extras, setExtras] = useState<Record<string, string>>(
    Object.fromEntries(offer.needs.map(n => [n, ""])));
  const [preview, setPreview] = useState<CurationPreview | null>(null);
  const [erro, setErro] = useState<CurationError | Error | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [feito, setFeito] = useState<{ id?: number; commit?: string } | null>(
    null);

  const params = { ...offer.params, ...extras };
  const faltando = offer.needs.filter(n => !extras[n]);
  const longo = (nome: string) => (offer.multiline ?? []).includes(nome);

  // Valor inicial dos campos longos (F1-PR3): o corpo ATUAL da página. Sem
  // isso o textarea abriria vazio e aplicar SUBSTITUIRIA a página que o
  // usuário quis corrigir. Qual página e qual campo vêm da oferta, não de
  // um `if (act === "edit")` aqui.
  useEffect(() => {
    const fontes = Object.entries(offer.prefill ?? {});
    if (!fontes.length) return;
    let vivo = true;
    Promise.all(fontes.map(([nome, de]) =>
      client.page(de.page).then(pg => [nome, pg[de.field]] as const)))
      .then(pares => { if (vivo) setExtras(a => ({ ...a, ...Object.fromEntries(pares) })); })
      .catch(e => { if (vivo) setErro(e); });
    return () => { vivo = false; };
  }, [offer]);

  const previsar = () => {
    if (faltando.length) return;
    setOcupado(true); setErro(null);
    client.curationAct(offer.act, params, true)
      .then(r => setPreview(r.preview))
      .catch(e => { setPreview(null); setErro(e); })
      .finally(() => setOcupado(false));
  };
  // Debounce: o preview roda o Harness sobre a página inteira, e num campo
  // longo cada tecla dispararia um. Nos campos curtos o atraso é
  // imperceptível — e o `clearTimeout` garante um preview por pausa.
  useEffect(() => {
    const t = setTimeout(previsar, 350);
    return () => clearTimeout(t);
  }, [JSON.stringify(params)]);

  const aplicar = () => {
    setOcupado(true); setErro(null);
    client.curationAct(offer.act, params, false)
      .then(r => { setFeito({ id: r.id, commit: r.commit }); onApplied(); })
      .catch(e => setErro(e))
      .finally(() => setOcupado(false));
  };

  const findingsDoErro = erro instanceof CurationError
    ? erro.harnessFindings : [];

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center
                    p-6 z-50" onClick={onClose}>
      <div className="bg-white rounded-lg p-4 max-w-3xl w-full max-h-full
                      overflow-y-auto space-y-3"
           onClick={e => e.stopPropagation()}>
        <h2 className="font-medium">{offer.label}</h2>

        {offer.needs.map(nome => (
          <label key={nome} className="block text-sm">
            <span className="text-neutral-600">{nome}</span>
            {offer.options?.[nome] ? (
              <select className="block w-full border rounded px-2 py-1 mt-1"
                      value={extras[nome]}
                      onChange={e => setExtras(
                        { ...extras, [nome]: e.target.value })}>
                <option value="">escolha…</option>
                {offer.options[nome].map(o =>
                  <option key={o} value={o}>{o}</option>)}
              </select>
            ) : longo(nome) ? (
              <textarea className="block w-full border rounded px-2 py-1 mt-1
                                   font-mono text-xs h-64"
                        spellCheck={false}
                        value={extras[nome]}
                        onChange={e => setExtras(
                          { ...extras, [nome]: e.target.value })} />
            ) : (
              <input className="block w-full border rounded px-2 py-1 mt-1"
                     value={extras[nome]}
                     onChange={e => setExtras(
                       { ...extras, [nome]: e.target.value })} />
            )}
          </label>))}

        {feito ? (
          <div className="space-y-2">
            <p className="text-sm">
              ✅ aplicado · ato #{feito.id} · commit{" "}
              <code className="text-xs">{feito.commit?.slice(0, 8)}</code>
            </p>
            <button className="border rounded px-3 py-1 text-sm"
                    onClick={onClose}>Fechar</button>
          </div>
        ) : (
          <>
            {faltando.length > 0 && (
              <p className="text-sm text-neutral-500">
                {faltando.some(longo) ? "carregando o conteúdo atual…"
                  : `escolha ${faltando.join(", ")} para ver o que vai mudar`}
              </p>)}
            {ocupado && <p className="text-sm text-neutral-400 animate-pulse">
              calculando…</p>}
            {erro && (
              <div className="border-l-2 border-red-400 pl-2 space-y-1">
                <p className="text-sm text-red-700">{erro.message}</p>
                <Findings itens={findingsDoErro} />
              </div>)}
            {preview && (
              <div className="space-y-2">
                <p className="text-sm text-neutral-700">{preview.note}</p>
                {Object.entries(preview.diffs).map(([pagina, texto]) => (
                  <div key={pagina}>
                    <div className="text-xs font-mono text-neutral-500">
                      {pagina}</div>
                    <Diff texto={texto} />
                  </div>))}
                <Findings itens={preview.findings} />
                {preview.dependents.length > 0 && (
                  <p className="text-xs text-neutral-500">
                    dependentes a <strong>revisar depois</strong> (não são
                    alterados por este ato):{" "}
                    {preview.dependents.join(", ")}</p>)}
              </div>)}
            <div className="flex gap-2 pt-1">
              <button
                className="border rounded px-3 py-1 text-sm
                           disabled:opacity-40"
                disabled={ocupado || !preview || preview.blocked}
                title={preview?.blocked
                  ? "o Harness rejeitaria esta escrita — veja os findings"
                  : undefined}
                onClick={aplicar}>Aplicar</button>
              <button className="border rounded px-3 py-1 text-sm"
                      onClick={onClose}>Cancelar</button>
            </div>
          </>)}
      </div>
    </div>
  );
}

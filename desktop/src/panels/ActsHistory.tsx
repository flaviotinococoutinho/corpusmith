// 🕘 Atos aplicados, e o desfazer — F-UI.
//
// `UndoCurationAct` está completo no backend desde o F1-PR1: desfaz por
// escrita-para-frente, liga `undoes`/`undone_by` na mesma transação e recusa
// com 409 nomeado (`UndoNotExpressible`) quando o estado anterior existe mas
// não é alcançável escrevendo para a frente. `GET /curation/history` devolve
// o `id` que ele precisa.
//
// E nada disso era alcançável pelo app: `/curation/history` não tinha método
// no cliente, então não havia de onde tirar o `act_id`. Aplicar era
// irreversível pela interface — `undo.py:1` promete "arrepender-se sem sair do
// produto" e o arrependimento só existia no CLI, que também não lista ids.
//
// O 409 é renderizado como MOTIVO, não como falha genérica: recusar dizendo
// por que é o comportamento que o ato foi escrito para ter, e engoli-lo aqui
// desperdiçaria a única parte difícil dele.
import { useCallback, useEffect, useState } from "react";
import { client } from "../lib/client";
import { CurationError, type CurationAct } from "../lib/daemonClient";

function quando(ts: number): string {
  return new Date(ts * 1000).toLocaleString();
}

export function ActsHistory() {
  const [atos, setAtos] = useState<CurationAct[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState<number | null>(null);

  const carregar = useCallback(() => {
    client.curationHistory()
      .then(r => setAtos(r.acts))
      .catch(e => { setAtos([]); setErro(String(e)); });
  }, []);
  useEffect(carregar, [carregar]);

  const desfazer = (id: number) => {
    setErro(null);
    setOcupado(id);
    client.curationAct("undo", { act_id: String(id) }, false)
      .then(carregar)
      .catch(e => setErro(e instanceof CurationError && e.status === 409
        ? `não dá para desfazer o ato #${id}: ${e.message}`
        : String(e)))
      .finally(() => setOcupado(null));
  };

  if (!atos) return <p className="text-xs text-neutral-400">carregando…</p>;
  return (
    <div className="text-xs">
      {erro && <p className="text-red-600 mb-2">{erro}</p>}
      {!atos.length && (
        <p className="text-neutral-400">
          Nenhum ato de curadoria aplicado ainda.</p>)}
      <ul className="space-y-1">
        {atos.map(a => {
          const desfeito = a.undone_by != null;
          return (
            <li key={a.id} className="flex items-center gap-2 border-t py-1">
              <span className="font-mono text-neutral-400">#{a.id}</span>
              <span className="font-medium">{a.act}</span>
              <span className="flex-1 truncate text-neutral-500"
                    title={a.pages.join(" · ")}>
                {a.pages.join(" · ")}
              </span>
              <span className="text-neutral-400">{quando(a.created_at)}</span>
              {a.undoes != null && (
                <span className="text-neutral-400"
                      title={`este ato desfaz o #${a.undoes}`}>
                  ↩︎ #{a.undoes}</span>)}
              {desfeito
                ? <span className="text-neutral-400"
                        title={`desfeito pelo ato #${a.undone_by}`}>
                    desfeito</span>
                : <button className="border rounded px-1 disabled:opacity-40"
                          disabled={ocupado === a.id}
                          onClick={() => desfazer(a.id)}>
                    {ocupado === a.id ? "desfazendo…" : "desfazer"}</button>}
            </li>);
        })}
      </ul>
      <p className="text-neutral-400 mt-2">
        Desfazer escreve PARA A FRENTE — nada é apagado do histórico. Quando o
        estado anterior não é alcançável assim, o ato recusa e diz por quê.
      </p>
    </div>
  );
}

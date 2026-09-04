// 🧾 A ficha do conceito na tela (Q-1 — RFC-006 V6, com V2/V3/V5 junto).
//
// A capacidade existia inteira no CLI e não tinha superfície: a reincidência
// da patologia de `docs/17` §1.4 ("o backend termina onde a interface
// começa"). Este componente é o outro lado da ponte.
//
// **A regra que ele obedece linha a linha**: nenhum número epistêmico
// aparece sem a ressalva do mecanismo ao lado, e nenhum silêncio é
// apresentado como resultado. Daí os dois estados vazios serem DIFERENTES:
//
//   `computed === false`  → "ainda não calculado" + o comando que calcula
//   `computed === true`, sem linha → "nada observado" (que não é "fácil",
//                                     não é "estável", não é "sem conflito")
//
// Empatá-los seria vender ausência de medição como medição — o avesso
// exato da autocertificação que o contrato `concept_sheet` recusa.
import type { ConceptSheet } from "../lib/daemonClient";

/** Uma linha do pitch: rótulo, valor e a ressalva que o qualifica. */
function Linha({ icone, titulo, children, means }: {
  icone: string; titulo: string; children: any; means?: string;
}) {
  return (
    <section className="border-t pt-2" aria-label={titulo}>
      <h4 className="font-medium text-xs">{icone} {titulo}</h4>
      <div className="text-xs">{children}</div>
      {means && <p className="text-[11px] text-neutral-500 mt-0.5">{means}</p>}
    </section>
  );
}

/** O vazio HONESTO: diz qual dos dois vazios é, e o que fazer com ele. */
function NaoCalculado({ refresh }: { refresh: string }) {
  return (
    <span className="text-neutral-500">
      ainda não calculado nesta máquina — rode <code>{refresh}</code>
    </span>
  );
}

export function ConceptSheetView({ sheet }: { sheet: ConceptSheet }) {
  const { stability: e, difficulty: d, lens: l, divergence: v } = sheet;
  const casos = sheet.applications.cases;
  const medicao = sheet.applications.measurement;
  return (
    <div className="space-y-2" role="region"
         aria-label={`Ficha do conceito: ${sheet.title}`}>
      <h3 className="font-medium">🧾 Ficha do conceito</h3>

      <Linha icone="⏱" titulo="Quanto custa ler" means={sheet.cost.how}>
        <b>{sheet.cost.read_minutes} min</b>{" "}
        <span className="text-neutral-500">
          ({sheet.cost.words} palavras)</span>
      </Linha>

      <Linha icone="🪨" titulo="O que menos muda" means={e.means}>
        {!e.computed ? <NaoCalculado refresh={e.refresh} /> : (
          <>
            <b>{e.edits}</b> edição(ões) no histórico · ciclo{" "}
            <b>{e.lifecycle}</b>
            {e.freshness && e.freshness.state !== "fresh" && (
              <span className="text-amber-700">
                {" "}· projeção {e.freshness.state}
                {e.freshness.reason ? ` (${e.freshness.reason})` : ""}</span>)}
            {e.computed_from && (
              <span className="text-neutral-400 font-mono">
                {" "}· de {e.computed_from.slice(0, 7)}</span>)}
          </>)}
      </Linha>

      <Linha icone="🧗" titulo="Onde o estudo trava" means={d.means}>
        {!d.computed ? <NaoCalculado refresh={d.refresh} />
         : !d.measured ? <span className="text-neutral-500">
             nada observado sobre esta página</span>
         : <>
             <b>{d.score?.toFixed(2)}</b> · {d.reason}
             <span className="text-neutral-400">
               {" "}({Object.entries(d.components)
                       .filter(([, n]) => n)
                       .map(([k, n]) => `${k}: ${n}`).join(", ")})</span>
           </>}
      </Linha>

      <Linha icone="🔍" titulo="Sob qual lente" means={l.means}>
        {!l.computed ? <NaoCalculado refresh={l.refresh} />
         : !l.entities.length ? <span className="text-neutral-500">
             nenhuma identidade reconhecida no texto</span>
         : <>
             {l.entities.map(x => (
               <span key={x.canonical} className="inline-block mr-2">
                 {x.ambiguous && "❓ "}
                 {x.sense ? <>{x.base}{" "}
                   <span className="text-neutral-500">({x.sense})</span></>
                          : x.base}
                 <span className="text-neutral-400"> ×{x.mentions}</span>
               </span>))}
             {l.total > l.entities.length && (
               <span className="text-neutral-400">
                 {" "}+{l.total - l.entities.length}</span>)}
           </>}
      </Linha>

      <Linha icone="⚔️" titulo="Onde diverge" means={v.means}>
        {!v.computed ? <NaoCalculado refresh={v.refresh} />
         : !v.conflicts.length ? <span className="text-neutral-500">
             nenhum desacordo detectado</span>
         : v.conflicts.map((c, i) => (
             <div key={`${c.rule}-${c.identifier}-${i}`}>
               <span className="font-mono">{c.identifier || c.rule}</span>
               {" ↔ "}
               <span className="font-mono">{c.with_pages.join(", ")}</span>
             </div>))}
      </Linha>

      <Linha icone="🎯" titulo="Onde se aplica" means={medicao.note}>
        {!casos.length ? <span className="text-neutral-500">
            nenhum caso declarado — a aresta é ATO humano, não inferência
          </span>
         : casos.map(c => (
             <div key={`${c.page}-${c.rel}`}>
               <span className="font-mono">{c.page}</span>{" "}
               <span className="text-neutral-500">
                 ({c.rel}, declaração {c.via})</span>
             </div>))}
        {medicao.ambiguous_fraction !== null && (
          <div className="text-neutral-500">
            custo do nível de página:{" "}
            {(medicao.ambiguous_fraction * 100).toFixed(0)}% dos alvos com
            2+ sujeitos fortes</div>)}
      </Linha>

      {/* Ressalvas e não-medidos são CONTEÚDO, não rodapé: a pergunta
          "quanto ganho?" é a que o leitor traz, e a ficha a recusa aqui,
          na tela, não numa página que ninguém abre. */}
      <Linha icone="🚧" titulo="O que esta ficha NÃO mede">
        <ul className="list-disc pl-4">
          {sheet.not_measured.map(t => <li key={t}>{t}</li>)}
        </ul>
      </Linha>

      <details className="text-xs border-t pt-2">
        <summary className="cursor-pointer">
          Ressalvas dos mecanismos ({sheet.guarantees.length})</summary>
        {sheet.guarantees.map(g => (
          <div key={g.mechanism_id} className="mt-1">
            <span className="font-mono">{g.mechanism_id}</span>{" "}
            <span className="text-neutral-500">
              (garantia {g.guarantee})</span>
            <ul className="list-disc pl-4 text-neutral-600">
              {g.misinterpretations.map(m => <li key={m}>{m}</li>)}
            </ul>
          </div>))}
      </details>
    </div>
  );
}

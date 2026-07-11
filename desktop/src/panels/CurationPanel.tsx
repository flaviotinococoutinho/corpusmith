// 🗂 Curadoria (Fase 5): gerenciador de tags · dicionário do domínio ·
// configuração viva dos métodos de captura/organização · comportamento da
// IA (pesos Hedge, flags) · exportador inteligente.
import { useEffect, useState } from "react";
import { client } from "../lib/client";

function Card({ title, children }: { title: string; children: any }) {
  return (
    <section className="border rounded p-3">
      <h3 className="font-medium text-sm mb-2">{title}</h3>
      {children}
    </section>
  );
}

export function CurationPanel() {
  const [tags, setTags] = useState<[string, number][]>([]);
  const [dict, setDict] = useState<any>(null);
  const [config, setConfig] = useState<any>(null);
  const [behavior, setBehavior] = useState<any>(null);
  const [notice, setNotice] = useState("");
  const [renaming, setRenaming] = useState<{ from: string; to: string } | null>(null);
  const [exp, setExp] = useState({ format: "zip", include_local: false, tag: "" });

  const load = () => {
    client.tags().then(r => setTags(r.tags));
    client.dictionary().then(setDict);
    client.configGet().then(setConfig);
    client.behavior().then(setBehavior);
  };
  useEffect(() => { client.connect().then(load); }, []);

  const tune = (section: string, key: string, value: any) =>
    client.configSet({ [section]: { [key]: value } })
      .then(c => { setConfig(c); setNotice(`⚙️ ${section}.${key} = ${value}`); });

  if (!config) return <div className="p-6">Carregando curadoria…</div>;
  return (
    <div className="p-4 grid grid-cols-2 gap-3 text-sm">
      {notice && <p className="col-span-2 text-xs border rounded p-2
        bg-neutral-50">{notice}</p>}

      <Card title="🏷 Tags">
        {tags.map(([t, n]) => (
          <div key={t} className="flex items-center gap-2 text-xs mb-1">
            <span className="flex-1">`{t}` × {n}</span>
            <button className="border rounded px-1"
                    onClick={() => setRenaming({ from: t, to: t })}>
              renomear/fundir</button>
            <button className="border rounded px-1"
                    onClick={() => client.tagOp(t).then(() => {
                      setNotice(`🏷 removida: ${t}`); load(); })}>
              remover</button>
          </div>))}
        {!tags.length && <span className="text-xs text-neutral-400">
          sem tags no bundle</span>}
        {renaming && (
          <div className="flex gap-2 mt-2 text-xs">
            <input className="border rounded p-1 flex-1" value={renaming.to}
                   onChange={e => setRenaming({ ...renaming, to: e.target.value })} />
            <button className="border rounded px-2"
                    onClick={() => client.tagOp(renaming.from, renaming.to)
                      .then(r => { setNotice(`🏷 ${renaming.from} → ${
                        renaming.to} (${r.pages} pág)`); setRenaming(null);
                        load(); })}>aplicar</button>
            <button onClick={() => setRenaming(null)}>✕</button>
          </div>)}
      </Card>

      <Card title="📖 Dicionário do domínio">
        {dict && (
          <div className="text-xs space-y-2">
            <div><b>Tipos</b> (● recomendado):{" "}
              {dict.types.filter((t: any) => t.uses > 0).map((t: any) =>
                `${t.recommended ? "●" : "○"} ${t.type}×${t.uses}`)
                .join(" · ") || "—"}</div>
            <div><b>Origens</b> ({dict.origin_prefixes.join(" | ")}):{" "}
              {dict.origins.map(([o, n]: any) => `${o}×${n}`).join(" · ") || "—"}</div>
            <div><b>Confiança</b>: {dict.confidence_scale.join(" → ")}</div>
            <div><b>Vereditos</b>: {dict.verdicts.join(" · ")}
              {" "}· <b>Privacidade</b>: {dict.privacy_values.join(" · ")}</div>
            <div><b>Autoridades</b>: {dict.authorities.map(
              ([a, n]: any) => `${a}×${n}`).join(" · ")}
              {" "}({dict.gazetteer_terms} termos no gazetteer)</div>
          </div>)}
      </Card>

      <Card title="⚙️ Métodos de captura e organização (a quente)">
        <div className="text-xs space-y-2">
          {[["flags", "retrieval.descend", "descida hierárquica L0/L1"],
            ["flags", "reconcile.llm_arbiter", "árbitro LLM na zona cinzenta"],
            ["memory", "auto_recycle", "reciclagem automática no fallback"],
            ["policy", "citation_required", "citações obrigatórias (api:*)"]]
            .map(([sec, key, label]) => (
            <label key={key} className="flex items-center gap-2">
              <input type="checkbox" checked={!!config[sec][key]}
                     onChange={e => tune(sec, key, e.target.checked)} />
              {label} <code className="text-neutral-400">{sec}.{key}</code>
            </label>))}
          {[["ask", "abstain_threshold", 0.01],
            ["memory", "max_recall_probability", 0.01],
            ["memory", "min_idle_days", 1],
            ["consolidate", "min_shared", 1],
            ["consolidate", "min_cluster", 1]].map(([sec, key, step]: any) => (
            <label key={key} className="flex items-center gap-2">
              <input type="number" step={step}
                     className="border rounded p-1 w-24"
                     value={config[sec][key]}
                     onChange={e => tune(sec, key, Number(e.target.value))} />
              <code className="text-neutral-400">{sec}.{key}</code>
            </label>))}
        </div>
      </Card>

      <Card title="🎛 Comportamento da IA">
        {behavior && (
          <div className="text-xs space-y-2">
            <div><b>Crédito dos streams (Hedge)</b>:{" "}
              {Object.entries(behavior.stream_weights).map(([s, w]: any) =>
                `${s}=${w.toFixed(2)}`).join(" · ") ||
                "(todos 1.0 — sem desfechos ainda)"}
              <button className="border rounded px-1 ml-2"
                      onClick={() => client.resetStreams().then(() => {
                        setNotice("🎛 crédito dos streams zerado"); load(); })}>
                zerar</button></div>
            <div><b>Adapter procedural</b>:{" "}
              {behavior.active_adapter ?? "nenhum"}</div>
            <div><b>Eval</b>: {behavior.eval.length
              ? behavior.eval.map((e: any) =>
                  `${e.category} ${e.passed}/${e.total}`).join(" · ")
              : "nunca rodado"}</div>
          </div>)}
      </Card>

      <Card title="📦 Exportador inteligente">
        <div className="text-xs space-y-2">
          <div className="flex items-center gap-3">
            <select className="border rounded p-1" value={exp.format}
                    onChange={e => setExp({ ...exp, format: e.target.value })}>
              <option value="zip">zip (bundle OKF)</option>
              <option value="json">json (pipelines)</option>
              <option value="md">md (digest)</option>
            </select>
            <label><input type="checkbox" checked={exp.include_local}
              onChange={e => setExp({ ...exp, include_local: e.target.checked })} />
              {" "}incluir 🔒 local_only</label>
            <select className="border rounded p-1" value={exp.tag}
                    onChange={e => setExp({ ...exp, tag: e.target.value })}>
              <option value="">todas as tags</option>
              {tags.map(([t]) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <p className="text-neutral-400">
            Por default, páginas privadas ficam DE FORA — o manifesto
            registra quantas foram omitidas.</p>
          <button className="border rounded px-2 py-1"
                  onClick={() => window.open(client.exportUrl({
                    format: exp.format,
                    include_local: String(exp.include_local),
                    tag: exp.tag }))}>⬇️ Exportar</button>
        </div>
      </Card>
    </div>
  );
}

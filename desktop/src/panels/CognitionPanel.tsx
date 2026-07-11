// 🧭 Cognição (v0.18): estado declarado (CLT) · melhor investimento dos
// próximos minutos (mochila por densidade de valor) · calibração (Brier)
// · estratégias de explicação (Hedge) · observações metacognitivas com
// gate humano (aceitar aplica pela linhagem de configuração).
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

const SCALE = [1, 2, 3, 4, 5];
const KIND_ICON: Record<string, string> = {
  review: "🔁", question: "❓", contested: "⚔️", stale: "🟡", inbox: "📥",
};

export function CognitionPanel() {
  const [view, setView] = useState<any>(null);
  const [obs, setObs] = useState<any[]>([]);
  const [plan, setPlan] = useState<any>(null);
  const [decl, setDecl] = useState({ load: 3, focus: 3, energy: 3,
                                     time_available_min: 60 });
  const [minutes, setMinutes] = useState(60);
  const [notice, setNotice] = useState("");

  const load = () => {
    client.cognition().then(setView);
    client.observations().then(r => setObs(r.observations));
  };
  useEffect(() => { client.connect().then(load); }, []);

  const planNow = () => client.attention(minutes).then(setPlan);

  if (!view) return <div className="p-6">Carregando cognição…</div>;
  const cal = view.calibration;
  return (
    <div className="p-4 grid grid-cols-2 gap-3 text-sm">
      {notice && <p className="col-span-2 text-xs border rounded p-2
        bg-neutral-50">{notice}</p>}

      <Card title="🧠 Estado agora (declarado — nunca inferido)">
        <div className="text-xs space-y-2">
          {view.state.declared
            ? <p>carga <b>{view.state.load}/5</b> · foco {view.state.focus}/5
                · energia {view.state.energy}/5
                {view.state.time_available_min &&
                  <> · ⏱ {view.state.time_available_min} min</>}
                <span className="text-neutral-400"> (há {
                  view.state.age_min} min)</span></p>
            : <p className="text-neutral-400">
                nenhum estado vigente — o sistema assume neutro (3/5)</p>}
          {[["carga", "load"], ["foco", "focus"], ["energia", "energy"]]
            .map(([label, key]) => (
            <div key={key} className="flex items-center gap-1">
              <span className="w-14">{label}</span>
              {SCALE.map(v => (
                <button key={v}
                  className={`border rounded w-6 ${
                    (decl as any)[key] === v ? "bg-neutral-200 font-bold" : ""}`}
                  onClick={() => setDecl({ ...decl, [key]: v })}>{v}</button>))}
            </div>))}
          <div className="flex items-center gap-2">
            <span className="w-14">minutos</span>
            <input type="number" className="border rounded p-1 w-20"
                   value={decl.time_available_min}
                   onChange={e => setDecl({ ...decl,
                     time_available_min: Number(e.target.value) })} />
            <button className="border rounded px-2 py-1"
                    onClick={() => client.declareState(decl).then(() => {
                      setNotice("🧠 estado registrado — as respostas se "
                                + "adaptam a ele (TTL 8h)"); load(); })}>
              registrar</button>
          </div>
          <p className="text-neutral-400">Carga alta ⇒ respostas mais curtas,
            menos evidências e plano só com blocos pequenos.</p>
        </div>
      </Card>

      <Card title="⏳ Melhor investimento dos próximos minutos">
        <div className="text-xs space-y-2">
          <div className="flex items-center gap-2">
            <input type="number" className="border rounded p-1 w-20"
                   value={minutes}
                   onChange={e => setMinutes(Number(e.target.value))} />
            <button className="border rounded px-2 py-1" onClick={planNow}>
              planejar</button>
            {plan?.high_load && <span className="text-amber-600">
              carga alta: só blocos pequenos</span>}
          </div>
          {plan?.plan.map((i: any) => (
            <div key={i.kind + i.target} title={i.reason}>
              {KIND_ICON[i.kind]} <span className="font-mono">{i.target}
              </span>{" "}· {i.cost_min} min
              <div className="text-neutral-400 truncate">↳ {i.reason}</div>
            </div>))}
          {plan && !plan.plan.length && <p className="text-neutral-400">
            nada rende dentro desse orçamento — capture algo novo</p>}
        </div>
      </Card>

      <Card title="🎯 Calibração (a confiança bate com o acerto?)">
        <div className="text-xs space-y-1">
          {cal.n
            ? <>
                <p>Brier <b>{cal.brier?.toFixed(3)}</b> (menor = melhor) ·{" "}
                  {cal.overconfidence > 0 ? "excesso" : "falta"} de confiança{" "}
                  <b>{Math.abs(cal.overconfidence * 100).toFixed(0)}%</b>{" "}
                  · n={cal.n}</p>
                {cal.bins.map((b: any) => (
                  <div key={b.lo} className="flex items-center gap-2">
                    <span className="w-20">{Math.round(b.lo * 100)}–{
                      Math.round(b.hi * 100)}%</span>
                    <span className="flex-1 h-3 bg-neutral-100 rounded">
                      <span className="block h-3 rounded bg-neutral-400"
                        style={{ width: `${100 * b.hit_rate}%` }} /></span>
                    <span className="w-24 text-right">acerta {
                      Math.round(b.hit_rate * 100)}% (n={b.n})</span>
                  </div>))}
              </>
            : <p className="text-neutral-400">julgue respostas
                (✅/🚫/✏️) para medir a calibração</p>}
        </div>
      </Card>

      <Card title="🧭 Estratégias de explicação (Hedge)">
        <div className="text-xs space-y-1">
          {Object.entries(view.strategies).map(([s, w]: any) => (
            <div key={s} className="flex items-center gap-2">
              <span className="w-36">{s}
                {view.profile.preferred_strategy === s && " ★"}</span>
              <span className="flex-1 h-3 bg-neutral-100 rounded">
                <span className="block h-3 rounded bg-neutral-400"
                  style={{ width: `${Math.min(100, w * 50)}%` }} /></span>
              <span className="w-10 text-right">{w.toFixed(2)}</span>
            </div>))}
          <div className="pt-1 border-t">
            preferida:{" "}
            <select className="border rounded p-1"
                    value={view.profile.preferred_strategy}
                    onChange={e => client.configSet({ profile:
                      { preferred_strategy: e.target.value } })
                      .then(() => { setNotice(`🧭 preferida = ${
                        e.target.value} (declarado vence o observado)`);
                        load(); })}>
              <option value="auto">auto (Hedge decide)</option>
              {Object.keys(view.strategies).map(s =>
                <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </div>
      </Card>

      <Card title={`🪞 Observações metacognitivas (${obs.length} pendentes)`}>
        <div className="text-xs space-y-2">
          <button className="border rounded px-2 py-1"
                  onClick={() => client.observe().then(r => {
                    setNotice(`🪞 varredura: ${r.created} observação(ões) `
                              + "nova(s)"); load(); })}>
            🔍 varrer padrões agora</button>
          {obs.map(o => (
            <div key={o.id} className="border rounded p-2">
              <p>{o.statement}</p>
              <p className="text-neutral-400">
                {o.kind} · suporte {o.support}
                {o.suggestion && " · aceitar aplica ajuste (com rollback)"}</p>
              <div className="flex gap-2 mt-1">
                {[["accepted", "✅ aceitar"], ["rejected", "🚫 rejeitar"],
                  ["suspended", "⏸ depois"]].map(([action, label]) => (
                  <button key={action} className="border rounded px-1"
                    onClick={() => client.reviewObservation(o.id, action)
                      .then(r => { setNotice(r.applied
                        ? `✅ aplicado pela linhagem (geração #${
                            r.applied.history_id})`
                        : `observação ${action}`); load(); })}>
                    {label}</button>))}
              </div>
            </div>))}
          {!obs.length && <p className="text-neutral-400">
            nenhuma hipótese pendente — o sistema só propõe com suporte
            mínimo (n≥{5}) e você sempre dá a palavra final</p>}
        </div>
      </Card>
    </div>
  );
}

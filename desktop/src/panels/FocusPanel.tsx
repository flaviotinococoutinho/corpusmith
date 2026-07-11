// 🎯 Foco (v0.19): a jornada cognitiva — objetivo → mapa focal (projeção
// explicada) → sessão com recuperação ativa (confiança ANTES) → feedback
// → suspensão/retomada (cápsula) → revisões espaçadas.
// Progressive disclosure: uma etapa por vez; wayfinding pelos _links.
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

const DIMS = ["conceptual", "technical", "mathematical", "practical",
              "historical", "critical", "transfer"];
const MODES = ["understand", "apply", "retain", "critique", "transfer"];
const EXERCISES = ["recall", "explain", "apply", "compare", "critique",
                   "transfer"];
const EPI_BADGE: Record<string, string> = {
  human: "👤 humano", extracted: "● extraído", inferred: "◐ inferido",
  ambiguous: "○ ambíguo",
};

export function FocusPanel() {
  const [goals, setGoals] = useState<any[]>([]);
  const [form, setForm] = useState<any>({ title: "", root: "", priority: 3,
    horizon_days: 30, time_available_min: 60, depth: { conceptual: 2 } });
  const [pages, setPages] = useState<string[]>([]);
  const [proj, setProj] = useState<any>(null);
  const [session, setSession] = useState<any>(null);
  const [attempt, setAttempt] = useState<any>({ item: "", exercise: "explain",
    answer: "", confidence: 0.6, revealed: false });
  const [reviews, setReviews] = useState<any[]>([]);
  const [notice, setNotice] = useState("");

  const load = () => {
    client.goals().then(r => setGoals(r.goals)).catch(() => {});
    client.reviewsDue().then(r => setReviews(r.reviews)).catch(() => {});
    client.pages().then(r =>
      setPages(r.pages.map((p: any) => p.path))).catch(() => {});
  };
  useEffect(() => { client.connect().then(load); }, []);

  const project = (goal_id: string, extra: any = {}) =>
    client.project({ goal_id, ...extra })
      .then(p => { setProj(p); setNotice(`🗺 projeção ${p.id}: ${
        p.working_set.items.length} nó(s), ${
        p.working_set.excluded_by_gate.length} barrado(s) por gate`); });

  const submit = (result: string) => {
    client.submitAttempt(session.id, {
      item: attempt.item, exercise: attempt.exercise,
      answer: attempt.answer, confidence_before: attempt.confidence,
      result,
    }).then(r => {
      setNotice(`🎯 ${attempt.exercise}: ${result} → acessibilidade ${
        r.accessibility.level} · revisão em ${r.review.interval_days}d (${
        r.review.reason})`);
      setAttempt({ ...attempt, answer: "", revealed: false });
      client.getSession(session.id).then(setSession);
      load();
    }).catch(() => setNotice("🚫 tentativa recusada"));
  };

  return (
    <div className="p-4 grid grid-cols-2 gap-3 text-sm">
      {notice && <p className="col-span-2 text-xs border rounded p-2
        bg-neutral-50">{notice}</p>}

      <Card title="🎯 Objetivo de foco">
        <div className="text-xs space-y-2">
          <input className="border rounded p-1 w-full" placeholder="título"
                 value={form.title}
                 onChange={e => setForm({ ...form, title: e.target.value })} />
          <select className="border rounded p-1 w-full" value={form.root}
                  onChange={e => setForm({ ...form, root: e.target.value })}>
            <option value="">conceito raiz…</option>
            {pages.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
          <div className="flex gap-2 flex-wrap items-center">
            prioridade <input type="number" min={1} max={5}
              className="border rounded p-1 w-14" value={form.priority}
              onChange={e => setForm({ ...form, priority: +e.target.value })} />
            horizonte(d) <input type="number"
              className="border rounded p-1 w-16" value={form.horizon_days}
              onChange={e => setForm({ ...form,
                horizon_days: +e.target.value })} />
            min <input type="number" className="border rounded p-1 w-16"
              value={form.time_available_min}
              onChange={e => setForm({ ...form,
                time_available_min: +e.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-1">
            {DIMS.map(d => (
              <label key={d} className="flex items-center gap-1">
                <span className="w-24">{d}</span>
                <input type="number" min={0} max={3}
                  className="border rounded p-1 w-12"
                  value={form.depth[d] ?? 0}
                  onChange={e => setForm({ ...form, depth:
                    { ...form.depth, [d]: +e.target.value } })} />
              </label>))}
          </div>
          <button className="border rounded px-2 py-1"
            disabled={!form.title || !form.root}
            onClick={() => client.createGoal({
              title: form.title, root: form.root, priority: form.priority,
              horizon_days: form.horizon_days,
              time_available_min: form.time_available_min,
              depth_desired: form.depth,
            }).then(g => { setNotice(`🎯 objetivo ${g.id} criado`); load();
              project(g.id); })
              .catch(() => setNotice("🚫 objetivo recusado (raiz existe?)"))}>
            criar objetivo</button>
          <div className="pt-1 border-t space-y-1">
            {goals.map(g => (
              <div key={g.id} className="flex items-center gap-2">
                <span className="flex-1 truncate">{g.title}
                  <span className="text-neutral-400"> · {g.root}</span></span>
                <button className="border rounded px-1"
                        onClick={() => project(g.id)}>🗺 projetar</button>
              </div>))}
          </div>
        </div>
      </Card>

      <Card title="🗺 Mapa focal (projeção explicada)">
        {!proj ? <p className="text-xs text-neutral-400">
          crie/projete um objetivo — cada nó chega com decomposição do
          score e o porquê</p> :
        <div className="text-xs space-y-2">
          <p className="text-neutral-400">política v{
            proj.working_set.policy_version} · {proj.working_set.eligible
            } elegíveis de {proj.working_set.considered} · custo {
            proj.working_set.cost_min} min · trace {proj.trace_id}</p>
          {proj.working_set.items.map((i: any) => (
            <div key={i.page} className="border rounded p-2">
              <div className="flex items-center gap-2">
                <span className="font-mono flex-1 truncate">{i.page}</span>
                <span title="confiança epistemológica (da memória)">
                  {EPI_BADGE[i.epistemic.confidence] ?? i.epistemic.confidence}
                </span>
                {i.epistemic.stale && <span>🟡</span>}
                {i.epistemic.contested && <span>⚔️</span>}
                <span className="tabular-nums" title="prioridade cognitiva
(da experiência — não é confiança)">{i.score.toFixed(2)}</span>
              </div>
              <span className="block h-2 bg-neutral-100 rounded mt-1">
                <span className="block h-2 rounded bg-neutral-400"
                      style={{ width: `${Math.min(100, i.score * 100)}%` }} />
              </span>
              <div className="text-neutral-500 mt-1">
                ↳ {i.reasons.join(" · ")}</div>
              <div className="flex gap-1 mt-1">
                <button className="border rounded px-1" title="fixar"
                  onClick={() => project(proj.goal_id, { pin: i.page })}>📌</button>
                <button className="border rounded px-1" title="excluir deste objetivo"
                  onClick={() => project(proj.goal_id, { exclude: i.page })}>🚫</button>
              </div>
            </div>))}
          {proj.working_set.open_questions.map((q: any) => (
            <div key={q.page} className="font-mono truncate">❓ {q.page}</div>))}
          <details><summary className="cursor-pointer">
            barrados por gate ({proj.working_set.excluded_by_gate.length}) ·
            cortados por orçamento ({proj.working_set.trimmed_by_budget.length})
          </summary>
            {proj.working_set.excluded_by_gate.map((e: any) => (
              <div key={e.page} className="font-mono truncate text-neutral-400">
                ⛔ {e.page} — {e.refused.join("; ")}</div>))}
            {proj.working_set.trimmed_by_budget.map((t: any) => (
              <div key={t.page} className="font-mono truncate text-neutral-400">
                ✂️ {t.page} — {t.why}</div>))}
          </details>
          <div className="flex gap-2 items-center pt-1 border-t">
            {MODES.map(m => (
              <button key={m} className="border rounded px-2 py-1"
                onClick={() => client.startSession(proj.id, m)
                  .then(s => { setSession(s); setAttempt({ ...attempt,
                    item: s.current_item ?? "" });
                    setNotice(`▶ sessão ${s.id} (${m})`); })}>
                ▶ {m}</button>))}
          </div>
        </div>}
      </Card>

      <Card title="🧪 Sessão (recuperação ativa)">
        {!session ? <p className="text-xs text-neutral-400">
          inicie uma sessão a partir do mapa focal</p> :
        <div className="text-xs space-y-2">
          <p>sessão <span className="font-mono">{session.id}</span> ·{" "}
            {session.state} · modo {session.mode} · {session.steps.length}{" "}
            passo(s)
            {session.open_questions.length > 0 &&
              <> · ❓ {session.open_questions.length} aberta(s)</>}</p>
          {session.state === "suspended" && session.capsule && (
            <div className="border rounded p-2 bg-neutral-50">
              💊 <b>cápsula</b>: {session.capsule.reason || "—"} · próximo:{" "}
              {session.capsule.next_step || "—"}
              <button className="border rounded px-2 ml-2"
                onClick={() => client.resumeSession(session.id)
                  .then(s => { setSession(s);
                    setNotice(`▶️ retomada: ${s.capsule.next_step ?? ""}`); })}>
                ▶️ retomar</button>
            </div>)}
          {session.state === "active" && <>
            <select className="border rounded p-1 w-full" value={attempt.item}
              onChange={e => setAttempt({ ...attempt, item: e.target.value })}>
              {session.working_set.items.map((i: any) =>
                <option key={i.page} value={i.page}>{i.page}</option>)}
            </select>
            <div className="flex gap-2 items-center">
              {EXERCISES.map(x => (
                <button key={x} className={`border rounded px-1 ${
                    attempt.exercise === x ? "bg-neutral-200" : ""}`}
                  onClick={() => setAttempt({ ...attempt, exercise: x })}>
                  {x}</button>))}
            </div>
            <textarea className="border rounded p-1 w-full" rows={3}
              placeholder="responda SEM consultar (retrieval practice)…"
              value={attempt.answer}
              onChange={e => setAttempt({ ...attempt, answer: e.target.value })} />
            <label className="flex items-center gap-2">
              confiança ANTES de conferir: {Math.round(attempt.confidence * 100)}%
              <input type="range" min={0} max={100}
                value={attempt.confidence * 100}
                onChange={e => setAttempt({ ...attempt,
                  confidence: +e.target.value / 100 })} />
            </label>
            {!attempt.revealed
              ? <button className="border rounded px-2 py-1"
                  onClick={() => setAttempt({ ...attempt, revealed: true })}>
                  👁 conferir na fonte</button>
              : <div className="flex gap-2">
                  {["success", "partial", "failure"].map(r => (
                    <button key={r} className="border rounded px-2 py-1"
                            onClick={() => submit(r)}>
                      {{ success: "✅ acertei", partial: "〰 parcial",
                         failure: "❌ errei" }[r]}</button>))}
                </div>}
            <div className="flex gap-1 flex-wrap pt-1 border-t">
              {["useful", "too_shallow", "too_deep", "confusing",
                "missing_example"].map(v => (
                <button key={v} className="border rounded px-1"
                  onClick={() => client.sessionFeedback(session.id,
                    { scope: "concept", target: attempt.item, verdict: v })
                    .then(() => setNotice(`🗳 feedback: ${v}`))}>
                  {v}</button>))}
            </div>
            <div className="flex gap-2">
              <button className="border rounded px-2 py-1"
                onClick={() => client.suspendSession(session.id, {
                  reason: "pausa", next_step: attempt.item
                    ? `continuar em ${attempt.item}` : null })
                  .then(r => { setNotice("💊 cápsula criada");
                    client.getSession(session.id).then(setSession); })}>
                ⏸ suspender</button>
              <button className="border rounded px-2 py-1"
                onClick={() => client.completeSession(session.id)
                  .then(s => { setSession(s); setNotice("🏁 concluída"); })}>
                🏁 concluir</button>
            </div>
          </>}
        </div>}
      </Card>

      <Card title={`🔁 Revisões devidas (${reviews.length})`}>
        <div className="text-xs space-y-1">
          {reviews.map(r => (
            <div key={r.id} className="flex items-center gap-2">
              <span className="font-mono flex-1 truncate">{r.item}</span>
              <span className="text-neutral-400" title={r.reason}>
                {r.level ?? "none"}·streak {r.streak ?? 0}</span>
              <button className="border rounded px-1"
                onClick={() => client.completeReview(r.id)
                  .then(() => { setNotice("🔁 revisão concluída"); load(); })}>
                ✔</button>
            </div>))}
          {!reviews.length && <span className="text-neutral-400">
            nada vencido — a agenda espaçada (spaced-v1) traz de volta no
            momento certo; falha confiante volta primeiro</span>}
        </div>
      </Card>
    </div>
  );
}

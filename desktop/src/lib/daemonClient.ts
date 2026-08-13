// Cliente do daemon (Parte V §9.1 + extensões do cockpit v0.7 §7.1).
// Handshake via preload (Electron); auth por header — exceto EventSource,
// que não envia headers e usa ?auth= (por isso a API aceita os dois).

export interface Handshake {
  host?: string;
  port: number;
  token: string;
}

export interface SidecarFailure {
  reason: "no-venv" | "spawn-failed" | "exited";
  detail: string;
}

// ---------------------------------------------------- F1-PR6: tipos do payload
// Até aqui `nextActions()` devolvia `any` e o painel usava `any`, então
// `tsc --noEmit` (o único gate de frontend do projeto) não provava NADA
// sobre este shape. Com os tipos declarados, renomear um campo no backend
// sem atualizar aqui QUEBRA o typecheck — que é a única garantia honesta
// disponível: não há runner de teste de UI no desktop.
export interface Finding {
  severity: "error" | "warn" | "info";
  rule: string;
  path: string;
  message: string;
  okf_conformance?: boolean;
  meta?: Record<string, unknown>;
}

// ------------------------------------------------------------- F-UI: doctor
// Os invariantes INV-001..006 eram o único verificador de integridade do
// produto e só existiam no terminal. O app pintava `🩺 stacks!` em vermelho e
// não oferecia ato nenhum — embora `REPAIRABLE` resolva três dos seis com um
// POST. Tipar o relatório aqui é o que faz `tsc` cobrar o painel quando o
// backend renomear um campo.
export interface DoctorFinding {
  inv: string;
  severity: "error" | "warn";
  message: string;
  hint?: string;
}

export interface DoctorReport {
  ok: boolean;
  findings: DoctorFinding[];
  repaired: { mode?: string; pages?: number } | null;
  counts: { error: number; warn: number };
  derivations?: Record<string, { state: string; reason?: string }>;
}

// F3-PR1 (RFC-003): o promote pode devolver COLLISION — nada foi escrito e
// a decisão é do humano. Sem o tipo, o dialog lia `pages?.[0] ?? "ok"` e
// mostrava "✅ criado: ok" para uma colisão: a mentira do log, na tela.
export interface PromoteBody {
  kind: string; title: string; content: string; source?: string;
  privacy?: string; description?: string; tags?: string[];
  resolution?: "update" | "new_slug";
  target?: string;
}

export interface PromoteResult {
  op: "ADD" | "UPDATE" | "COLLISION";
  kind: string;
  pages?: string[];
  commit?: string;
  // presentes só em COLLISION
  target?: string;
  score?: number;
  reason?: string;
  options?: string[];
}

/** Ato de curadoria já aplicado (`GET /curation/history`).
 *  `undone_by` preenchido = já desfeito; `undoes` = este É um desfazer. */
export interface CurationAct {
  id: number;
  act: string;
  params: Record<string, unknown>;
  commit_sha: string | null;
  pages: string[];
  created_at: number;
  undoes: number | null;
  undone_by: number | null;
}

// F2-PR3+4: o grafo declara DE QUANDO é a intermediação e QUEM a mediu.
// `computed: false` = ainda não medida — a interface serve grau em vez de
// inventar influência, e o badge oferece o job que a mede.
export interface GraphCentrality {
  computed: boolean;
  backend: "none" | "python" | "rust";
  computed_at: number | null;
  bundle_head: string | null;
  pages: number;
}

export interface GraphFreshness {
  partition_backend: "none" | "leiden" | "components";
  centrality_backend: "none" | "python" | "rust";
  computed_at: number | null;
  bundle_head: string | null;
}

export interface GraphData {
  nodes: Array<Record<string, unknown> & {
    page: string; degree: number; betweenness: number; community: number;
  }>;
  edges: Array<{ src: string; dst: string; confidence: string;
                 bridge?: boolean }>;
  centrality: GraphCentrality;
  freshness: GraphFreshness;
  total_nodes: number;
  total_edges: number;
  truncated: boolean;
}

export interface PageDetail {
  path: string;
  body: string;                  // o `prefill` do ato de edição lê DAQUI
  meta: Record<string, unknown>;
  git: string[];
  related?: unknown[];
}

export interface CurationActOffer {
  act: string;
  params: Record<string, string>;
  needs: string[];
  label: string;
  options?: Record<string, string[]>;
  // F1-PR3: campos longos (o corpo da página) e de onde vem o valor
  // inicial. Quem declara é a oferta, no backend — a alternativa era o
  // .tsx conhecer o nome do ato, e é justamente isso que os testes de
  // contrato existem para evitar.
  multiline?: string[];
  prefill?: Record<string, { page: string; field: "body" }>;
}

export interface CurationPreview {
  act: string;
  pages: string[];
  diffs: Record<string, string>;
  findings: Finding[];
  dependents: string[];
  note: string;
  blocked: boolean;
}

export interface CurationActResult {
  dry_run: boolean;
  applied: boolean;
  preview: CurationPreview;
  id?: number;
  commit?: string;
  undone_act?: number;
}

export interface NextActionItem {
  kind: string;
  target: string;
  title: string;
  origin: string;
  value: number;
  cost_min: number;
  reason: string;
  action: { type: string } & Record<string, unknown>;
  acts: CurationActOffer[];
}

export interface NextActionsQueue {
  actions: NextActionItem[];
  total: number;
  truncated: boolean;
  by_origin: Record<string, number>;
}

/** Erro de ato com o CORPO preservado (F1-PR6).
 *
 *  `get`/`post` genéricos descartam `r.json()` em `!r.ok` — um 422 virava
 *  literalmente `Error("/curation/act: 422")`, e os findings nunca
 *  chegavam à tela, desfazendo o ganho do handler que existe justamente
 *  para o produto parar de parecer quebrado.
 *
 *  Atenção aos DOIS shapes de 422: o do Harness traz
 *  `{error: "harness_rejection", findings}`; o do Pydantic traz
 *  `{detail: [...]}`. Discriminar por status é errado — tem de ser pelo
 *  corpo. */
export class CurationError extends Error {
  constructor(
    readonly status: number,
    readonly body: any,
  ) {
    super(
      body?.error === "harness_rejection"
        ? body.message ?? "rejeitado pelo Harness"
        : typeof body?.detail === "string"
          ? body.detail
          : `falha ${status}`,
    );
  }
  get harnessFindings(): Finding[] {
    return this.body?.error === "harness_rejection"
      ? (this.body.findings ?? [])
      : [];
  }
}

declare global {
  interface Window {
    corpusmith?: {
      handshake(): Promise<Handshake | null>;
      // F0: opcional — versões antigas do preload não expõem
      sidecarFailure?(): Promise<SidecarFailure | null>;
    };
  }
}

export class DaemonClient {
  private info: Handshake | null = null;
  private connecting: Promise<void> | null = null;

  connect(timeoutMs = 20_000): Promise<void> {
    this.connecting ??= (async () => {
      const t0 = Date.now();
      for (;;) {
        this.info = (await window.corpusmith?.handshake()) ?? null;
        if (this.info) {
          try {
            const r = await fetch(this.base() + "/health");
            if (r.ok) return;
          } catch { /* daemon ainda subindo */ }
        }
        if (Date.now() - t0 > timeoutMs) {
          this.connecting = null;
          throw new Error("daemon não respondeu (modo read-only)");
        }
        await new Promise(res => setTimeout(res, 500));
      }
    })();
    return this.connecting;
  }

  /** F0: descarta handshake e promessa em cache para um retry REAL.
   *  Sem isto, um daemon que subiu depois da falha (ou que reiniciou com
   *  token novo) continuaria inalcançável até o app ser reaberto. */
  reset(): void {
    this.info = null;
    this.connecting = null;
  }

  base(): string {
    if (!this.info) throw new Error("connect() antes de usar o cliente");
    return `http://${this.info.host ?? "127.0.0.1"}:${this.info.port}`;
  }

  headers(): Record<string, string> {
    return { "x-corpusmith-auth": this.info?.token ?? "" };
  }

  private async get<T = any>(p: string): Promise<T> {
    await this.connect();
    return fetch(this.base() + p, { headers: this.headers() })
      .then(r => { if (!r.ok) throw new Error(`${p}: ${r.status}`); return r.json(); });
  }

  // ------------------------------------------------ base (Parte V §9.1)
  status = () => this.get<any>("/status");
  jobs = () => this.get<any>("/jobs");
  enqueue = (type: string, payload: unknown = {}) =>
    this.post("/jobs", { type, payload });

  eventTypes = () => this.get<{ types: string[] }>("/events/types");

  /** Ponte SSE — F-UI.
   *
   *  O `EventSource` só entrega um evento NOMEADO a quem tenha feito
   *  `addEventListener` com aquele nome exato; `onmessage` recebe apenas os
   *  sem nome. Este método registrava CINCO nomes fixos e o servidor emite
   *  cinquenta e três: `page.stage`, `pipeline.*`, `consolidate.done` e
   *  `source.ingested` saíam do backend e morriam aqui. O Stepper do Inbox e
   *  a barra de progresso por job estavam escritos, tipados — e nunca foram
   *  alimentados uma única vez.
   *
   *  Uma lista fixa maior repetiria o erro na próxima adição. O cliente
   *  PERGUNTA ao servidor o que ele emite (`/events/types`), e o servidor não
   *  pode responder desatualizado porque `EventBus.emit` recusa tipo fora do
   *  vocabulário declarado.
   *
   *  A conexão abre ANTES da lista chegar, de propósito: perder eventos
   *  enquanto se espera por um GET seria trocar um buraco por outro. Até a
   *  resposta, valem os nomes de sempre. */
  events(onEvent: (e: any) => void): EventSource {
    const es = new EventSource(
      `${this.base()}/events?auth=${encodeURIComponent(this.info?.token ?? "")}`);
    const registrados = new Set<string>();
    const escutar = (t: string) => {
      if (registrados.has(t)) return;
      registrados.add(t);
      es.addEventListener(t, ev =>
        onEvent(JSON.parse((ev as MessageEvent).data)));
    };
    es.onmessage = ev => onEvent(JSON.parse(ev.data));
    for (const t of ["job.started", "job.done", "job.failed",
                     "memory.promoted", "compile.done"]) escutar(t);
    this.eventTypes()
      .then(({ types }) => types.forEach(escutar))
      .catch(() => { /* daemon antigo: seguem os cinco de sempre */ });
    return es;
  }

  cancelJob = (id: string) => this.post<any>(`/jobs/${id}/cancel`, {});
  retryJob = (id: string) => this.post<any>(`/jobs/${id}/retry`, {});

  // ---------------------------------------------- doctor (F0, v1.8.1)
  doctor = () => this.get<DoctorReport>("/system/doctor");
  doctorRepair = () => this.post<DoctorReport>("/system/doctor/repair", {});

  // ------------------------------------------- histórico de atos (F-UI)
  // `GET /curation/history` existe desde o F1-PR1 e nunca teve método aqui:
  // sem o `act_id`, o `undo` — completo no backend, com 409 nomeado — era
  // inalcançável pelo app. Aplicar era irreversível pela interface.
  curationHistory = (limit = 30) =>
    this.get<{ acts: CurationAct[] }>(`/curation/history?limit=${limit}`);

  // ------------------------------------------- cockpit (v0.7 §7.1)
  dashboard = () => this.get<any>("/cockpit/dashboard");
  inbox = () => this.get<any>("/cockpit/inbox");
  pages = () => this.get<any>("/cockpit/pages");
  page = (path: string) =>
    this.get<PageDetail>(`/cockpit/page?path=${encodeURIComponent(path)}`);
  markStale = (path: string) => this.post("/cockpit/page/stale", { path });
  promote = (body: PromoteBody) => this.post<PromoteResult>("/cockpit/promote", body);
  memory = () => this.get<any>("/cockpit/memory");
  quality = () => this.get<any>("/cockpit/quality");
  review = () => this.get<any>("/cockpit/review");
  ledgerToday = () => this.get<any>("/cockpit/ledger/today");
  ask = (query: string, deep = false, local = false) =>
    this.post<any>("/ask", { query, deep, local_only: local });
  // ------------------------------------------------ v0.8 (§11.2)
  outcome = (body: { ask_id?: string; verdict: string; note?: string;
                     pages: string[] }) =>
    this.post("/cockpit/outcome", body);
  evalRes = () => this.get<any>("/cockpit/eval");
  authorities = () => this.get<any>("/cockpit/authorities");
  reflectCand = () => this.get<any>("/cockpit/reflect");
  // ------------------------------------------------ v0.11 (ingestão densa)
  ingest = (body: { filename: string; content?: string;
                    content_base64?: string; subdir?: string;
                    compile?: boolean }) =>
    this.post<any>("/cockpit/ingest", body);
  stats = () => this.get<any>("/cockpit/stats");
  // ------------------------------------------------ v0.12 (base fria)
  freeze = (path: string, force = false) =>
    this.post<any>("/cockpit/freeze", { path, force });
  recycle = (path: string) => this.post<any>("/cockpit/recycle", { path });
  cold = () => this.get<any>("/cockpit/cold");
  // ------------------------------------------------ Fase 5 (v0.15)
  graph = (limit = 0) =>
    this.get<GraphData>(`/cockpit/graph${limit ? `?limit=${limit}` : ""}`);
  insights = () => this.get<any>("/cockpit/insights");
  gaps = () => this.get<any>("/cockpit/gaps");   // v1.1: lacunas estruturais
  nextActions = (limit = 40) =>                  // R3 (v1.8): fila única
    this.get<NextActionsQueue>(`/cockpit/next-actions?limit=${limit}`);

  /** Veredito humano sobre PADRÃO COMPUTADO (F3-PR2, P-3).
   *
   *  Ponte e contradição não são páginas: são relações que o job recomputa.
   *  Dizer "esta não vale" precisa de um lugar que sobreviva à recomputação —
   *  senão o item rejeitado volta na execução seguinte, e a fila ensina o
   *  usuário a ignorá-la. `until` adia com prazo; sem ele, some até alguém
   *  reabrir. Nada é DELETADO. */
  patternVerdict = (body: { kind: string; pages: string[];
                            status: "accepted" | "rejected" | "deferred";
                            until?: number; note?: string }) =>
    this.post<{ kind: string; key: string; status: string }>(
      "/cockpit/next-actions/verdict", body);

  /** Ato de curadoria (F1-PR6). Método PRÓPRIO em vez de usar `post()`:
   *  precisa preservar o corpo do erro. Aditivo — não toca a assinatura
   *  de `post()`/`get()`, conforme a regra de colisão do docs/15 §6. */
  curationAct = async (act: string, params: Record<string, string>,
                       dryRun: boolean): Promise<CurationActResult> => {
    await this.connect();
    const r = await fetch(this.base() + "/curation/act", {
      method: "POST",
      headers: { ...this.headers(), "Content-Type": "application/json" },
      body: JSON.stringify({ act, params, dry_run: dryRun }),
    });
    if (!r.ok) throw new CurationError(r.status, await r.json().catch(() => null));
    return r.json();
  };
  dictionary = () => this.get<any>("/cockpit/dictionary");
  traces = () => this.get<any>("/cockpit/traces");
  trace = (askId: string) =>
    this.get<any>(`/cockpit/trace?ask_id=${encodeURIComponent(askId)}`);
  tags = () => this.get<any>("/cockpit/tags");
  tagOp = (from: string, to?: string) =>
    this.post<any>("/cockpit/tags", { from, to });
  configGet = () => this.get<any>("/cockpit/config");
  configSet = (body: any) => this.post<any>("/cockpit/config", body);
  // ------------------------------------------------ v0.16 (NFR)
  configHistory = () => this.get<any>("/cockpit/config/history");
  configRollback = () => this.post<any>("/cockpit/config/rollback", {});
  // ------------------------------------------------ v1.6.5 (UX-4)
  configPresets = () => this.get<any>("/cockpit/config/presets");
  applyPreset = (name: string) =>
    this.post<any>("/cockpit/config/preset", { name });
  healthFull = () => this.get<any>("/health/full");
  // ------------------------------------------------ v0.18 (cognição)
  declareState = (body: { load: number; focus?: number; energy?: number;
                          time_available_min?: number; note?: string }) =>
    this.post<any>("/cockpit/state", body);
  cognition = () => this.get<any>("/cockpit/cognition");
  observe = () => this.post<any>("/cockpit/cognition/observe", {});
  observations = (status = "proposed") =>
    this.get<any>(`/cockpit/cognition/observations?status=${status}`);
  reviewObservation = (id: number, action: string) =>
    this.post<any>("/cockpit/cognition/observations/review", { id, action });
  attention = (minutes?: number) =>
    this.get<any>(`/cockpit/attention${minutes ? `?minutes=${minutes}` : ""}`);
  // ------------------------------------------------ v0.19 (foco/jornada)
  createGoal = (body: any) => this.post<any>("/cognitive/goals", body);
  goals = () => this.get<any>("/cognitive/goals");
  project = (body: any) => this.post<any>("/cognitive/projections", body);
  startSession = (projection_id: string, mode = "understand") =>
    this.post<any>("/cognitive/sessions", { projection_id, mode });
  getSession = (id: string) => this.get<any>(`/cognitive/sessions/${id}`);
  submitAttempt = (sid: string, body: any) =>
    this.post<any>(`/cognitive/sessions/${sid}/attempts`, body);
  sessionFeedback = (sid: string, body: any) =>
    this.post<any>(`/cognitive/sessions/${sid}/feedback`, body);
  suspendSession = (sid: string, body: any) =>
    this.post<any>(`/cognitive/sessions/${sid}/suspend`, body);
  resumeSession = (sid: string) =>
    this.post<any>(`/cognitive/sessions/${sid}/resume`, {});
  completeSession = (sid: string) =>
    this.post<any>(`/cognitive/sessions/${sid}/complete`, {});
  reviewsDue = () => this.get<any>("/cognitive/reviews/due");
  goalProgress = (id: string) =>
    this.get<any>(`/cognitive/goals/${id}/progress`);
  reportExperience = (body: any) =>
    this.post<any>("/cognitive/experiences", body);
  exercisePrompt = (exercise: string, title: string) =>
    this.get<any>(`/cognitive/prompt?exercise=${exercise}&title=${
      encodeURIComponent(title)}`);
  cognitiveMetrics = () => this.get<any>("/cognitive/metrics");
  curationProjection = () => this.get<any>("/cognitive/curation");
  completeReview = (id: number) =>
    this.post<any>(`/cognitive/reviews/${id}/complete`, {});
  // ------------------------------------------------ v0.17 (pipelines)
  pipelines = () => this.get<any>("/cockpit/pipelines");
  runPipeline = (name: string) =>
    this.post<any>("/cockpit/pipelines/run", { name });
  pipelineRuns = (name = "") =>
    this.get<any>(`/cockpit/pipelines/runs?name=${encodeURIComponent(name)}`);
  behavior = () => this.get<any>("/cockpit/behavior");
  resetStreams = () => this.post<any>("/cockpit/behavior/reset-streams", {});
  epistemics = () => this.get<any>("/cockpit/epistemics");
  epistemicsMechanism = (id: string) =>
    this.get<any>(`/cockpit/epistemics/${encodeURIComponent(id)}`);
  exportUrl = (params: Record<string, string>) => {
    const q = new URLSearchParams({ ...params,
      auth: (this as any).info?.token ?? "" });
    return `${this.base()}/cockpit/export?${q}`;
  };
  private async post<T = any>(p: string, body: unknown): Promise<T> {
    await this.connect();
    return fetch(this.base() + p, {
      method: "POST",
      headers: { ...this.headers(), "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(r => { if (!r.ok) throw new Error(`${p}: ${r.status}`); return r.json(); });
  }
}

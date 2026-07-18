// Cliente do daemon (Parte V §9.1 + extensões do cockpit v0.7 §7.1).
// Handshake via preload (Electron); auth por header — exceto EventSource,
// que não envia headers e usa ?auth= (por isso a API aceita os dois).

export interface Handshake {
  host?: string;
  port: number;
  token: string;
}

declare global {
  interface Window {
    llmwiki?: { handshake(): Promise<Handshake | null> };
  }
}

export class DaemonClient {
  private info: Handshake | null = null;
  private connecting: Promise<void> | null = null;

  connect(timeoutMs = 20_000): Promise<void> {
    this.connecting ??= (async () => {
      const t0 = Date.now();
      for (;;) {
        this.info = (await window.llmwiki?.handshake()) ?? null;
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

  base(): string {
    if (!this.info) throw new Error("connect() antes de usar o cliente");
    return `http://${this.info.host ?? "127.0.0.1"}:${this.info.port}`;
  }

  headers(): Record<string, string> {
    return { "x-llmwiki-auth": this.info?.token ?? "" };
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

  events(onEvent: (e: any) => void): EventSource {
    const es = new EventSource(
      `${this.base()}/events?auth=${encodeURIComponent(this.info?.token ?? "")}`);
    es.onmessage = ev => onEvent(JSON.parse(ev.data));
    for (const t of ["job.started", "job.done", "job.failed",
                     "memory.promoted", "compile.done"]) {
      es.addEventListener(t, ev =>
        onEvent(JSON.parse((ev as MessageEvent).data)));
    }
    return es;
  }

  // ------------------------------------------- cockpit (v0.7 §7.1)
  dashboard = () => this.get<any>("/cockpit/dashboard");
  inbox = () => this.get<any>("/cockpit/inbox");
  pages = () => this.get<any>("/cockpit/pages");
  page = (path: string) => this.get<any>(`/cockpit/page?path=${encodeURIComponent(path)}`);
  markStale = (path: string) => this.post("/cockpit/page/stale", { path });
  promote = (body: unknown) => this.post("/cockpit/promote", body);
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
  graph = () => this.get<any>("/cockpit/graph");
  insights = () => this.get<any>("/cockpit/insights");
  gaps = () => this.get<any>("/cockpit/gaps");   // v1.1: lacunas estruturais
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

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
  private async post<T = any>(p: string, body: unknown): Promise<T> {
    await this.connect();
    return fetch(this.base() + p, {
      method: "POST",
      headers: { ...this.headers(), "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(r => { if (!r.ok) throw new Error(`${p}: ${r.status}`); return r.json(); });
  }
}

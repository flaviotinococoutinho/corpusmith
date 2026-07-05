// Store de eventos ao vivo (v0.11): UMA assinatura SSE compartilhada por
// todos os painéis + snapshot de /status em polling leve. Mantém a UI
// acoplada ao runtime sem que cada painel abra sua própria conexão.
import { client } from "./client";

export interface LiveEvent {
  seq?: number;
  type: string;
  data: any;
}

export interface DaemonStatus {
  pending_jobs: number;
  budget_left_usd: number;
  spent_today_usd: number;
}

type Listener = (e: LiveEvent) => void;
type StatusListener = (s: DaemonStatus | null) => void;

class LiveStore {
  private listeners = new Set<Listener>();
  private statusListeners = new Set<StatusListener>();
  private es: EventSource | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  status: DaemonStatus | null = null;
  lastEvent: LiveEvent | null = null;
  connected = false;

  start(): void {
    if (this.es || this.timer) return;
    client.connect().then(() => {
      this.connected = true;
      this.es = client.events(e => {
        this.lastEvent = e;
        this.listeners.forEach(l => l(e));
      });
      const poll = () => client.status()
        .then(s => { this.status = s; this.statusListeners.forEach(l => l(s)); })
        .catch(() => { this.connected = false; });
      poll();
      this.timer = setInterval(poll, 5000);
    }).catch(() => { this.connected = false; });
  }

  onEvent(cb: Listener): () => void {
    this.listeners.add(cb);
    return () => this.listeners.delete(cb);
  }

  onStatus(cb: StatusListener): () => void {
    this.statusListeners.add(cb);
    cb(this.status);
    return () => this.statusListeners.delete(cb);
  }
}

export const live = new LiveStore();

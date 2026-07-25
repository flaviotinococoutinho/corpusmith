// Store de eventos ao vivo (v0.11): UMA assinatura SSE compartilhada por
// todos os painéis + snapshot de /status em polling leve. Mantém a UI
// acoplada ao runtime sem que cada painel abra sua própria conexão.
//
// F0 (v1.8.1): a barra de status parou de mentir e o SSE parou de morrer
// calado. Antes daqui, o `.catch` do poll engolia a exceção e NÃO notificava
// os listeners — então a bolinha continuava verde e o orçamento congelado
// depois de o daemon morrer; e o EventSource não tinha `onerror` nem
// reconexão, então um daemon reiniciado (token novo ⇒ 401 eterno) ficava
// inalcançável até o app ser reaberto.
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

const RETRY_BASE_MS = 1_000;
const RETRY_MAX_MS = 30_000;

class LiveStore {
  private listeners = new Set<Listener>();
  private statusListeners = new Set<StatusListener>();
  private es: EventSource | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  private retry: ReturnType<typeof setTimeout> | null = null;
  private attempt = 0;
  status: DaemonStatus | null = null;
  lastEvent: LiveEvent | null = null;
  connected = false;

  start(): void {
    if (this.es || this.timer || this.retry) return;
    client.connect().then(() => {
      this.connected = true;
      this.attempt = 0;
      this.subscribe();
      const poll = () => client.status()
        .then(s => this.publishStatus(s))
        // a falha do poll AGORA propaga: quem desenha o indicador precisa
        // saber que o daemon caiu (antes ficava verde para sempre)
        .catch(() => this.drop());
      poll();
      this.timer = setInterval(poll, 5000);
    }).catch(() => this.drop());
  }

  /** Assina o SSE e se reinscreve com backoff quando a conexão cai. */
  private subscribe(): void {
    this.es = client.events(e => {
      this.lastEvent = e;
      this.listeners.forEach(l => l(e));
    });
    // EventSource reconecta sozinho em erro de rede, mas NÃO quando o token
    // mudou (daemon reiniciado): fechar e refazer o handshake é a única saída.
    this.es.onerror = () => this.drop();
  }

  /** Daemon inalcançável: derruba tudo, avisa os listeners e reagenda. */
  private drop(): void {
    this.connected = false;
    this.publishStatus(null);
    if (this.es) { this.es.close(); this.es = null; }
    if (this.timer) { clearInterval(this.timer); this.timer = null; }
    if (this.retry) return;
    const delay = Math.min(RETRY_BASE_MS * 2 ** this.attempt, RETRY_MAX_MS);
    this.attempt += 1;
    this.retry = setTimeout(() => {
      this.retry = null;
      client.reset();                 // token novo exige handshake novo
      this.start();
    }, delay);
  }

  private publishStatus(s: DaemonStatus | null): void {
    this.status = s;
    this.statusListeners.forEach(l => l(s));
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

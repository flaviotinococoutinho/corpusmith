// A ponte SSE — F-UI.
//
// O achado: `events()` registrava CINCO nomes de evento e o servidor emite
// cinquenta e três. Pela spec do EventSource, um evento nomeado só chega a
// quem fez `addEventListener` com aquele nome exato, e `onmessage` só recebe
// os SEM nome — então `page.stage`, `pipeline.*`, `consolidate.done` e
// `source.ingested` saíam do backend e morriam aqui. O Stepper do Inbox e a
// barra de progresso por job estavam escritos, tipados, e nunca receberam um
// único evento.
//
// Nada disso aparecia no `tsc --noEmit`, que era o gate inteiro do frontend:
// o código estava correto em tipo e errado em comportamento.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DaemonClient } from "./daemonClient";

/** EventSource de mentira que REGISTRA o que foi escutado — a asserção é
 *  sobre os nomes registrados, porque é exatamente aí que o defeito vivia. */
class FakeEventSource {
  static ultima: FakeEventSource | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  readonly escutados: string[] = [];
  private readonly handlers = new Map<string, (e: MessageEvent) => void>();

  constructor(readonly url: string) { FakeEventSource.ultima = this; }

  addEventListener(tipo: string, fn: (e: MessageEvent) => void) {
    this.escutados.push(tipo);
    this.handlers.set(tipo, fn);
  }

  close() { /* nada a fechar num duplo */ }

  /** Simula o servidor mandando um evento NOMEADO, como ele de fato manda. */
  servidorEmite(tipo: string, data: unknown) {
    this.handlers.get(tipo)?.(
      { data: JSON.stringify({ type: tipo, data }) } as MessageEvent);
  }
}

function clientePronto(tipos: string[]) {
  const c = new DaemonClient();
  (c as any).info = { host: "127.0.0.1", port: 1, token: "t" };
  (c as any).connecting = Promise.resolve();
  vi.spyOn(c, "eventTypes").mockResolvedValue({ types: tipos });
  return c;
}

describe("DaemonClient.events", () => {
  beforeEach(() => {
    FakeEventSource.ultima = null;
    vi.stubGlobal("EventSource", FakeEventSource);
  });

  it("escuta TODO tipo que o servidor declara, não uma lista fixa", async () => {
    const c = clientePronto(["page.stage", "pipeline.done", "job.done",
                             "consolidate.done", "source.ingested"]);
    c.events(() => {});
    const es = FakeEventSource.ultima!;
    await vi.waitFor(() =>
      expect(es.escutados).toContain("page.stage"));
    for (const t of ["pipeline.done", "consolidate.done", "source.ingested"])
      expect(es.escutados).toContain(t);
  });

  it("um `page.stage` do servidor CHEGA ao consumidor", async () => {
    // O teste que o defeito original teria reprovado: com os cinco nomes
    // fixos, este evento não tinha handler e o callback nunca era chamado.
    const recebidos: any[] = [];
    const c = clientePronto(["page.stage"]);
    c.events(e => recebidos.push(e));
    const es = FakeEventSource.ultima!;
    await vi.waitFor(() => expect(es.escutados).toContain("page.stage"));
    es.servidorEmite("page.stage", { id: "j1", stage: "write" });
    expect(recebidos).toEqual([
      { type: "page.stage", data: { id: "j1", stage: "write" } }]);
  });

  it("não registra o mesmo tipo duas vezes", async () => {
    // `job.done` está na lista de arranque E na resposta do servidor: sem
    // deduplicar, o consumidor receberia o evento em dobro e a UI contaria
    // dois jobs onde há um.
    const c = clientePronto(["job.done", "page.stage"]);
    c.events(() => {});
    const es = FakeEventSource.ultima!;
    await vi.waitFor(() => expect(es.escutados).toContain("page.stage"));
    expect(es.escutados.filter(t => t === "job.done")).toHaveLength(1);
  });

  it("daemon sem /events/types ainda entrega os cinco de sempre", async () => {
    // Degradar não pode virar apagão: um daemon anterior a esta versão não
    // conhece a rota, e o app precisa continuar mostrando o que já mostrava.
    const c = new DaemonClient();
    (c as any).info = { host: "127.0.0.1", port: 1, token: "t" };
    (c as any).connecting = Promise.resolve();
    vi.spyOn(c, "eventTypes").mockRejectedValue(new Error("404"));
    const recebidos: any[] = [];
    c.events(e => recebidos.push(e));
    const es = FakeEventSource.ultima!;
    expect(es.escutados).toContain("job.done");
    es.servidorEmite("job.done", { id: "j2" });
    expect(recebidos).toHaveLength(1);
  });

  it("a conexão abre ANTES da lista chegar", () => {
    // Esperar o GET para só então abrir o stream perderia os eventos do
    // intervalo — trocaria um buraco por outro, menor e mais difícil de ver.
    const c = clientePronto(["page.stage"]);
    c.events(() => {});
    expect(FakeEventSource.ultima).not.toBeNull();
    expect(FakeEventSource.ultima!.escutados).toContain("job.started");
  });
});

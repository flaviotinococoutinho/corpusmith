// F0 (v1.8.1) — o app deixa de ficar em beco sem saída silencioso.
//
// Até aqui as 9 chamadas de client.connect() nos painéis não tinham .catch,
// e o erro "daemon não respondeu (modo read-only)" que o cliente levanta
// após 20 s não aparecia em lugar nenhum: cada painel ficava em
// "Carregando…" como estado TERMINAL, com uma bolinha de 8 px na StatusBar
// como única pista. Pior: a falha do sidecar do Electron era silenciosa por
// construção (`if (!existsSync(venv)) return;`), então quem não é o autor
// caía exatamente aqui — e não tinha como saber por quê.
//
// Este componente é a resposta única: motivo, o comando para subir, retry,
// e o reparo do doctor quando o daemon responde mas os invariantes não.
import { useEffect, useState } from "react";
import { client } from "../lib/client";
import type { SidecarFailure } from "../lib/daemonClient";

export const DAEMON_CMD = "cd backend && .venv/bin/python -m corpusmith.daemon";

const SIDECAR_HINT: Record<SidecarFailure["reason"], string> = {
  "no-venv": "o ambiente Python do backend não foi encontrado — rode "
             + "`just bootstrap` (ou scripts/install.sh) uma vez",
  "spawn-failed": "o processo do daemon não pôde ser iniciado",
  exited: "o daemon iniciou e saiu com erro",
};

export function DaemonUnavailable(
  { error, onRetry }: { error: unknown; onRetry?: () => void },
) {
  const [tentando, setTentando] = useState(false);
  const [sidecar, setSidecar] = useState<SidecarFailure | null>(null);
  useEffect(() => {
    // o motivo vem do processo principal do Electron: sem ele, o usuário
    // veria só "não respondeu" sem saber que falta o venv
    window.corpusmith?.sidecarFailure?.().then(setSidecar).catch(() => {});
  }, []);
  const motivo = error instanceof Error ? error.message : String(error);
  const retry = () => {
    setTentando(true);
    client.reset();                       // descarta o handshake que falhou
    Promise.resolve(onRetry?.()).finally(() => setTentando(false));
  };
  return (
    <div className="p-6 max-w-2xl space-y-4">
      <div className="border rounded p-4 bg-neutral-50 space-y-3">
        <h2 className="font-medium flex items-center gap-2">
          <span className="inline-block w-2 h-2 rounded-full bg-red-500" />
          O daemon não está respondendo
        </h2>
        <p className="text-sm text-neutral-600">
          O app funciona em modo somente-leitura sem ele, mas nada que
          precise do backend (consulta, curadoria, indicadores) vai carregar.
        </p>
        <p className="text-xs font-mono text-neutral-500 break-all">
          {motivo}
        </p>
        {sidecar && (
          <p className="text-sm text-amber-700 border-l-2 border-amber-400
                        pl-2">
            {SIDECAR_HINT[sidecar.reason]}
            <span className="block text-xs font-mono text-neutral-500 mt-1
                             break-all">{sidecar.detail}</span>
          </p>)}
        <div className="space-y-1">
          <div className="text-xs text-neutral-500">
            Para subir manualmente, na raiz do repositório:
          </div>
          <pre className="text-xs bg-white border rounded p-2 overflow-x-auto">
            {DAEMON_CMD}
          </pre>
        </div>
        <button className="border rounded px-3 py-1 text-sm hover:bg-white
                           disabled:opacity-50"
                disabled={tentando}
                onClick={retry}>
          {tentando ? "tentando…" : "tentar de novo"}
        </button>
      </div>
    </div>
  );
}

// Estado de carregamento que NÃO é terminal: quem usa passa o erro assim
// que ele chega, e o usuário vê o motivo em vez de um texto eterno.
export function PanelState(
  { error, onRetry, children }:
  { error: unknown; onRetry?: () => void; children: React.ReactNode },
) {
  if (error) return <DaemonUnavailable error={error} onRetry={onRetry} />;
  return <>{children}</>;
}

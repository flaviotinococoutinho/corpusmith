// Ciclo de vida do sidecar (Parte II §2.1 + handshake Parte V §2.1).
// Empacotado: resources/backend/llmwiki-server (PyInstaller onedir).
// Dev: usa o daemon já rodando OU sobe via venv do backend.
import { ChildProcess, spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";

export interface Handshake {
  host: string;
  port: number;
  token: string;
  started_at?: number;
}

let child: ChildProcess | null = null;

export function handshakePath(): string {
  const home = process.env.LLMWIKI_HOME ?? path.join(homedir(), "llmwiki");
  return path.join(home, "state", "daemon.json");
}

export function readHandshake(): Handshake | null {
  try {
    return JSON.parse(readFileSync(handshakePath(), "utf-8"));
  } catch {
    return null;
  }
}

export async function daemonAlive(): Promise<boolean> {
  const hs = readHandshake();
  if (!hs) return false;
  try {
    const r = await fetch(`http://${hs.host ?? "127.0.0.1"}:${hs.port}/health`);
    return r.ok;
  } catch {
    return false;
  }
}

/** Motivo pelo qual o sidecar não subiu — `null` = subiu (ou já havia um
 *  daemon externo). F0: antes disto a falha era um `return` MUDO, e o app
 *  ficava com todas as abas em "Carregando…" sem dizer por quê. É a razão
 *  nº 1 pela qual quem não é o autor nunca chega a ver o produto. */
export type SidecarFailure =
  | { reason: "no-venv"; detail: string }
  | { reason: "spawn-failed"; detail: string }
  | { reason: "exited"; detail: string };

let lastFailure: SidecarFailure | null = null;

export function sidecarFailure(): SidecarFailure | null {
  return lastFailure;
}

export async function startSidecar(
  resourcesPath: string,
  onFailure?: (f: SidecarFailure) => void,
): Promise<SidecarFailure | null> {
  const fail = (f: SidecarFailure): SidecarFailure => {
    lastFailure = f;
    onFailure?.(f);
    return f;
  };
  if (child || (await daemonAlive())) {         // daemon externo já sobe o app
    lastFailure = null;
    return null;
  }
  const packaged = path.join(resourcesPath, "backend", "llmwiki-server");
  let bin: string;
  let args: string[];
  if (existsSync(packaged)) {
    bin = packaged;
    args = [];
  } else {
    const venv = path.join(__dirname, "..", "..", "backend", ".venv",
                           "bin", "python");
    if (!existsSync(venv)) {
      return fail({ reason: "no-venv", detail: venv });
    }
    bin = venv;
    args = ["-m", "llmwiki.daemon"];
  }
  try {
    child = spawn(bin, args, { stdio: "ignore" });
  } catch (e) {
    return fail({ reason: "spawn-failed", detail: String(e) });
  }
  child.on("error", e =>
    fail({ reason: "spawn-failed", detail: String(e) }));
  child.on("exit", (code, signal) => {
    child = null;
    if (code !== 0) {
      fail({ reason: "exited", detail: `código ${code ?? signal}` });
    }
  });
  lastFailure = null;
  return null;
}

export function stopSidecar(): void {
  child?.kill();
  child = null;
}

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

export async function startSidecar(resourcesPath: string): Promise<void> {
  if (child || (await daemonAlive())) return;   // daemon externo já sobe o app
  const packaged = path.join(resourcesPath, "backend", "llmwiki-server");
  if (existsSync(packaged)) {
    child = spawn(packaged, [], { stdio: "ignore" });
  } else {
    const venv = path.join(__dirname, "..", "..", "backend", ".venv",
                           "bin", "python");
    if (!existsSync(venv)) return;              // modo read-only sem daemon
    child = spawn(venv, ["-m", "llmwiki.daemon"], { stdio: "ignore" });
  }
  child.on("exit", () => { child = null; });
}

export function stopSidecar(): void {
  child?.kill();
  child = null;
}

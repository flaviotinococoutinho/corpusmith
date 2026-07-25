import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("llmwiki", {
  handshake: () => ipcRenderer.invoke("llmwiki:handshake"),
  // F0: motivo da falha do sidecar — o que o painel de indisponibilidade
  // mostra em vez de um "Carregando…" terminal.
  sidecarFailure: () => ipcRenderer.invoke("llmwiki:sidecarFailure"),
});

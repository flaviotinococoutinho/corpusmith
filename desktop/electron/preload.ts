import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("corpusmith", {
  handshake: () => ipcRenderer.invoke("corpusmith:handshake"),
  // F0: motivo da falha do sidecar — o que o painel de indisponibilidade
  // mostra em vez de um "Carregando…" terminal.
  sidecarFailure: () => ipcRenderer.invoke("corpusmith:sidecarFailure"),
});

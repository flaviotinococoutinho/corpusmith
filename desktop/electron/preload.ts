import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("llmwiki", {
  handshake: () => ipcRenderer.invoke("llmwiki:handshake"),
});

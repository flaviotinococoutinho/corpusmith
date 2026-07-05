import { app, BrowserWindow, ipcMain } from "electron";
import path from "node:path";
import { daemonAlive, readHandshake, startSidecar, stopSidecar } from "./sidecar";

let win: BrowserWindow | null = null;

async function createWindow(): Promise<void> {
  win = new BrowserWindow({
    width: 1280,
    height: 840,
    title: "LLM Wiki — Cockpit",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  if (process.env.VITE_DEV_SERVER_URL) {
    await win.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else {
    await win.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }
}

ipcMain.handle("llmwiki:handshake", async () =>
  (await daemonAlive()) ? readHandshake() : null);

app.whenReady().then(async () => {
  await startSidecar(process.resourcesPath);
  await createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("quit", stopSidecar);

import { useState } from "react";
import { DashboardPanel } from "./panels/DashboardPanel";
import { InboxPanel } from "./panels/InboxPanel";
import { ExplorerPanel } from "./panels/ExplorerPanel";
import { ChatEvidencePanel } from "./panels/ChatEvidencePanel";
import { QualityPanel } from "./panels/QualityPanel";
import { ProcessesPanel } from "./panels/ProcessesPanel";
import { MemoryPanel } from "./panels/MemoryPanel";
import { GraphPanel } from "./panels/GraphPanel";
import { InsightsPanel } from "./panels/InsightsPanel";
import { CurationPanel } from "./panels/CurationPanel";
import { StatusBar } from "./panels/StatusBar";

const TABS = {
  dashboard: ["🏠 Estado", DashboardPanel],
  ask:       ["💬 Consulta", ChatEvidencePanel],
  inbox:     ["📥 Inbox", InboxPanel],
  wiki:      ["📚 Wiki", ExplorerPanel],
  graph:     ["🕸 Grafo", GraphPanel],
  insights:  ["📈 Indicadores", InsightsPanel],
  memory:    ["🧠 Memória", MemoryPanel],
  curation:  ["🗂 Curadoria", CurationPanel],
  quality:   ["✅ Qualidade", QualityPanel],
  processes: ["⚙️ Processos", ProcessesPanel],
} as const;

export default function App() {
  const [tab, setTab] = useState<keyof typeof TABS>("dashboard");
  const Panel = TABS[tab][1];
  return (
    <div className="flex flex-col h-screen">
      <div className="flex flex-1 min-h-0">
        <nav className="w-44 border-r p-2 space-y-1 bg-neutral-50">
          {Object.entries(TABS).map(([k, [label]]) => (
            <button key={k}
              className={`w-full text-left px-3 py-2 rounded text-sm ${
                tab === k ? "bg-neutral-200 font-medium" : "hover:bg-neutral-100"}`}
              onClick={() => setTab(k as keyof typeof TABS)}>{label}</button>
          ))}
        </nav>
        <main className="flex-1 overflow-auto"><Panel /></main>
      </div>
      <StatusBar />
    </div>
  );
}

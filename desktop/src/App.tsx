import { useEffect, useState } from "react";
import { DashboardPanel } from "./panels/DashboardPanel";
import { InboxPanel } from "./panels/InboxPanel";
import { ExplorerPanel } from "./panels/ExplorerPanel";
import { ChatEvidencePanel } from "./panels/ChatEvidencePanel";
import { QualityPanel } from "./panels/QualityPanel";
import { ProcessesPanel } from "./panels/ProcessesPanel";
import { MemoryPanel } from "./panels/MemoryPanel";
import { CognitionPanel } from "./panels/CognitionPanel";
import { FocusPanel } from "./panels/FocusPanel";
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
  cognition: ["🧭 Cognição", CognitionPanel],
  focus:     ["🎯 Foco", FocusPanel],
  curation:  ["🗂 Curadoria", CurationPanel],
  quality:   ["✅ Qualidade", QualityPanel],
  processes: ["⚙️ Processos", ProcessesPanel],
} as const;

export default function App() {
  const [tab, setTab] = useState<keyof typeof TABS>("dashboard");
  // R3 (v1.8): a fila "Próxima ação" navega por evento — um clique leva à
  // aba onde a ação se realiza, sem acoplar o Dashboard ao switch de abas.
  useEffect(() => {
    const go = (e: Event) => {
      const target = (e as CustomEvent).detail;
      if (target in TABS) setTab(target as keyof typeof TABS);
    };
    window.addEventListener("bc:navigate", go);
    return () => window.removeEventListener("bc:navigate", go);
  }, []);
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

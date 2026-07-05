import { useState } from "react";
import { client } from "../lib/client";

const KINDS = [["semantic", "Memória semântica"], ["decision", "Decisão"],
  ["runbook", "Runbook"], ["skill", "Skill procedural"],
  ["question", "Pergunta aberta"], ["alert", "Alerta arquitetural"]] as const;

export function PromoteDialog({ content, source, onClose, initialKind }:
  { content: string; source: string; onClose: () => void;
    initialKind?: string }) {
  const [kind, setKind] = useState(initialKind ?? "semantic");
  const [title, setTitle] = useState("");
  const [privacy, setPrivacy] = useState("local_only");
  const [done, setDone] = useState<string | null>(null);

  const save = async () => {
    const r = await client.promote({ kind, title, content, source, privacy });
    setDone(r.pages?.[0] ?? "ok");
  };

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center">
      <div className="bg-white rounded-lg p-4 w-[28rem] space-y-3">
        <h3 className="font-medium">Promover para memória</h3>
        {done ? (
          <>
            <p className="text-sm">✅ criado: <code>{done}</code></p>
            <button className="border rounded px-3 py-1" onClick={onClose}>Fechar</button>
          </>
        ) : (
          <>
            <select className="border rounded w-full p-2 text-sm" value={kind}
                    onChange={e => setKind(e.target.value)}>
              {KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </select>
            <input className="border rounded w-full p-2 text-sm" placeholder="Título"
                   value={title} onChange={e => setTitle(e.target.value)} />
            <textarea className="border rounded w-full p-2 text-xs h-32"
                      value={content} readOnly />
            <select className="border rounded w-full p-2 text-sm" value={privacy}
                    onChange={e => setPrivacy(e.target.value)}>
              <option value="local_only">🔒 local_only</option>
              <option value="api_allowed">🌐 api_allowed</option>
            </select>
            <div className="flex gap-2 justify-end">
              <button className="px-3 py-1" onClick={onClose}>Cancelar</button>
              <button className="border rounded px-3 py-1 font-medium"
                      disabled={!title} onClick={save}>Promover</button>
            </div>
          </>)}
      </div>
    </div>
  );
}

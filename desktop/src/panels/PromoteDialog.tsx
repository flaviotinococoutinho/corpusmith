// Promover para memória — e a colisão como decisão humana (F3-PR1, RFC-003).
//
// Antes deste PR, promover um título repetido APAGAVA a página residente em
// silêncio, e este dialog mostrava "✅ criado". Agora o backend devolve
// `op="COLLISION"` sem escrever nada, e este componente apresenta as três
// saídas que sempre foram do humano: escrever sobre a residente (explícito,
// com log Update e frontmatter fundido), criar com outro slug, ou cancelar.
import { useState } from "react";
import { client } from "../lib/client";
import type { PromoteResult } from "../lib/daemonClient";

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
  const [collision, setCollision] = useState<PromoteResult | null>(null);

  const handle = (r: PromoteResult) => {
    if (r.op === "COLLISION") setCollision(r);
    else setDone(r.pages?.[0] ?? "ok");
  };

  const save = async () =>
    handle(await client.promote({ kind, title, content, source, privacy }));

  const resolve = async (resolution: "update" | "new_slug") =>
    handle(await client.promote({
      kind, title, content, source, privacy,
      resolution, target: collision?.target }));

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center">
      <div className="bg-white rounded-lg p-4 w-[28rem] space-y-3">
        <h3 className="font-medium">Promover para memória</h3>
        {done ? (
          <>
            <p className="text-sm">✅ salvo: <code>{done}</code></p>
            <button className="border rounded px-3 py-1" onClick={onClose}>Fechar</button>
          </>
        ) : collision ? (
          <>
            <p className="text-sm">
              ⚠️ Já existe memória sobre isto:{" "}
              <code className="text-xs">{collision.target}</code>
            </p>
            <p className="text-xs text-neutral-500">{collision.reason}</p>
            <div className="flex flex-col gap-2 text-sm">
              <button className="border rounded px-3 py-1.5 text-left"
                      onClick={() => resolve("update")}>
                ✍️ Escrever sobre a existente
                <span className="block text-xs text-neutral-500">
                  substitui o corpo; tags e campos curados são preservados;
                  fica no log como Update
                </span>
              </button>
              <button className="border rounded px-3 py-1.5 text-left"
                      onClick={() => resolve("new_slug")}>
                ➕ Criar como página separada
                <span className="block text-xs text-neutral-500">
                  são conceitos distintos — nasce com sufixo (ex.: -2)
                </span>
              </button>
              <button className="px-3 py-1.5 text-left text-neutral-600"
                      onClick={onClose}>
                Cancelar — nada foi escrito
              </button>
            </div>
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

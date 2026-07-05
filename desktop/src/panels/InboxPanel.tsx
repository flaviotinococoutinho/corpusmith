import { useEffect, useState } from "react";
import { client } from "../lib/client";

export function InboxPanel() {
  const [items, setItems] = useState<any[]>([]);
  const load = () => client.inbox().then(r => setItems(r.items));
  useEffect(() => { load(); }, []);
  // path é relativo ao knowledge base (raw/...): o daemon resolve contra o kb
  const compile = (path: string) =>
    client.enqueue("compile_source", { path }).then(load);
  return (
    <div className="p-4">
      <h2 className="font-semibold mb-3">Inbox de conhecimento (raw/)</h2>
      <table className="w-full text-sm">
        <thead><tr className="text-left text-neutral-500">
          <th>Fonte</th><th>Privacidade</th><th>Status</th><th /></tr></thead>
        <tbody>{items.map(i => (
          <tr key={i.path} className="border-t">
            <td className="font-mono text-xs">{i.path}</td>
            <td>{i.privacy === "local_only" ? "🔒 local" : "🌐 api"}</td>
            <td>{{ novo: "🆕", stale: "🟡", compilado: "✅" }[i.status as string]} {i.status}</td>
            <td>{i.status !== "compilado" &&
              <button className="border rounded px-2 py-1 text-xs"
                      onClick={() => compile(i.path)}>
                {i.status === "stale" ? "Recompilar" : "Compilar"}</button>}</td>
          </tr>))}</tbody>
      </table>
    </div>
  );
}

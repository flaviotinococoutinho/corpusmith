import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { client } from "../lib/client";

export function ExplorerPanel() {
  const [pages, setPages] = useState<any[]>([]);
  const [sel, setSel] = useState<any>(null);
  useEffect(() => { client.pages().then(r => setPages(r.pages)); }, []);
  const tree = useMemo(() => {
    const g: Record<string, any[]> = {};
    for (const p of pages)
      (g[p.path.split("/").slice(0, -1).join("/") || "(raiz)"] ??= []).push(p);
    return g;
  }, [pages]);
  const open = (path: string) => client.page(path).then(setSel);

  return (
    <div className="flex h-full text-sm">
      <aside className="w-72 border-r overflow-auto p-2">
        {Object.entries(tree).map(([dir, list]) => (
          <div key={dir} className="mb-2">
            <div className="text-xs font-semibold text-neutral-500">{dir}</div>
            {list.map(p => (
              <button key={p.path}
                className="block w-full text-left px-2 py-1 rounded hover:bg-neutral-100"
                onClick={() => open(p.path)}>
                {p.stale && "🟡 "}{p.privacy === "local_only" && "🔒 "}{p.title}
              </button>))}
          </div>))}
      </aside>
      <div className="flex-1 overflow-auto p-4 prose prose-sm max-w-none">
        {sel ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{sel.body}</ReactMarkdown>
             : <p className="text-neutral-400">Selecione uma página.</p>}
      </div>
      {sel && (
        <aside className="w-72 border-l p-3 overflow-auto">
          <h3 className="font-medium mb-2">Frontmatter</h3>
          <table className="text-xs w-full">
            <tbody>{Object.entries(sel.meta).map(([k, v]) => (
              <tr key={k} className="border-t">
                <td className="pr-2 text-neutral-500 align-top">{k}</td>
                <td className="break-all">{JSON.stringify(v)}</td>
              </tr>))}</tbody>
          </table>
          <h3 className="font-medium mt-4 mb-1">Git</h3>
          {sel.git.map((l: string) => (
            <div key={l} className="text-xs font-mono">{l}</div>))}
          <div className="mt-3 space-x-2">
            <button className="border rounded px-2 py-1 text-xs"
              onClick={() => client.markStale(sel.path).then(() => open(sel.path))}>
              marcar stale</button>
          </div>
        </aside>)}
    </div>
  );
}

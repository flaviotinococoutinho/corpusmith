import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { client } from "../lib/client";
import type { ConceptSheet } from "../lib/daemonClient";
import { ConceptSheetView } from "./ConceptSheetView";

export function ExplorerPanel() {
  const [pages, setPages] = useState<any[]>([]);
  const [sel, setSel] = useState<any>(null);
  const [authOnly, setAuthOnly] = useState(false);          // v0.8 §11.2
  const [uses, setUses] = useState<Record<string, number>>({});
  // Q-1: a ficha do conceito ao abrir a página. `null` é "sem ficha"
  // (página que não existe mais no bundle, ou daemon fora) e não trava a
  // leitura do texto — a ficha é COMPOSIÇÃO, o canônico é a autoridade.
  const [sheet, setSheet] = useState<ConceptSheet | null>(null);
  useEffect(() => {
    client.pages().then(r => setPages(r.pages));
    client.authorities().then(r => {
      const m: Record<string, number> = {};
      for (const e of r.entities) m[e.canonical] = e.uses;
      setUses(m);
    }).catch(() => setUses({}));
  }, []);
  const tree = useMemo(() => {
    const g: Record<string, any[]> = {};
    for (const p of pages) {
      if (authOnly && p.type !== "authority_record") continue;
      (g[p.path.split("/").slice(0, -1).join("/") || "(raiz)"] ??= []).push(p);
    }
    return g;
  }, [pages, authOnly]);
  const open = (path: string) => {
    setSheet(null);
    client.sheet(path).then(setSheet).catch(() => setSheet(null));
    return client.page(path).then(setSel);
  };

  return (
    <div className="flex h-full text-sm">
      <aside className="w-72 border-r overflow-auto p-2">
        <label className="text-xs block mb-2">
          <input type="checkbox" checked={authOnly}
                 onChange={e => setAuthOnly(e.target.checked)} />{" "}
          só authority records
        </label>
        {Object.entries(tree).map(([dir, list]) => (
          <div key={dir} className="mb-2">
            <div className="text-xs font-semibold text-neutral-500">{dir}</div>
            {list.map(p => (
              <button key={p.path}
                className="block w-full text-left px-2 py-1 rounded hover:bg-neutral-100"
                onClick={() => open(p.path)}>
                {p.stale && "🟡 "}{p.privacy === "local_only" && "🔒 "}{p.title}
                {p.type === "authority_record" && uses[p.title] != null &&
                  <span className="text-neutral-400"> · {uses[p.title]} usos</span>}
              </button>))}
          </div>))}
      </aside>
      <div className="flex-1 overflow-auto p-4 prose prose-sm max-w-none">
        {sel ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{sel.body}</ReactMarkdown>
             : <p className="text-neutral-400">Selecione uma página.</p>}
      </div>
      {sel && (
        <aside className="w-80 border-l p-3 overflow-auto">
          {sheet && <div className="mb-4"><ConceptSheetView sheet={sheet} /></div>}
          <h3 className="font-medium mb-2">Frontmatter</h3>
          <table className="text-xs w-full">
            <tbody>{Object.entries(sel.meta).map(([k, v]) => (
              <tr key={k} className="border-t">
                <td className="pr-2 text-neutral-500 align-top">{k}</td>
                <td className="break-all">{JSON.stringify(v)}</td>
              </tr>))}</tbody>
          </table>
          {sel.related?.length > 0 && (
            <>
              <h3 className="font-medium mt-4 mb-1">
                🔗 Relacionadas (linke?)</h3>
              {sel.related.map((r: any) => (
                <div key={r.page} className="text-xs mb-1">
                  <button className="font-mono underline text-left"
                          onClick={() => open(r.page)}>{r.page}</button>
                  <span className="text-neutral-400">
                    {" "}· {r.shared.join(", ")}</span>
                </div>))}
            </>)}
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

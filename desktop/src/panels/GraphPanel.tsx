// 🕸 Grafo da memória (Fase 5 · v1.1) — visão estilo Obsidian em SVG puro:
// simulação de forças própria (repulsão + molas + gravidade), cor por
// classificador (tipo/comunidade/privacidade/stale/heat), pontes frágeis
// tracejadas em vermelho, clique abre cartão com ações de curadoria.
// v1.1 (InfraNodus próprio): tamanho do nó = grau + ARTICULAÇÃO
// (intermediação de Brandes) e lacunas estruturais como ARESTAS-FANTASMA
// roxas pontilhadas — o link que FALTA, com "?" clicável que captura a
// pergunta-ponte como question.
import { useEffect, useMemo, useRef, useState } from "react";
import { client } from "../lib/client";
import { DaemonUnavailable } from "./DaemonUnavailable";

const PALETTE = ["#6366f1", "#059669", "#d97706", "#dc2626", "#0891b2",
                 "#7c3aed", "#be185d", "#4d7c0f", "#b45309", "#334155"];

type Node = any & { x: number; y: number; vx: number; vy: number };

function colorOf(node: any, mode: string): string {
  if (mode === "stale") return node.stale ? "#f59e0b" : "#94a3b8";
  if (mode === "privacy")
    return node.privacy === "local_only" ? "#0f766e" : "#6366f1";
  if (mode === "heat") {
    const h = Math.min(1, node.heat ?? 0);
    return `hsl(${220 - 200 * h}, 80%, ${65 - 20 * h}%)`;
  }
  const key = mode === "community" ? node.community : node.type;
  const hash = String(key).split("").reduce(
    (a, c) => (a * 31 + c.charCodeAt(0)) | 0, 7);
  return PALETTE[Math.abs(hash) % PALETTE.length];
}

export function GraphPanel() {
  const [data, setData] = useState<any>(null);
  const [mode, setMode] = useState("type");
  const [selected, setSelected] = useState<any>(null);
  const [gaps, setGaps] = useState<any[]>([]);
  const [notice, setNotice] = useState("");
  const [tick, setTick] = useState(0);
  const nodesRef = useRef<Node[]>([]);
  const running = useRef(false);

  const [erro, setErro] = useState<unknown>(null);
  useEffect(() => {
    client.connect().then(() => {
      client.graph().then((g) => {
        const W = 900, H = 640;
        nodesRef.current = g.nodes.map((n: any, i: number) => ({
          ...n,
          x: W / 2 + 220 * Math.cos((2 * Math.PI * i) / g.nodes.length),
          y: H / 2 + 220 * Math.sin((2 * Math.PI * i) / g.nodes.length),
          vx: 0, vy: 0,
        }));
        setData(g);
      });
      client.gaps().then(g => setGaps(g.gaps)).catch(() => {});
    }).catch(setErro);              // F0: falha do daemon vira estado visível
  }, []);

  // simulação: roda ~240 ticks e congela (re-renderiza a cada 4)
  useEffect(() => {
    if (!data || running.current) return;
    running.current = true;
    const nodes = nodesRef.current;
    const index: Record<string, Node> = {};
    nodes.forEach(n => { index[n.page] = n; });
    let alpha = 1, count = 0;
    const timer = setInterval(() => {
      for (let a = 0; a < nodes.length; a++)       // repulsão O(n²)
        for (let b = a + 1; b < nodes.length; b++) {
          const na = nodes[a], nb = nodes[b];
          let dx = na.x - nb.x, dy = na.y - nb.y;
          const d2 = Math.max(64, dx * dx + dy * dy);
          const f = (2600 * alpha) / d2;
          const d = Math.sqrt(d2);
          dx /= d; dy /= d;
          na.vx += dx * f; na.vy += dy * f;
          nb.vx -= dx * f; nb.vy -= dy * f;
        }
      for (const e of data.edges) {                 // molas nas arestas
        const sa = index[e.src], sb = index[e.dst];
        if (!sa || !sb) continue;
        const dx = sb.x - sa.x, dy = sb.y - sa.y;
        const d = Math.max(1, Math.sqrt(dx * dx + dy * dy));
        const f = 0.02 * alpha * (d - 90);
        sa.vx += (dx / d) * f; sa.vy += (dy / d) * f;
        sb.vx -= (dx / d) * f; sb.vy -= (dy / d) * f;
      }
      for (const n of nodes) {                      // gravidade + integração
        n.vx += (450 - n.x) * 0.002 * alpha;
        n.vy += (320 - n.y) * 0.002 * alpha;
        n.x += n.vx *= 0.85;
        n.y += n.vy *= 0.85;
      }
      alpha *= 0.985;
      if (++count % 4 === 0) setTick(t => t + 1);
      if (alpha < 0.02 || count > 240) {
        clearInterval(timer);
        running.current = false;
        setTick(t => t + 1);
      }
    }, 16);
    return () => clearInterval(timer);
  }, [data]);

  const positions = useMemo(() => {
    const m: Record<string, Node> = {};
    nodesRef.current.forEach(n => { m[n.page] = n; });
    return m;
  }, [tick, data]);

  if (erro) return <DaemonUnavailable error={erro}
                     onRetry={() => client.graph()} />;
  if (!data) return <div className="p-6">Carregando grafo…</div>;
  const nodes = nodesRef.current;
  return (
    <div className="flex h-full">
      <div className="flex-1 flex flex-col min-w-0">
        <div className="p-2 border-b flex items-center gap-3 text-xs">
          <span className="font-semibold text-sm">🕸 Grafo</span>
          <label>cor por{" "}
            <select className="border rounded p-1" value={mode}
                    onChange={e => setMode(e.target.value)}>
              {["type", "community", "privacy", "stale", "heat"].map(m =>
                <option key={m} value={m}>{m}</option>)}
            </select></label>
          <span className="text-neutral-400">
            {data.nodes.length} nós · {data.edges.length} arestas ·
            pontes em vermelho · lacunas em roxo (clique no ?) ·
            tamanho = grau + articulação</span>
          {notice && <span className="border rounded px-2 py-0.5
            bg-violet-50 text-violet-700">{notice}</span>}
        </div>
        <svg className="flex-1 bg-neutral-50" viewBox="0 0 900 640">
          {data.edges.map((e: any, i: number) => {
            const a = positions[e.src], b = positions[e.dst];
            if (!a || !b) return null;
            return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
              stroke={e.bridge ? "#dc2626" : "#cbd5e1"}
              strokeDasharray={e.bridge ? "4 3" : undefined}
              strokeWidth={e.confidence === "extracted" ? 1.4 : 0.7}
              opacity={0.8} />;
          })}
          {gaps.map((gp: any, i: number) => {
            // aresta-fantasma: o link AUSENTE entre os articuladores
            const a = positions[gp.rep_a], b = positions[gp.rep_b];
            if (!a || !b) return null;
            const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
            return (
              <g key={`gap${i}`} className="cursor-pointer"
                 onClick={() => client.promote({
                   kind: "question", title: gp.question,
                   content: `# ${gp.question}\n\nPergunta-ponte entre `
                     + `**${gp.title_a}** (${gp.rep_a}) e `
                     + `**${gp.title_b}** (${gp.rep_b}) — lacuna `
                     + `estrutural (déficit ${gp.deficit}).`,
                   tags: ["ponte"] }).then(() =>
                     setNotice(`❓ capturada: ${gp.question}`))}>
                <title>{gp.question} (déficit {gp.deficit})</title>
                <line x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                  stroke="#7c3aed" strokeDasharray="2 6"
                  strokeWidth={1.2} opacity={0.55} />
                <circle cx={mx} cy={my} r={7} fill="#ede9fe"
                        stroke="#7c3aed" strokeWidth={1} />
                <text x={mx} y={my + 3.5} fontSize="10" fill="#7c3aed"
                      textAnchor="middle">?</text>
              </g>);
          })}
          {nodes.map(n => (
            <g key={n.page} onClick={() => setSelected(n)}
               className="cursor-pointer">
              <circle cx={n.x} cy={n.y}
                r={4 + Math.log1p(n.degree) * 2
                     + (n.betweenness ?? 0) * 16}
                fill={colorOf(n, mode)}
                stroke={selected?.page === n.page ? "#111" : "#fff"}
                strokeWidth={selected?.page === n.page ? 2 : 1} />
              {(n.degree >= 3 || (n.betweenness ?? 0) > 0.15 ||
                selected?.page === n.page) && (
                <text x={n.x + 8} y={n.y + 3} fontSize="9"
                      fill="#475569">{n.title}</text>)}
            </g>))}
        </svg>
      </div>
      {selected && (
        <aside className="w-72 border-l p-3 text-sm overflow-auto">
          <h3 className="font-medium">{selected.title}</h3>
          <table className="text-xs w-full mt-2">
            <tbody>
              {[["página", selected.page], ["tipo", selected.type],
                ["comunidade", selected.community],
                ["grau", selected.degree],
                ["articulação", selected.betweenness ?? 0],
                ["heat", selected.heat],
                ["privacidade", selected.privacy],
                ["origem", selected.origin],
                ["órfã", selected.orphan ? "sim" : "não"],
                ["stale", selected.stale ? "sim" : "não"]].map(([k, v]) => (
                <tr key={String(k)} className="border-t">
                  <td className="text-neutral-500 pr-2">{k}</td>
                  <td className="break-all">{String(v)}</td></tr>))}
            </tbody>
          </table>
          <div className="mt-3 space-x-2">
            {!selected.stale && (
              <button className="border rounded px-2 py-1 text-xs"
                onClick={() => client.markStale(selected.page)
                  .then(() => setSelected({ ...selected, stale: true }))}>
                🟡 stale</button>)}
            <button className="border rounded px-2 py-1 text-xs"
              onClick={() => client.freeze(selected.page)
                .then(() => setSelected(null))
                .catch(e => alert(`veto: ${e.message}`))}>🧊 congelar</button>
          </div>
        </aside>)}
    </div>
  );
}

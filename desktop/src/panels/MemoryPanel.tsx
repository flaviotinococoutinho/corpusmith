// Painel de Memória (v0.14): as quatro camadas cognitivas + a base fria —
// o mapa vivo de ONDE cada conhecimento mora e como transita entre camadas.
import { useEffect, useState } from "react";
import { client } from "../lib/client";

function Column({ title, hint, children }:
  { title: string; hint: string; children: any }) {
  return (
    <div className="border rounded p-3 flex flex-col min-h-0">
      <h3 className="font-medium">{title}</h3>
      <p className="text-xs text-neutral-400 mb-2">{hint}</p>
      <div className="overflow-auto text-xs space-y-1 flex-1">{children}</div>
    </div>
  );
}

export function MemoryPanel() {
  const [m, setM] = useState<any>(null);
  const [cold, setCold] = useState<any>(null);
  const load = () => {
    client.memory().then(setM);
    client.cold().then(setCold).catch(() => setCold(null));
  };
  useEffect(() => { client.connect().then(load); }, []);
  if (!m) return <div className="p-6">Carregando camadas…</div>;
  return (
    <div className="p-4 h-full flex flex-col gap-3">
      <h2 className="font-semibold">🧠 Camadas de memória
        <button className="border rounded px-2 py-1 text-xs ml-3"
                onClick={load}>atualizar</button></h2>
      <div className="grid grid-cols-4 gap-3 flex-1 min-h-0">
        <Column title="T0 · Working" hint="eventos do runtime (efêmera)">
          {m.working.map((e: any) => (
            <div key={e.seq} className="font-mono truncate"
                 title={e.data}>#{e.seq} {e.type}</div>))}
          {!m.working.length && <span className="text-neutral-400">(vazio)</span>}
        </Column>
        <Column title="T1 · Episódica" hint="log.md — append-only">
          {m.episodic.map((l: string, i: number) => (
            <div key={i} className={l.startsWith("## ")
              ? "font-semibold mt-1" : "font-mono truncate"}>{l}</div>))}
          {!m.episodic.length && <span className="text-neutral-400">(vazio)</span>}
        </Column>
        <Column title="T2 · Semântica"
                hint="conceitos, decisões, specs (compilada)">
          {m.semantic.map((p: any) => (
            <div key={p.path} className="truncate">
              {p.stale && "🟡 "}{p.title}
              <span className="text-neutral-400"> · {p.type}</span></div>))}
          {!m.semantic.length && <span className="text-neutral-400">(vazio)</span>}
        </Column>
        <Column title="T2 · Procedural"
                hint={`runbooks e skills${m.procedural.active_adapter
                  ? ` · adapter: ${m.procedural.active_adapter}` : ""}`}>
          {m.procedural.pages.map((p: any) => (
            <div key={p.path} className="truncate">{p.title}
              <span className="text-neutral-400"> · {p.type}</span></div>))}
          {!m.procedural.pages.length &&
            <span className="text-neutral-400">(vazio)</span>}
        </Column>
      </div>
      <div className="border rounded p-3 text-xs">
        <h3 className="font-medium text-sm">
          T3 · ❄️ Base fria{cold && ` · ${cold.count} memória(s) · ${
            cold.compression_saved}% compactado`}</h3>
        {cold?.entries?.slice(0, 6).map((e: any) => (
          <div key={e.page} className="flex items-center gap-2 mt-1">
            <span className="font-mono flex-1 truncate">{e.page}</span>
            <span className="text-neutral-400">
              P(recall) {e.recall_p?.toFixed(3) ?? "—"}</span>
            <button className="border rounded px-1"
                    onClick={() => client.recycle(e.page).then(load)}>
              ♻️</button>
          </div>))}
        {(!cold || !cold.count) &&
          <p className="text-neutral-400 mt-1">
            Nada congelado — T4 (Git) guarda o resto da história.</p>}
      </div>
    </div>
  );
}

//! corpusmith-native-worker — executável para jobs longos (ADR-39 §9).
//!
//! Protocolo v1: manifesto JSON (campos desconhecidos REJEITADOS) via
//! argv[1]; eventos NDJSON no stdout (worker.started / stage.* /
//! worker.completed|failed|cancelled); relatório final em
//! `<output_dir>/report.json`. O worker NUNCA escreve no bundle
//! canônico; hard timeout é responsabilidade do processo PAI (matar o
//! processo), deadline aqui é cooperativo. Exit codes ESTÁVEIS:
//! 0=completed · 2=manifesto inválido · 3=cancelled · 4=deadline ·
//! 5=erro interno.

use corpusmith_etl::{WorkerManifest, WorkerReport};
use corpusmith_types::{GRAPH_ALGO_VERSION, PROTOCOL_VERSION,
                      SKETCH_ALGO_VERSION};
use serde_json::{json, Value};
use std::io::Write;
use std::time::{SystemTime, UNIX_EPOCH};

fn emit(event: &str, data: Value) {
    let mut line = json!({"event": event});
    if let (Some(obj), Some(extra)) = (line.as_object_mut(), data.as_object())
    {
        for (k, v) in extra {
            obj.insert(k.clone(), v.clone());
        }
    }
    println!("{line}");
    let _ = std::io::stdout().flush();
}

fn now_ms() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as u64).unwrap_or(0)
}

fn deadline_hit(manifest: &WorkerManifest) -> bool {
    manifest.deadline_epoch_ms > 0 && now_ms() > manifest.deadline_epoch_ms
}

fn run(manifest: &WorkerManifest) -> Result<(Value, Value), (i32, String)> {
    match manifest.job_type.as_str() {
        // smoke do doctor: PPR + SimHash mínimos, prova a cadeia inteira
        "selfcheck" => {
            emit("stage.started", json!({"stage": "selfcheck"}));
            let csr = corpusmith_graph::Csr::from_edges(
                &[0, 1], &[1, 2], &[1.0, 1.0], 3)
                .map_err(|e| (5, e.to_string()))?;
            let ranked = corpusmith_graph::ppr(
                &csr, &[0], &[1.0], 0.0, 0.5, 20, 1e-9, 3);
            let total: f64 = ranked.iter().map(|(_, s)| s).sum();
            let sketches = corpusmith_sketch::simhash_batch(
                &["memoria conhecimento grafo".into(),
                  "memoria conhecimento grafo".into()], 3);
            if (total - 1.0).abs() > 1e-6 || sketches[0] != sketches[1] {
                return Err((5, "selfcheck divergente".into()));
            }
            emit("stage.completed", json!({"stage": "selfcheck"}));
            Ok((json!({"ppr_mass": total, "sketch_equal": true}),
                json!([])))
        }
        // métricas de grafo em lote: input {edges: [[src,dst,w],...],
        // n_nodes, top_k} — SINAIS apenas; significado fica no Python
        "graph_metrics" => {
            emit("stage.started", json!({"stage": "graph_load"}));
            let edges = manifest.input.get("edges")
                .and_then(|v| v.as_array())
                .ok_or((2, "input.edges ausente".to_string()))?;
            let n_nodes = manifest.input.get("n_nodes")
                .and_then(|v| v.as_u64())
                .ok_or((2, "input.n_nodes ausente".to_string()))? as usize;
            let top_k = manifest.input.get("top_k")
                .and_then(|v| v.as_u64()).unwrap_or(0) as usize;
            let (mut s, mut t, mut w) = (Vec::new(), Vec::new(), Vec::new());
            for e in edges {
                let triple = e.as_array()
                    .ok_or((2, "aresta não é [src,dst,w]".to_string()))?;
                s.push(triple[0].as_u64().unwrap_or(0) as u32);
                t.push(triple[1].as_u64().unwrap_or(0) as u32);
                w.push(triple.get(2).and_then(|x| x.as_f64())
                       .unwrap_or(1.0) as f32);
            }
            let csr = corpusmith_graph::Csr::from_edges(&s, &t, &w, n_nodes)
                .map_err(|e| (2, e.to_string()))?;
            emit("stage.completed", json!({"stage": "graph_load"}));
            if deadline_hit(manifest) {
                return Err((4, "deadline antes do brandes".into()));
            }
            emit("stage.started", json!({"stage": "brandes"}));
            let mut central = corpusmith_graph::brandes(&csr);
            central.sort_unstable_by(|a, b| b.1.partial_cmp(&a.1)
                .unwrap_or(std::cmp::Ordering::Equal).then(a.0.cmp(&b.0)));
            if top_k > 0 {
                central.truncate(top_k);
            }
            emit("stage.completed", json!({"stage": "brandes"}));
            let comps = corpusmith_graph::components(&csr);
            let distinct: std::collections::BTreeSet<u32> =
                comps.iter().copied().collect();
            Ok((json!({"nodes": csr.n,
                       "edges": csr.edges_undirected(),
                       "components": distinct.len(),
                       "betweenness_top":
                           central.iter()
                               .map(|(v, c)| json!([v, c]))
                               .collect::<Vec<_>>()}),
                json!([])))
        }
        other => Err((2, format!("job_type desconhecido: {other}"))),
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let manifest_path = match args.get(1) {
        Some(p) => p.clone(),
        None => {
            eprintln!("uso: corpusmith-native-worker <manifest.json>");
            std::process::exit(2);
        }
    };
    let raw = match std::fs::read_to_string(&manifest_path) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("manifesto ilegível: {e}");
            std::process::exit(2);
        }
    };
    let manifest: WorkerManifest = match serde_json::from_str(&raw) {
        Ok(m) => m,
        Err(e) => {
            eprintln!("manifesto inválido (campos desconhecidos são \
                       rejeitados): {e}");
            std::process::exit(2);
        }
    };
    if manifest.protocol_version != PROTOCOL_VERSION {
        eprintln!("protocolo {} ≠ {}", manifest.protocol_version,
                  PROTOCOL_VERSION);
        std::process::exit(2);
    }
    emit("worker.started",
         json!({"job_id": manifest.job_id, "trace_id": manifest.trace_id,
                "job_type": manifest.job_type,
                "protocol_version": PROTOCOL_VERSION}));
    if deadline_hit(&manifest) {
        emit("worker.failed", json!({"job_id": manifest.job_id,
                                     "reason": "deadline"}));
        std::process::exit(4);
    }
    let started = std::time::Instant::now();
    match run(&manifest) {
        Ok((metrics, artifacts)) => {
            let report = WorkerReport {
                protocol_version: PROTOCOL_VERSION,
                job_id: manifest.job_id.clone(),
                status: "completed".into(),
                backend: "rust".into(),
                algorithm_versions: json!({
                    "graph": GRAPH_ALGO_VERSION,
                    "sketch": SKETCH_ALGO_VERSION}),
                metrics: json!({"elapsed_ms":
                                started.elapsed().as_millis() as u64,
                                "detail": metrics}),
                artifacts: artifacts.as_array().map(|a| a.iter()
                    .filter_map(|v| v.as_str().map(String::from))
                    .collect()).unwrap_or_default(),
                warnings: vec![],
            };
            let out = std::path::Path::new(&manifest.output_dir);
            let _ = std::fs::create_dir_all(out);
            if let Ok(body) = serde_json::to_string_pretty(&report) {
                let _ = std::fs::write(out.join("report.json"), body);
            }
            emit("worker.completed",
                 json!({"job_id": manifest.job_id,
                        "elapsed_ms": started.elapsed().as_millis() as u64}));
        }
        Err((code, reason)) => {
            let event = match code {
                3 => "worker.cancelled",
                _ => "worker.failed",
            };
            emit(event, json!({"job_id": manifest.job_id,
                               "reason": reason}));
            std::process::exit(code);
        }
    }
}

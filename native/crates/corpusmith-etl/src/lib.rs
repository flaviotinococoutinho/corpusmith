//! corpusmith-etl — ALVO da Fase 4 (ADR-39): leitura paralela do delta,
//! extração em lote, agregação determinística, lotes colunares e
//! relatórios de cardinalidade, com cancelamento cooperativo e
//! checkpoints. NESTA entrega: o MANIFESTO do worker (protocolo v1,
//! campos desconhecidos REJEITADOS) — o Native Index Builder que
//! produzirá index.db.next só entra após Graph e Sketch validados, e o
//! swap do índice é SEMPRE decisão do Python (o worker nunca substitui
//! index.db sozinho).

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct WorkerManifest {
    pub protocol_version: u32,
    pub job_id: String,
    pub trace_id: String,
    pub job_type: String,
    #[serde(default)]
    pub deadline_epoch_ms: u64,
    pub input: serde_json::Value,
    pub output_dir: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkerReport {
    pub protocol_version: u32,
    pub job_id: String,
    pub status: String,          // completed|cancelled|failed
    pub backend: String,
    pub algorithm_versions: serde_json::Value,
    pub metrics: serde_json::Value,
    pub artifacts: Vec<String>,
    pub warnings: Vec<String>,
}

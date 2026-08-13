//! corpusmith-types — tipos serializáveis, erros fechados e versões de
//! protocolo do compute plane (ADR-39). IDs compactos: nós de grafo são
//! `u32` via string interning feito no control plane (Python).

use serde::{Deserialize, Serialize};

/// Versão do protocolo entre Python e a camada nativa (bindings E
/// worker). Incompatibilidade ⇒ recusa explícita + fallback Python.
pub const PROTOCOL_VERSION: u32 = 1;

/// Versões dos algoritmos — vão na proveniência de toda execução.
pub const GRAPH_ALGO_VERSION: &str = "ppr-0.5/brandes-1";
pub const SKETCH_ALGO_VERSION: &str = "simhash64-blake2b/bands-9";

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BackendReport {
    pub backend: String,
    pub native_version: String,
    pub algorithm_version: String,
    pub elapsed_ms: f64,
    pub items: u64,
    pub warnings: Vec<String>,
}

/// Erros FECHADOS do compute plane — traduzidos 1:1 para exceções
/// Python estáveis nos bindings.
#[derive(Debug)]
pub enum ComputeError {
    InvalidInput(String),
    ProtocolMismatch { expected: u32, got: u32 },
    Cancelled,
    DeadlineExceeded,
    Internal(String),
}

impl std::fmt::Display for ComputeError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ComputeError::InvalidInput(m) => write!(f, "entrada inválida: {m}"),
            ComputeError::ProtocolMismatch { expected, got } => {
                write!(f, "protocolo {got} ≠ esperado {expected}")
            }
            ComputeError::Cancelled => write!(f, "cancelado"),
            ComputeError::DeadlineExceeded => write!(f, "deadline excedido"),
            ComputeError::Internal(m) => write!(f, "erro interno: {m}"),
        }
    }
}

impl std::error::Error for ComputeError {}

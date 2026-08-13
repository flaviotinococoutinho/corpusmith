//! corpusmith_native — bindings PyO3 do compute plane (ADR-39).
//!
//! Regras: GIL LIBERADO durante todo trabalho pesado (allow_threads);
//! resultados voltam como SoA (listas paralelas), nunca list[dict];
//! erros viram exceções Python estáveis (ValueError/RuntimeError).

use corpusmith_graph::{brandes, components, ppr, Csr};
use corpusmith_sketch::{candidate_pairs, hamming, simhash_batch};
use corpusmith_types::{ComputeError, GRAPH_ALGO_VERSION, PROTOCOL_VERSION,
                      SKETCH_ALGO_VERSION};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyDict;

fn to_py_err(e: ComputeError) -> PyErr {
    match e {
        ComputeError::InvalidInput(m) => PyValueError::new_err(m),
        other => PyRuntimeError::new_err(other.to_string()),
    }
}

/// Snapshot imutável de grafo (CSR) — construído uma vez, consultado
/// muitas (cache por geração no lado Python).
#[pyclass(frozen)]
struct Graph {
    csr: Csr,
}

#[pymethods]
impl Graph {
    #[getter]
    fn nodes(&self) -> usize {
        self.csr.n
    }

    #[getter]
    fn edges(&self) -> u64 {
        self.csr.edges_undirected()
    }

    /// Personalized PageRank. `outside_restart` agrega seeds fora do
    /// grafo (equivalência exata para nós reais). Devolve (ids, scores).
    #[pyo3(signature = (seed_ids, seed_weights, outside_restart,
                        damping, iterations, tolerance, top_k))]
    #[allow(clippy::too_many_arguments)]
    fn ppr(&self, py: Python<'_>, seed_ids: Vec<u32>,
           seed_weights: Vec<f64>, outside_restart: f64, damping: f64,
           iterations: u32, tolerance: f64, top_k: usize)
           -> PyResult<(Vec<u32>, Vec<f64>)> {
        if seed_ids.len() != seed_weights.len() {
            return Err(PyValueError::new_err(
                "seed_ids e seed_weights com tamanhos diferentes"));
        }
        let csr = &self.csr;
        let ranked = py.allow_threads(|| {
            ppr(csr, &seed_ids, &seed_weights, outside_restart, damping,
                iterations, tolerance, top_k)
        });
        Ok(ranked.into_iter().unzip())
    }

    /// Brandes normalizado [0,1]; top_k=0 devolve todos os nós ativos.
    fn brandes(&self, py: Python<'_>, top_k: usize)
               -> PyResult<(Vec<u32>, Vec<f64>)> {
        let csr = &self.csr;
        let mut scored = py.allow_threads(|| brandes(csr));
        scored.sort_unstable_by(|a, b| b.1.partial_cmp(&a.1)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then(a.0.cmp(&b.0)));
        if top_k > 0 {
            scored.truncate(top_k);
        }
        Ok(scored.into_iter().unzip())
    }

    /// Rótulo de componente por nó (rótulo = menor id do componente).
    fn components(&self, py: Python<'_>) -> Vec<u32> {
        let csr = &self.csr;
        py.allow_threads(|| components(csr))
    }
}

/// Constrói o grafo NÃO-direcionado a partir do lote de arestas.
#[pyfunction]
fn build_graph(py: Python<'_>, sources: Vec<u32>, targets: Vec<u32>,
               weights: Vec<f32>, n_nodes: usize) -> PyResult<Graph> {
    let csr = py.allow_threads(
        || Csr::from_edges(&sources, &targets, &weights, n_nodes))
        .map_err(to_py_err)?;
    Ok(Graph { csr })
}

/// SimHash 64-bit em LOTE (rayon; ordem de saída = ordem de entrada).
#[pyfunction]
#[pyo3(signature = (texts, shingle = 3))]
fn simhash64_batch(py: Python<'_>, texts: Vec<String>, shingle: usize)
                   -> Vec<u64> {
    py.allow_threads(|| simhash_batch(&texts, shingle))
}

#[pyfunction]
fn hamming64(a: u64, b: u64) -> u32 {
    hamming(a, b)
}

/// Pares candidatos (i<j) com hamming ≤ max_hamming — (a_ids, b_ids).
#[pyfunction]
fn candidate_pairs64(py: Python<'_>, sketches: Vec<u64>, max_hamming: u32)
                     -> (Vec<u32>, Vec<u32>) {
    py.allow_threads(|| candidate_pairs(&sketches, max_hamming))
}

/// Proveniência do backend: versão, build e protocolo.
#[pyfunction]
fn backend_info(py: Python<'_>) -> PyResult<Py<PyDict>> {
    let d = PyDict::new(py);
    d.set_item("version", env!("CARGO_PKG_VERSION"))?;
    d.set_item("build", option_env!("CORPUSMITH_NATIVE_SHA").unwrap_or(""))?;
    d.set_item("protocol", PROTOCOL_VERSION)?;
    d.set_item("graph_algorithm", GRAPH_ALGO_VERSION)?;
    d.set_item("sketch_algorithm", SKETCH_ALGO_VERSION)?;
    Ok(d.into())
}

#[pymodule]
fn corpusmith_native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Graph>()?;
    m.add_function(wrap_pyfunction!(build_graph, m)?)?;
    m.add_function(wrap_pyfunction!(simhash64_batch, m)?)?;
    m.add_function(wrap_pyfunction!(hamming64, m)?)?;
    m.add_function(wrap_pyfunction!(candidate_pairs64, m)?)?;
    m.add_function(wrap_pyfunction!(backend_info, m)?)?;
    Ok(())
}

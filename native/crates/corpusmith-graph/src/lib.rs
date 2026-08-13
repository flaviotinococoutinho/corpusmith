//! corpusmith-graph — CSR + Personalized PageRank + union-find +
//! Brandes (ADR-39). Identidade interna: u32 (interning no control
//! plane). A MATEMÁTICA espelha o kernel Python de referência
//! (kernel/graphwalk.py e kernel/topology.py): mesmo damping, mesma
//! regra de dangling, mesma normalização — testes diferenciais exigem
//! igualdade dentro de tolerância declarada.

use std::collections::VecDeque;

/// Grafo NÃO-direcionado em CSR: `offsets: Vec<u64>`, `targets:
/// Vec<u32>`, `weights: Vec<f32>` (contrato §7 da spec). Imutável após
/// construção — o snapshot de cache é seguro entre threads.
pub struct Csr {
    pub n: usize,
    pub offsets: Vec<u64>,
    pub targets: Vec<u32>,
    pub weights: Vec<f32>,
    /// soma dos pesos de saída por nó (f64: acumulação estável)
    pub out_weight: Vec<f64>,
}

impl Csr {
    /// Constrói do lote de arestas (src, dst, w) espelhando cada aresta
    /// (não-direcionado) e SOMANDO pesos de arestas repetidas — mesma
    /// semântica do dict Python `adjacency[a][b] += w`.
    pub fn from_edges(sources: &[u32], targets_in: &[u32], weights_in: &[f32],
                      n: usize) -> Result<Csr, corpusmith_types::ComputeError> {
        if sources.len() != targets_in.len()
            || sources.len() != weights_in.len() {
            return Err(corpusmith_types::ComputeError::InvalidInput(
                "src/dst/w com tamanhos diferentes".into()));
        }
        // agrega paralelas (a,b) somando peso, em espaço de pares
        use std::collections::HashMap;
        let mut merged: HashMap<(u32, u32), f64> = HashMap::new();
        for i in 0..sources.len() {
            let (a, b, w) = (sources[i], targets_in[i], weights_in[i] as f64);
            if a as usize >= n || b as usize >= n {
                return Err(corpusmith_types::ComputeError::InvalidInput(
                    format!("nó {} fora de 0..{}", a.max(b), n)));
            }
            *merged.entry((a, b)).or_insert(0.0) += w;
            *merged.entry((b, a)).or_insert(0.0) += w;
        }
        let mut degree = vec![0u64; n];
        for (a, _) in merged.keys() {
            degree[*a as usize] += 1;
        }
        let mut offsets = vec![0u64; n + 1];
        for i in 0..n {
            offsets[i + 1] = offsets[i] + degree[i];
        }
        let m = offsets[n] as usize;
        let mut targets = vec![0u32; m];
        let mut weights = vec![0f32; m];
        let mut cursor: Vec<u64> = offsets[..n].to_vec();
        // ordena vizinhos por id (determinismo de iteração)
        let mut entries: Vec<(u32, u32, f64)> = merged
            .into_iter().map(|((a, b), w)| (a, b, w)).collect();
        entries.sort_unstable_by_key(|(a, b, _)| (*a, *b));
        for (a, b, w) in entries {
            let at = cursor[a as usize] as usize;
            targets[at] = b;
            weights[at] = w as f32;
            cursor[a as usize] += 1;
        }
        let mut out_weight = vec![0f64; n];
        for v in 0..n {
            let (lo, hi) = (offsets[v] as usize, offsets[v + 1] as usize);
            out_weight[v] = weights[lo..hi].iter()
                .map(|w| *w as f64).sum();
        }
        Ok(Csr { n, offsets, targets, weights, out_weight })
    }

    pub fn edges_undirected(&self) -> u64 {
        self.offsets[self.n] / 2
    }
}

/// Personalized PageRank — power iteration idêntica em estrutura ao
/// kernel Python: p ← (1−d)·s + d·(Wᵀp + dangling·s). `outside_restart`
/// agrega a massa de seeds FORA do grafo num nó virtual sem arestas
/// (equivalência exata para os scores dos nós reais). Devolve top_k
/// (score desc, id asc) apenas de nós REAIS.
pub fn ppr(csr: &Csr, seed_ids: &[u32], seed_weights: &[f64],
           outside_restart: f64, damping: f64, iterations: u32,
           tolerance: f64, top_k: usize) -> Vec<(u32, f64)> {
    let n = csr.n;
    let total_seed: f64 = seed_weights.iter().filter(|w| **w > 0.0).sum::<f64>()
        + outside_restart.max(0.0);
    if total_seed <= 0.0 || (n == 0 && outside_restart <= 0.0) {
        return Vec::new();
    }
    // nó virtual n = massa fora do grafo (dangling por construção)
    let total = n + 1;
    let mut restart = vec![0f64; total];
    for (i, id) in seed_ids.iter().enumerate() {
        if seed_weights[i] > 0.0 {
            restart[*id as usize] += seed_weights[i] / total_seed;
        }
    }
    restart[n] = outside_restart.max(0.0) / total_seed;
    let mut rank = restart.clone();
    let mut incoming = vec![0f64; total];
    for _ in 0..iterations {
        incoming.iter_mut().for_each(|x| *x = 0.0);
        for v in 0..n {
            if csr.out_weight[v] <= 0.0 {
                continue;
            }
            let spread = rank[v] / csr.out_weight[v];
            let (lo, hi) = (csr.offsets[v] as usize,
                            csr.offsets[v + 1] as usize);
            for e in lo..hi {
                incoming[csr.targets[e] as usize]
                    += spread * csr.weights[e] as f64;
            }
        }
        let mut dangling = rank[n];             // virtual é sempre dangling
        for v in 0..n {
            if csr.out_weight[v] <= 0.0 {
                dangling += rank[v];
            }
        }
        let mut delta = 0.0;
        for v in 0..total {
            let updated = (1.0 - damping) * restart[v]
                + damping * (incoming[v] + dangling * restart[v]);
            delta += (updated - rank[v]).abs();
            rank[v] = updated;
        }
        if delta < tolerance {
            break;
        }
    }
    let mut scored: Vec<(u32, f64)> = (0..n)
        .map(|v| (v as u32, rank[v]))
        .filter(|(_, s)| *s > 0.0)
        .collect();
    scored.sort_unstable_by(|a, b| b.1.partial_cmp(&a.1)
        .unwrap_or(std::cmp::Ordering::Equal)
        .then(a.0.cmp(&b.0)));
    if top_k > 0 {
        scored.truncate(top_k);
    }
    scored
}

/// Componentes conexos via union-find; rótulo = MENOR id do componente
/// (mesmo critério determinístico da referência Python).
pub fn components(csr: &Csr) -> Vec<u32> {
    let mut parent: Vec<u32> = (0..csr.n as u32).collect();
    fn find(parent: &mut [u32], mut x: u32) -> u32 {
        while parent[x as usize] != x {
            parent[x as usize] = parent[parent[x as usize] as usize];
            x = parent[x as usize];
        }
        x
    }
    for v in 0..csr.n {
        let (lo, hi) = (csr.offsets[v] as usize, csr.offsets[v + 1] as usize);
        for e in lo..hi {
            let (ra, rb) = (find(&mut parent, v as u32),
                            find(&mut parent, csr.targets[e]));
            if ra != rb {
                let (hi_r, lo_r) = if ra > rb { (ra, rb) } else { (rb, ra) };
                parent[hi_r as usize] = lo_r;
            }
        }
    }
    (0..csr.n as u32).map(|v| find(&mut parent, v)).collect()
}

/// Brandes (não-ponderado, não-direcionado) normalizado em [0,1] com o
/// MESMO fator da referência (1/((n−1)(n−2)), n = nós com grau ≥ 1).
pub fn brandes(csr: &Csr) -> Vec<(u32, f64)> {
    let active: Vec<u32> = (0..csr.n as u32)
        .filter(|v| csr.offsets[*v as usize + 1] > csr.offsets[*v as usize])
        .collect();
    let n_active = active.len();
    let mut centrality = vec![0f64; csr.n];
    let mut sigma = vec![0f64; csr.n];
    let mut dist = vec![-1i64; csr.n];
    let mut delta = vec![0f64; csr.n];
    let mut preds: Vec<Vec<u32>> = vec![Vec::new(); csr.n];
    for &source in &active {
        sigma.iter_mut().for_each(|x| *x = 0.0);
        dist.iter_mut().for_each(|x| *x = -1);
        delta.iter_mut().for_each(|x| *x = 0.0);
        preds.iter_mut().for_each(|p| p.clear());
        sigma[source as usize] = 1.0;
        dist[source as usize] = 0;
        let mut stack: Vec<u32> = Vec::with_capacity(n_active);
        let mut queue = VecDeque::from([source]);
        while let Some(v) = queue.pop_front() {
            stack.push(v);
            let (lo, hi) = (csr.offsets[v as usize] as usize,
                            csr.offsets[v as usize + 1] as usize);
            for e in lo..hi {
                let w = csr.targets[e];
                if dist[w as usize] < 0 {
                    queue.push_back(w);
                    dist[w as usize] = dist[v as usize] + 1;
                }
                if dist[w as usize] == dist[v as usize] + 1 {
                    sigma[w as usize] += sigma[v as usize];
                    preds[w as usize].push(v);
                }
            }
        }
        while let Some(w) = stack.pop() {
            for &v in &preds[w as usize] {
                delta[v as usize] += (sigma[v as usize] / sigma[w as usize])
                    * (1.0 + delta[w as usize]);
            }
            if w != source {
                centrality[w as usize] += delta[w as usize];
            }
        }
    }
    let scale = if n_active > 2 {
        1.0 / ((n_active as f64 - 1.0) * (n_active as f64 - 2.0))
    } else {
        0.0
    };
    active.iter().map(|&v| (v, centrality[v as usize] * scale)).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn star() -> Csr {
        // centro 0 ligado a 1..=4
        Csr::from_edges(&[0, 0, 0, 0], &[1, 2, 3, 4],
                        &[1.0, 1.0, 1.0, 1.0], 5).unwrap()
    }

    #[test]
    fn ppr_mass_sums_to_one_over_all_nodes() {
        let g = star();
        let scores = ppr(&g, &[0], &[1.0], 0.0, 0.5, 20, 1e-9, 0);
        let total: f64 = scores.iter().map(|(_, s)| s).sum();
        assert!((total - 1.0).abs() < 1e-9, "soma={total}");
        assert!(scores.iter().all(|(_, s)| s.is_finite() && *s >= 0.0));
    }

    #[test]
    fn brandes_star_center_is_maximal() {
        let g = star();
        let c = brandes(&g);
        let center = c.iter().find(|(v, _)| *v == 0).unwrap().1;
        assert!((center - 1.0).abs() < 1e-12);
        for (v, s) in c {
            if v != 0 {
                assert!(s.abs() < 1e-12);
            }
        }
    }

    #[test]
    fn components_label_is_min_id() {
        let g = Csr::from_edges(&[0, 2], &[1, 3], &[1.0, 1.0], 5).unwrap();
        assert_eq!(components(&g), vec![0, 0, 2, 2, 4]);
    }
}

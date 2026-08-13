//! corpusmith-sketch — SimHash 64-bit + Hamming + 9 bandas LSH + pares
//! candidatos (ADR-39). PARIDADE BIT-A-BIT com kernel/sketch.py:
//! shingles de palavras (\w+ Unicode, minúsculas), blake2b com
//! digest_size=8 (parâmetro, não truncamento), votos por bit, bandas
//! com as MESMAS bordas round(i·64/9). Igualdade exata exigida por
//! teste diferencial.

use blake2::digest::{Update, VariableOutput};
use blake2::Blake2bVar;
use rayon::prelude::*;

pub const BITS: usize = 64;
pub const BAND_COUNT: usize = 9;

/// Caractere de palavra com a MESMA semântica do `\w` do CPython
/// (SRE_UNI_IS_WORD = Py_UNICODE_ISALNUM ∪ '_'), que equivale às
/// categorias gerais Unicode L* ∪ N* ∪ '_'. Dois achados de property
/// test motivaram a tabela explícita: o `\w` do crate regex NÃO cobre
/// No (ex.: '²'), e `char::is_alphabetic` (propriedade Alphabetic)
/// cobre A MAIS marcas Other_Alphabetic (ex.: U+11F00) que o Python
/// não considera. Paridade bit-a-bit exige o predicado exato.
fn is_word_char(c: char) -> bool {
    use unicode_general_category::{get_general_category, GeneralCategory};
    matches!(get_general_category(c),
             GeneralCategory::UppercaseLetter
             | GeneralCategory::LowercaseLetter
             | GeneralCategory::TitlecaseLetter
             | GeneralCategory::ModifierLetter
             | GeneralCategory::OtherLetter
             | GeneralCategory::DecimalNumber
             | GeneralCategory::LetterNumber
             | GeneralCategory::OtherNumber)
        || c == '_'
}

fn words(text: &str) -> Vec<String> {
    let lowered = text.to_lowercase();
    let mut out = Vec::new();
    let mut current = String::new();
    for c in lowered.chars() {
        if is_word_char(c) {
            current.push(c);
        } else if !current.is_empty() {
            out.push(std::mem::take(&mut current));
        }
    }
    if !current.is_empty() {
        out.push(current);
    }
    out
}

fn shingles(text: &str, size: usize) -> Vec<String> {
    let words = words(text);
    if words.is_empty() {
        return Vec::new();
    }
    if words.len() < size {
        return vec![words.join(" ")];
    }
    (0..=words.len() - size)
        .map(|i| words[i..i + size].join(" "))
        .collect()
}

fn blake2b_u64(piece: &str) -> u64 {
    let mut hasher = Blake2bVar::new(8).expect("digest_size=8");
    hasher.update(piece.as_bytes());
    let mut out = [0u8; 8];
    hasher.finalize_variable(&mut out).expect("finalize");
    u64::from_be_bytes(out)
}

/// SimHash 64-bit — mesma construção do kernel Python (votos por bit).
pub fn simhash(text: &str, shingle: usize) -> u64 {
    let mut votes = [0i64; BITS];
    for piece in shingles(text, shingle) {
        let digest = blake2b_u64(&piece);
        for (bit, vote) in votes.iter_mut().enumerate() {
            *vote += if (digest >> bit) & 1 == 1 { 1 } else { -1 };
        }
    }
    let mut value = 0u64;
    for (bit, vote) in votes.iter().enumerate() {
        if *vote > 0 {
            value |= 1u64 << bit;
        }
    }
    value
}

/// Lote paralelo (rayon) — a ordem da SAÍDA segue a ordem da entrada.
pub fn simhash_batch(texts: &[String], shingle: usize) -> Vec<u64> {
    texts.par_iter().map(|t| simhash(t, shingle)).collect()
}

pub fn hamming(a: u64, b: u64) -> u32 {
    (a ^ b).count_ones()
}

/// Bordas das 9 bandas: round(i·64/9) — MESMA fórmula do Python
/// (sem empates .5, logo round() coincide). Tabela: 0,7,14,21,28,36,
/// 43,50,57,64 (larguras 7,7,7,7,8,7,7,7,7).
pub fn band_edges() -> [u32; BAND_COUNT + 1] {
    let mut edges = [0u32; BAND_COUNT + 1];
    for (i, e) in edges.iter_mut().enumerate() {
        *e = ((i as f64) * (BITS as f64) / (BAND_COUNT as f64)).round() as u32;
    }
    edges
}

/// (índice, valor) de cada banda — chave de bucket LSH.
pub fn bands(value: u64) -> [(u32, u64); BAND_COUNT] {
    let edges = band_edges();
    let mut out = [(0u32, 0u64); BAND_COUNT];
    for i in 0..BAND_COUNT {
        let width = edges[i + 1] - edges[i];
        let mask = if width >= 64 { u64::MAX } else { (1u64 << width) - 1 };
        out[i] = (i as u32, (value >> edges[i]) & mask);
    }
    out
}

/// Pares (i<j) com hamming ≤ max_hamming via baldes de banda + re-
/// verificação. EXATO por casa de pombos para max_hamming ≤ 8 com 9
/// bandas. Saída ordenada e única (SoA: dois vetores paralelos).
pub fn candidate_pairs(sketches: &[u64], max_hamming: u32)
                       -> (Vec<u32>, Vec<u32>) {
    use std::collections::HashMap;
    let mut buckets: HashMap<(u32, u64), Vec<u32>> = HashMap::new();
    for (i, sk) in sketches.iter().enumerate() {
        for band in bands(*sk) {
            buckets.entry(band).or_default().push(i as u32);
        }
    }
    let mut seen: std::collections::BTreeSet<(u32, u32)> =
        std::collections::BTreeSet::new();
    for members in buckets.values() {
        for a in 0..members.len() {
            for b in a + 1..members.len() {
                let pair = (members[a], members[b]);
                if !seen.contains(&pair)
                    && hamming(sketches[pair.0 as usize],
                               sketches[pair.1 as usize]) <= max_hamming {
                    seen.insert(pair);
                }
            }
        }
    }
    let mut ai = Vec::with_capacity(seen.len());
    let mut bi = Vec::with_capacity(seen.len());
    for (a, b) in seen {
        ai.push(a);
        bi.push(b);
    }
    (ai, bi)
}

/// Jaccard racional sobre listas ORDENADAS de ids (interseção/união).
pub fn jaccard_sorted(a: &[u64], b: &[u64]) -> f64 {
    if a.is_empty() && b.is_empty() {
        return 0.0;
    }
    let (mut i, mut j, mut inter) = (0usize, 0usize, 0usize);
    while i < a.len() && j < b.len() {
        match a[i].cmp(&b[j]) {
            std::cmp::Ordering::Equal => { inter += 1; i += 1; j += 1; }
            std::cmp::Ordering::Less => i += 1,
            std::cmp::Ordering::Greater => j += 1,
        }
    }
    let union = a.len() + b.len() - inter;
    inter as f64 / union as f64
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn band_edges_match_reference_table() {
        assert_eq!(band_edges(), [0, 7, 14, 21, 28, 36, 43, 50, 57, 64]);
    }

    #[test]
    fn hamming_properties() {
        assert_eq!(hamming(42, 42), 0);
        assert_eq!(hamming(1, 2), hamming(2, 1));
    }

    #[test]
    fn pigeonhole_low_hamming_shares_a_band() {
        // difere em 8 bits ⇒ ao menos uma das 9 bandas idêntica
        let a = 0xDEAD_BEEF_CAFE_F00Du64;
        let b = a ^ 0b1111_1111u64;              // 8 bits nos primeiros 7+1
        let ba = bands(a);
        let bb = bands(b);
        assert!(ba.iter().zip(bb.iter()).any(|(x, y)| x == y));
    }

    #[test]
    fn jaccard_in_unit_interval() {
        let j = jaccard_sorted(&[1, 2, 3], &[2, 3, 4]);
        assert!((0.0..=1.0).contains(&j));
        assert!((j - 0.5).abs() < 1e-12);
    }

    #[test]
    fn candidate_pairs_finds_near_duplicates() {
        let base = simhash("memoria conhecimento grafo indice retrieval \
                            abstencao entidade curadoria", 3);
        let (a, b) = candidate_pairs(&[base, base, !base], 8);
        assert_eq!((a, b), (vec![0], vec![1]));
    }
}

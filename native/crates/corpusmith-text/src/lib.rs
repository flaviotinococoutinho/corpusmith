//! corpusmith-text — ALVO da Fase 3 (ADR-39): chunking, parsing de
//! links, masking de spans protegidos, Aho–Corasick para gazetteer e
//! extratores (datas/quantidades/identificadores). NESTA entrega o
//! crate define apenas os TIPOS do lote — a extração continua no
//! Python de referência (normalize/), e Rust NÃO reescreve conteúdo
//! canônico em nenhuma fase.

/// Um documento do lote de extração (SoA no protocolo; aqui o registro).
#[derive(Debug, Clone)]
pub struct DocumentRef {
    pub doc_id: u32,
    pub rel_path: String,
    pub bytes: u64,
}

/// Plano fechado da Fase 3 (ordem de migração):
/// 1. chunking determinístico (limite 1200 chars por parágrafos);
/// 2. parse de links markdown + resolução interna;
/// 3. masking de regiões protegidas (fences/inline/quotes/Citations);
/// 4. Aho–Corasick sobre o gazetteer compilado;
/// 5. extratores de datas/quantidades/identificadores/normas.
/// Critério de entrada: benchmark da Fase 0 apontando extração como
/// hotspot dominante do índice E testes diferenciais byte-idênticos.
pub const PHASE3_PLAN: &str = "chunking→links→masking→aho-corasick→extratores";

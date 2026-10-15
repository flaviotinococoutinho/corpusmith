# 07 · Sinergias — combinar e extrair o melhor dos conceitos

> **Altitude:** fluxo · **Status:** vivo

> Os conceitos não são features isoladas: formam um sistema com laços.
> Este documento mapeia as interações (quem alimenta quem), as receitas
> de composição prontas e os pontos de extensão seguros.

## 1. O diagrama de laços

```
                       ┌────────────────────────────────────────────┐
                       │                 HUMANO                     │
                       │  promove · julga (✅🚫✏️) · cura grafias   │
                       └───────┬──────────────┬─────────────┬───────┘
                               ▼              ▼             ▼
   fontes raw/ ──► SANDUÍCHE ──► BUNDLE OKF (Git) ◄── authority_records
                     │   ▲          │
     anexo PRÉ ──────┘   │          ▼
                         │      REBUILD INDEX ──► chunks · entidades · níveis · arestas
   reconciliação ◄───────┘          │
   (id forte→NCD→LLM)               ▼
                                RETRIEVAL (RRF×crédito×overlay×as_of)
                                    │            ▲            ▲
                                    ▼            │            │
                                RESPOSTA ──► DESFECHO ──► Hedge (streams)
                                (uncertainty)    │
                                                 ▼
                                        REFLECT ──► overlay · heat ──┐
                                                 │                   │
                                        correção ▼                   ▼
                                        (inbox) volta            ranking
                                        ao sanduíche             do ask
```

Três laços fechados: **curadoria** (authority → grafia → menos entropia →
melhor fusão de entidades → melhor reconciliação), **julgamento**
(desfecho → Hedge + overlay → ranking), **correção** (nota → inbox →
sanduíche → página nova).

## 2. Matriz de interação (quem amplifica quem)

| ↓ alimenta → | Normalização | Reconciliação | Retrieval | Grafo | Reflect/Heat | Eval |
|---|---|---|---|---|---|---|
| **Normalização** | idempotência | ids fortes + entidades p/ Jaccard | stream de entidades; anexo ISO p/ as_of; simetria pergunta↔memória | co-menção de entidades = arestas inferred | — | categorias temporal/update dependem do anexo |
| **Reconciliação** | — | log auditável | menos duplicatas ⇒ menos diluição de score | menos nós duplicados ⇒ comunidades limpas | UPDATE concentra heat numa página só | update: a página certa é atualizada |
| **Bi-temporalidade** | datas anotadas viram valid_at | SUPERSEDE grava invalid_at | filtro as_of | — | — | categoria temporal |
| **Confiança (escala)** | decide reescrita×anexo | confidence da decisão | — | pesos 1.0/0.5/0.15 | — | — |
| **Desfechos** | correção vira fonte | — | Hedge nos streams; overlay nas páginas | — | heat.outcome; overlay | — |
| **Topologia (pontes)** | — | — | — | diagnóstico de curadoria | candidatos a linkar | — |
| **Autoridade (bundle)** | gazetteer estendido | entidades melhores ⇒ Jaccard melhor | entidades melhores ⇒ stream melhor | fusão de nós por QID (futuro) | — | — |

A matriz mostra dependências entre os mecanismos. Por exemplo, uma grafia
canônica pode melhorar a correspondência de entidades usada na reconciliação
e na recuperação. O efeito deve ser avaliado no corpus usado.

## 3. Receitas de composição

### R1 — "Minha base está fragmentada em duplicatas"
1. Cure `authority_records` para os termos que aparecem com variantes
   (o Explorer com filtro de autoridade + `/cockpit/authorities` mostra
   os usos).
2. Execute `corpusmith okf index` para reanotar com o novo gazetteer.
3. Recompile as fontes que precisam de revisão e confira `reconcile_log`.
   A mudança pode alterar a similaridade, mas não garante uma decisão `UPDATE`.

### R2 — "As respostas estão confiantes demais"
1. Adicione casos `expect_abstain` ao golden set com perguntas sem cobertura.
2. Avalie a configuração atual com `eval_memory`.
3. Ajuste `ask.abstain_threshold` gradualmente e compare os resultados.
   O score RRF não é probabilidade de verdade.
4. Inspecione as evidências e `uncertainty`, que mede dispersão do ranking.
   Entropia baixa também pode acompanhar uma resposta incorreta.

### R3 — "Quero que o retrieval aprenda meu jeito de perguntar"
Registre os desfechos das consultas. O mecanismo atualiza `stream_weights`
a partir dos streams que contribuíram para as páginas julgadas. Não há
prazo de convergência ou garantia de melhoria; o contrato é `heuristic`.

Inspecione os pesos com `SELECT * FROM stream_weights`. Para reiniciá-los,
use `POST /cockpit/behavior/reset-streams` em vez de editar o banco. A API
usa a autenticação descrita na [referência](06-referencia.md).

### R4 — "Dois temas da minha base não conversam"
Painel Qualidade → 🌉 pontes frágeis. Cada ponte lista o par de blocos e
o peso do fio. Ações: promover uma página-conceito que ligue os dois
temas (com links para ambos) ou adicionar links nas páginas existentes.
Rodar `leiden` de novo: a ponte deve engrossar ou sumir da lista.

### R5 — "Fato mudou no mundo (troquei de stack, mudou a lei)"
NUNCA editar a página antiga destrutivamente. Compilar/promover a nova;
se o reconciliador não decidir SUPERSEDE sozinho, gravar na antiga
`superseded_by` + `invalid_at` (ou `mark_stale` se for tempo de código).
Teste de aceitação natural: `ask "... em <data antiga>"` responde o
velho; sem data, responde o novo. Adicionar caso `temporal` no golden.

### R6 — "Quero um novo tipo de página gerada por máquina"
Herdar de `MachinePageUseCase`, implementar `_produce()` (e opcionalmente
`_reconcile`/`_after_write`). O esqueleto executa a normalização, a validação e a escrita versionada.
O teste de arquitetura verifica que a subclasse não redefine `execute()`.
Registrar o job no REGISTRY e expor via facade.

### R7 — "Quero um novo sinal de retrieval"
Implementar como stream: lista de hits `{id, page, text, ...}` e
`streams.add("meu_sinal", hits)` no AskMemory. O RRF absorve qualquer
escala (só usa posições); o Hedge passa a treinar o crédito do sinal
novo automaticamente (aparece em `ask_provenance`/`stream_weights` sem
código extra).

### R8b — "Meu inbox acumula notas soltas do mesmo assunto"
Deixe o `consolidate_inbox` (diário) agir: notas que compartilham
identificador forte ou ≥2 entidades canônicas viram UMA página
consolidada com `sources` rastreados — uma chamada de LLM por cluster.
Notas sem recorrência ficam pendentes (compile individual continua
disponível). A curadoria de authority_records (R1) melhora diretamente o
clustering: mais aliases mapeados ⇒ mais recorrência detectada.

### R8c — "Depreciei uma página; o que mais fica suspeito?"
O retorno do `mark_stale` lista os `dependents` (quem cita a página).
Revise-os na ordem; se a informação deles se apoiava só na depreciada,
marque-os também ou atualize os links para a sucessora. O
`policy.contradiction_candidate` no lint pega o caso complementar: duas
versões da mesma verdade convivendo sem sucessão declarada.

### R8 — "Quero medir se uma mudança melhorou a memória"
1. Fixe um golden set com cobertura das categorias relevantes e registre
   seu tamanho e suas limitações.
2. Execute `eval_memory` antes e depois. Compare `eval_runs` e os envelopes.
3. Para mudanças de recuperação, compare recall, MRR, abstenção e latência.
   Observe também `uncertainty`, sem tratar sua redução como melhoria
   automática de correção factual.

## 4. Tensões conhecidas (trade-offs deliberados)

| Tensão | Escolha do projeto | Quando reconsiderar |
|---|---|---|
| Precisão × recall na reescrita | precisão (só `extracted`) | nunca — anote em vez de reescrever |
| Fundir × duplicar (reconcile) | duplicar na dúvida (ADD) | se `reconcile_log` mostrar ADDs em série do mesmo objeto, calibrar HI/LO |
| Abster × responder | responder com `uncertainty` visível; abster só sem evidência | subir threshold quando o custo de resposta errada > custo de silêncio |
| Hedge agressivo × estável | η=0.25 com clamp | η maior só com volume alto de desfechos |
| Verbatim × resumo | resumo com fonte por sha + anexo estruturado | fontes curtas podem ir verbatim (passthrough já faz isso) |
| Local × API | local por default; API é opt-in duplo (privacy + budget) | — |

## 5. Pontos de extensão seguros (e os perigosos)

**Seguros** (protegidos por contrato/teste):
- novo detector em `normalize/detectors/` (puro; entra no engine e no
  anexo automaticamente);
- novo `authority_record` no bundle (é um commit);
- novo stream de retrieval (R7); novo use case de página (R6);
- nova regra de política em `local_policy.check` (com golden test);
- novas colunas via `_migrate` (idempotente).

**Perigosos** (exigem revisão dos invariantes):
- mudar o esqueleto de `MachinePageUseCase.execute` (todos os produtores
  de página passam por ali);
- mudar `protected_spans` (risco de reescrever código/citações);
- mudar a semântica de `confidence` (pesa em grafo, reescrita,
  reconciliação e anexo ao mesmo tempo);
- escrever no bundle fora do `BundleWriter` (quebra lock/log/commit).

## 6. Norte para evoluções futuras

Candidatos alinhados com a arquitetura (cada um é um stream, um hook ou
uma página — nunca um subsistema paralelo): fusão de entidades por QID
entre authority_records; embeddings como stream `dense` de verdade
(sqlite-vec); persistência 1-dim (ciclos = redundância de caminhos)
como métrica de robustez; bandit contextual no lugar do Hedge quando
houver volume; export do bundle como grafo RDF via QIDs (o OKF já é
tripla implícita página→predicado→página).

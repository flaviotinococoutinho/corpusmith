# _estudo_dev

Portal local-first de estudo para Backend Java/Kotlin Senior/Staff.

A pasta transforma a apostila em um sistema navegável: ontologia de conceitos, trilhas, evidências, perguntas, laboratórios, comandos e checkpoint. O conteúdo canônico fica separado do progresso pessoal; a interface é uma projeção descartável e reconstruível.

## Abrir

Abra `index.html` diretamente no navegador. O portal usa scripts clássicos e referências relativas, portanto funciona por `file://` e também em qualquer servidor estático.

Para servir por HTTP local, qualquer servidor de arquivos funciona, por exemplo:

```bash
python3 -m http.server 8080 --directory _estudo_dev
```

Depois abra `localhost:8080` no navegador. O endereço acima é apenas um exemplo local; o pacote não contém links externos completos.

## Estrutura

```text
_estudo_dev/
├── index.html
├── assets/
│   ├── app.js
│   └── styles.css
├── data/
│   ├── catalog.js
│   ├── plan.js
│   ├── questions.js
│   ├── commands.js
│   └── references.js
└── docs/
    ├── ontology.md
    ├── epistemology.md
    ├── portability.md
    ├── content-contract.md
    └── qa.md
```

## Princípios

1. **Conceito não é afirmação.** Um nó organiza conhecimento; uma claim precisa de escopo, confiança e evidência.
2. **Fonte não vira verdade por estar catalogada.** Evidência pode apoiar, contextualizar ou desafiar.
3. **Progresso cognitivo não altera o conteúdo canônico.** Notas, erros e revisões ficam somente no navegador.
4. **Projeções são descartáveis.** A interface pode evoluir sem reescrever os dados.
5. **Validade é temporal.** Tecnologia dependente de versão deve declarar revisão e escopo.
6. **Privacidade por separação física.** Documentos pessoais aparecem apenas como registros locais; o pacote não inclui cartas, seguros, identificadores ou arquitetura confidencial.
7. **iFood público ≠ stack universal da empresa.** Referências públicas são datadas e limitadas ao sistema ou vaga descritos.

## Recursos

- mapa ontológico em SVG, com alternativa textual;
- catálogo de 203 conceitos em 15 módulos;
- busca e filtros locais;
- plano de 21 dias com revisões R0/R1/R3/R7/R14;
- simulador de entrevista com cronômetro de 120 segundos;
- respostas progressivas e régua 0–4;
- cartões de comandos com risco operacional;
- ledger explícito de 15 claims, evidências e fontes;
- catálogo de 38 referências públicas por identificador relativo;
- 99 cartões de comandos com risco e versão;
- checkpoint, exportação e importação de progresso;
- tema claro, escuro e alto contraste;
- funcionamento offline, sem CDN, analytics, fontes ou requisições remotas.

## Atalhos

- `/`: busca global
- `g`: mapa
- `c`: conceitos
- `t`: trilhas
- `i`: entrevistas
- `Esc`: fechar diálogo ou limpar foco

## Evolução do conteúdo

Adicione conceitos em `data/catalog.js` preservando IDs. Use relações tipadas e evite duplicar um conceito em dois módulos proprietários. Para uma mudança incompatível, crie um novo ID e marque `supersedes`.

Execute `npm run validate` antes de publicar. O validador não possui dependências externas e confere contagens, IDs, relações, fontes, caminhos e sintaxe.

Antes de publicar, confira:

- IDs únicos;
- relações resolvidas;
- nenhuma URL absoluta;
- toda afirmação factual com fonte;
- nenhuma informação pessoal no perfil compartilhável;
- teclado, foco, reflow a 320 px e zoom de 200%;
- exportação seguida de importação preservando o estado.

Veja os contratos em `docs/`.

## Proveniência

O seed foi sintetizado a partir da apostila Backend Java/Kotlin Senior/Staff, do plano de 21 dias, de documentos profissionais autorizados e de referências técnicas catalogadas. Repositórios comunitários são tratados como rotas de prática, não como prova sobre uma empresa ou processo seletivo.

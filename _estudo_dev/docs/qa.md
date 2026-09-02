# Contrato de QA

Falhas de integridade, privacidade, acessibilidade ou perda de progresso bloqueiam a publicação.

## Gates automáticos

| Gate | Critério |
|---|---|
| Conteúdo | 15 módulos, 203 conceitos, 105 questões e 21 dias |
| Identidade | IDs únicos; zero relação órfã |
| Epistemologia | fato com fonte, escopo e confiança; inferência visível |
| Caminhos | zero URL absoluta, caminho de máquina ou `..` |
| Privacidade | zero dado pessoal no perfil compartilhável |
| Segurança | zero `eval`, handler inline, analytics ou conexão externa |
| Importação | schema 1.0.0; rejeição atômica de JSON inválido e prototype pollution |
| Console | zero erro e zero promise rejeitada |

## Matriz visual

- 320 × 568;
- 360 × 800;
- 768 × 1024;
- 1024 × 768;
- 1440 × 900;
- zoom 100% e 200%;
- temas claro, escuro e alto contraste;
- `prefers-reduced-motion`;
- navegação somente por teclado.

## WCAG 2.2 AA

- `lang="pt-BR"`, landmarks e skip link;
- contraste 4,5:1 para texto e 3:1 para componentes;
- foco visível e ordem previsível;
- ações com pelo menos 44 × 44 px no portal;
- diálogos fecham com Escape e devolvem foco;
- atualização de busca e cronômetro usa região viva;
- grafo visual possui lista DOM equivalente;
- nenhuma informação depende apenas de cor;
- reflow a 320 px sem rolagem horizontal da página.

## Cenários manuais críticos

1. abrir `index.html` sem rede;
2. navegar por todas as rotas hash;
3. buscar com e sem acento;
4. filtrar catálogo e comandos;
5. selecionar módulo pelo SVG e pela lista textual;
6. responder pergunta, usar cronômetro e registrar nota;
7. salvar checkpoint com evidência relativa;
8. exportar, limpar e importar o progresso;
9. recusar URL absoluta como evidência;
10. copiar a pasta para outro nome e repetir o teste.

## Performance

O seed atual deve responder instantaneamente. Ao ultrapassar 2.000 itens:

- paginar ou virtualizar listas;
- construir índice de busca em worker;
- desenhar apenas subgrafo ou vizinhança;
- preservar a lista textual como modo degradado;
- evitar layout de força síncrono sobre o grafo completo.

Metas de evolução: busca p95 abaixo de 150 ms em 2.000 itens e modo navegável com 10.000 nós/30.000 arestas.

## Limite desta entrega

A ausência de runtime de navegador no ambiente de geração impede afirmar Lighthouse, axe e testes multi-engine. O código deve passar por esses gates antes de merge em `main`; a branch isolada permite essa revisão sem afetar o repositório principal.

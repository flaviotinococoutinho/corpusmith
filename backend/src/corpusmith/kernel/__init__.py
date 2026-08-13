"""kernel/ — o núcleo IMUTÁVEL do projeto (v0.9).

Regra de dependência (functional core, imperative shell):
  kernel  →  nada além da stdlib pura (sem I/O, sem rede, sem disco)
  domain  (okf/, harness/, normalize/)  →  kernel
  usecases/  →  domain + infra via injeção
  facades/   →  usecases
  adapters   (jobs/, api/, cli, daemon)  →  facades

A pureza do kernel (e do normalize/) é GARANTIDA por teste de arquitetura
(tests/test_architecture.py): qualquer import de sqlite3/httpx/subprocess/
fastapi/git aqui quebra a suíte. Isto separa fisicamente o que muda pouco
(matemática, invariantes) do que muda muito (endpoints, schemas, painéis).
"""

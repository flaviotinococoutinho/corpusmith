"""usecases/ — camada de aplicação (v0.9).

Cada caso de uso é UMA operação do domínio com UM método público
(`execute()`), dependências pelo construtor — regra garantida por teste de
arquitetura. Os adapters (jobs/, api/, cli) nunca chamam use cases
diretamente: passam pelas facades/ que os orquestram.
"""

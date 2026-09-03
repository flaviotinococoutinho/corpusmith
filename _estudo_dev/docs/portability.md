# Portabilidade e offline

## Decisão

O portal usa HTML, CSS, JavaScript clássico e SVG nativos. Isso evita runtime remoto, CDN e etapa obrigatória de build. Arquivos podem ser copiados, versionados, compactados ou servidos por qualquer servidor estático.

## Caminhos

Todos os recursos usam caminhos relativos. O conteúdo não contém:

- `http:` ou `https:`;
- caminhos iniciados por `/`;
- `file:`;
- caminhos com `..`;
- caminho absoluto do computador.

Referências externas são registradas por título, organização, identificador pesquisável e data. O navegador não faz requisições a elas.

## Perfis

- **Compartilhável:** conhecimento público e exemplos simulados.
- **Pessoal:** acrescenta progresso e evidências explicitamente autorizadas.
- **Restrito:** apenas placeholder local; nunca é empacotado.

O portal entregue é compartilhável. Progresso fica em `localStorage` e só sai do navegador por exportação manual.

## Backup

Use “Exportar progresso”. O arquivo contém versão de schema, notas, revisões e checkpoints. A importação valida formato e não executa conteúdo.

## Migração futura

Os dados atuais são scripts clássicos para compatibilidade com `file://`. Em um deploy HTTP, eles podem ser convertidos para JSON e indexados por MiniSearch; o adaptador do grafo pode ser substituído por Cytoscape.js. O contrato dos IDs e relações permanece o mesmo.

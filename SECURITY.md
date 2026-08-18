# Política de segurança

## Relatando uma vulnerabilidade

Use o recurso **Report a vulnerability** na aba Security deste repositório para
enviar o relato de forma privada. Não abra uma issue pública para uma
vulnerabilidade ainda não corrigida.

Inclua, quando possível:

- componente e versão ou commit afetado;
- passos mínimos de reprodução e impacto observado;
- condições necessárias para exploração;
- sugestão de correção ou mitigação, se houver.

Não inclua tokens reais, dados pessoais ou conteúdo privado de um corpus. Use
exemplos sintéticos e remova segredos de logs e capturas.

O projeto ainda não publica uma matriz formal de versões suportadas nem um SLA
de resposta. O mantenedor confirmará o recebimento pelo próprio relato privado
e coordenará divulgação e correção antes que os detalhes sejam publicados.

## Escopo de segurança

O Corpusmith é local-first: o daemon deve permanecer em loopback por padrão,
o token de handshake é efêmero e conteúdo marcado como `local_only` não deve
sair da máquina. Relatos de exposição remota, bypass de autenticação ou
privacidade, traversal, execução por conteúdo ingerido, escrita fora do
Harness, corrupção do bundle e vazamento de segredos estão dentro do escopo.

Para discussões públicas sobre endurecimento sem uma vulnerabilidade
explorável, abra uma issue sem dados sensíveis.

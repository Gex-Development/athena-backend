# Contrato de API v0

Contrato entre o Athena Front e o Athena Backend, em OpenAPI 3.1. O Front gera os tipos dele a partir de `openapi.yaml`.

## Arquivos

- `openapi.yaml`: arquivo raiz, com versão, segurança e a lista de rotas.
- `componentes.yaml`: os schemas e as respostas que as rotas usam, dentro de `components`.
- `caminhos/`: as rotas, um arquivo por assunto. Entram nas próximas partes do contrato.

## Estabilidade

Cada rota tem `x-estabilidade`:

- `firme`: pode ser implementada sem dúvida. Muda só pela regra abaixo.
- `provisorio`: depende de uma task ainda aberta, que aparece na descrição da rota.

Firme não quer dizer que a rota já existe. A rota que já responde no backend tem `x-implementada: true`, e um teste confere que essa marcação bate com as rotas do backend nos dois sentidos.

## Regra de mudança

O contrato só muda por PR aprovada pelo dono do Front e pelo dono do Backend. Mudança que quebra quem já consome a rota sobe a versão do contrato e entra na descrição da PR como quebra de contrato.

## Convenções

- Datas em UTC, no formato ISO 8601.
- Erro sempre no formato `{"error": "...", "code": "..."}`, com `code` estável.
- Listas paginadas devolvem `itens` e `proximoCursor`, que vem nulo na última página.
- Valores em dólar com o sufixo `Usd`. A base da oferta é o valor sem impostos e sem frete.
- `conversaId` é sempre o ID da conversa no Chatwoot. A conversa do analista com a Athena no chat tem id próprio, em texto.

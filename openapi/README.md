# Contrato de API v0

Contrato entre o Athena Front e o Athena Backend, em OpenAPI 3.1. O Front gera os tipos dele a partir destes arquivos.

## Arquivos

- `athena-api-v0.yaml`: arquivo raiz, com versão, segurança e a lista de rotas.
- `caminhos/`: as rotas, um arquivo por assunto (sessão, chat, conversa, Command Center, controle, entrada).
- `componentes.yaml`: os schemas e as respostas que as rotas usam.

## Estabilidade

Cada rota tem `x-estabilidade`:

- `firme`: pode ser implementada sem dúvida. Muda só pela regra abaixo.
- `provisorio`: depende de uma task ainda aberta, que aparece na descrição da rota.

## Regra de mudança

O contrato só muda por PR aprovada pelo dono do Front e pelo dono do Backend. Mudança que quebra quem já consome a rota sobe a versão do contrato e entra na descrição da PR como quebra de contrato.

## Convenções

- Datas em UTC, no formato ISO 8601.
- Erro sempre no formato `{"error": "...", "code": "..."}`, com `code` estável.
- Listas paginadas devolvem `itens` e `proximoCursor`, que vem nulo na última página.
- Valores em dólar com o sufixo `Usd`. A base da oferta é o valor sem impostos e sem frete.

01/09 - fazer_backup() faz no maximo 1 backup por dia (throttle), nao um por
execucao. Sem rotacao/limite de quantidade ainda (fica pro futuro).

02/09 - taxas em transacoes = so corretagem/emolumentos (custo por operacao).
IR nao entra em transacoes: e calculado mensal e agregado (soma das vendas do
mes, compensacao de prejuizo, isencao ate R$20mil/mes), nao por transacao.
Quando for implementado, vira apuracao separada derivada de transacoes,
nao um campo na tabela.

- 02/09: .env foi encontrado fora do lugar (em exports/) e causou falha
  silenciosa de token em ambas as APIs por um tempo. Restaurado. Ainda falta
  o ajuste combinado em config.py para falhar de forma explicita se o
  token vier vazio (ver DECISOES.md).
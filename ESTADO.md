# Estado do projeto

Atualizado em: 26/10/2026
Referência de prioridade: seção 10 do PRD v1.2

Atualize este arquivo ao fim de cada tarefa e commite junto. Ele é o que te
orienta quando você voltar ao projeto depois de um tempo parado.

---

## Concluído

### Base (antes do backlog)
- [x] `config.py` — tokens das duas APIs carregados via `.env`
- [x] `coletor.py` — brapi (cotações) e BolsAI (fundamentos) funcionando
- [x] `banco.py` — SQLite com `cotacoes`, `fundamentos`, `posicoes`
- [x] Dedupe diário de fundamentos (`ja_tem_fundamento_hoje`)
- [x] Join entre as duas fontes por `ticker`
- [x] `whitelist.py` — universo dinâmico (base ∪ tickers em carteira)
- [x] `main.py` — loop de coleta em thread + CLI
- [x] `gerenciar_posicoes.py` — CLI de carteira com preço médio ponderado
- [x] `analise.py` — score fundamentalista, score de preço, score geral
- [x] `analise.ipynb` — descritiva, correlação, PCA, ADF, ACF/PACF, ARIMA

### Setup do fluxo de trabalho
- [x] `git init` + primeiro commit
- [x] `.gitignore` (`.env`, `*.db`, `__pycache__/`, `.ipynb_checkpoints/`,
      `exports/`)
- [x] `CLAUDE.md`, `ESTADO.md`, `DECISOES.md` e PRD na raiz

### Backlog
- [x] **P0-2** caminho absoluto do banco (`src/paths.py`) — commit c54ab82
- [x] **P0-6** backup automático do `.db` (throttle diário) — em `paths.py`
- [x] **P0-1** tabela `transacoes` + backfill das posições
- [x] **P0-3** coluna `data_hora_iso` nas três tabelas + script de migração
- [x] **P0-4** valuation via earnings yield e book-to-market — commit a253fbe
- [x] **P0-5** coleta automática restrita ao pregão (dias úteis, 10h–18h,
      horário de Brasília) — `esta_no_horario_de_pregao()` em `main.py`;
      feriados nacionais ficaram fora de propósito, ver §Restrições
- [x] `config.py` com caminho explícito do `.env` + falha imediata se faltar
      token
- [x] Limpeza da posição de teste TESTE3
- [x] Revisão da metodologia de score (PRD v1.2, seção 7A + DECISOES.md)
- [x] **P3-4** backfill de preços históricos — tabela `cotacoes_historicas`,
      `buscar_historico()` em `coletor.py` e `backfill_historico.py`, com
      `test_historico.py` (15 testes). Primeira carga: 819 linhas, 63 pregões
      por ticker, 28/07 a 23/10/2026. **Puxado fora da ordem do backlog**, a
      pedido, antes do P1-1.
- [x] **Benchmarks** (tarefa não prevista no PRD) — tabela `indices` com IBOV
      (brapi) e Selic/CDI (BCB, API aberta), `indices.py`,
      `backfill_indices.py` e `test_indices.py` (18 testes). 62 linhas por
      série, mesmo período da série de preços. `python indices.py` imprime a
      comparação de rendimento ação × IBOV × CDI.
- [x] **Correção:** o pregão do dia corrente deixou de ser gravado no
      histórico. A barra em formação vinha inconsistente da brapi e o
      `INSERT OR IGNORE` a congelaria errada para sempre — 13 linhas do dia
      26/10 foram removidas do banco. Ver DECISOES.md.

### Limpeza de 26/10/2026 (ao retomar o projeto)
Três coisas estavam fora do lugar depois de ~7 semanas parado:
- `ESTADO.md` no disco tinha regredido para a versão de 02/09; restaurado da
  versão commitada.
- `transacoes` estava vazia apesar do P0-1 constar como feito — provável
  restore de backup anterior ao backfill. `backfill_transacoes.py` e
  `migrar_datas_iso.py` rodados; 9 transações criadas.
- `COMANDOS.MD` nunca tinha entrado no git (o commit 81c2e7d só alterou o
  `CLAUDE.md`); agora versionado.

---

## Em andamento

- [ ] nada — próxima é **P1-1** (extrair score para `src/scoring.py`)

---

## Próximas tarefas — ORDEM REPRIORIZADA (PRD v1.2 §10)

A ordem mudou depois da revisão de metodologia. **P1-8 (ampliar whitelist)
saiu da frente**: com faixas absolutas, ampliar a lista deixa de recalibrar o
score inteiro, então não precisa mais vir antes dos ajustes de fórmula.
Todo o bloco de score vem **antes** do P1-4, para não gravar snapshots numa
escala que será trocada.

### Bloco de score (o miolo da revisão)
- [ ] **P1-1** extrair lógica de score de `analise.py` para `src/scoring.py`
      *Aceite:* `analise.py` importa de `scoring.py`; ranking sai igual.
- [ ] **P1-11** faixas absolutas para rentabilidade, margens, crescimento e
      segurança (substitui min-max) — PRD §7A.3 a §7A.6
      *Aceite:* mudar a whitelist não altera a nota de um ticker que não mudou.
      Inclui: separar margens de rentabilidade, dropar `margem_bruta` do score,
      cap de 30% no CAGR de lucro e descarte se ano-base ≤ 0.
- [ ] **P1-12** flag de setor por ticker; não pontuar dívida/PL, ROA e margens
      para financeiras (nota neutra + `nao_aplicavel`, nunca 0)
      *Aceite:* BBAS3 deixa de tirar 0.0 em segurança.
- [ ] **P1-13** remover `score_geral`; parar de imputar mediana em dado
      faltante e expor cobertura de indicadores
      *Aceite:* ranking mostra "7 de 11 indicadores" quando faltar dado.
- [ ] **P1-2** winsorização (p5/p95) + z-score no valuation
      *Aceite:* o pior colocado deixa de tirar exatamente 0.0.
- [ ] **P1-14** flag `premio_negativo` quando earnings yield < Selic

### Universo e reversão
- [ ] **P1-8** ampliar whitelist para 20–30 tickers
- [ ] **P1-3** janela explícita (252 pregões) + flag "dados insuficientes";
      renomear `score_preco` para `score_reversao`
      *Aceite:* com menos de 60 observações, retorna 50 com flag.
      **Bloqueado parcialmente:** o plano free da brapi entrega 3 meses (63
      pregões), não 252. A janela cheia só existe depois de uns 9 meses
      rodando `backfill_historico.py` periodicamente. Dá para implementar a
      flag agora e deixar a janela de 252 valendo quando a série alcançar.

### Carteira, sinais e histórico
- [ ] **P1-5** `carteira.py` — lucro absoluto, relativo, peso, resultado
      realizado
- [ ] **P1-6** `sinais.py` — compra/manter/venda com justificativa
- [ ] **P1-4** `snapshots_score` + job diário
- [ ] **P1-7** dashboard Streamlit (Visão geral, Ranking, Carteira)

Depois: P1-9, P1-10 e a faixa P2 (robustez).

---

## Travas e decisões

### Resolvidas (ver DECISOES.md)
- ~~**Q5**~~ — universo vs setor: resolvida parcialmente em 02/09. Sem massa
  para z-score setorial com 10–30 papéis; adotado marcar setor e não pontuar
  o inaplicável (P1-12).
- ~~**Q7**~~ — taxas e IR: resolvida em 02/09. `taxas` = só corretagem e
  emolumentos; IR é apuração mensal separada, fora de `transacoes`.
- ~~**Q2**~~ — janela do score de reversão: adotado 252 pregões, mínimo de 60
  observações (PRD §RF-05).

### Abertas
- **Q1** — tamanho alvo da whitelist. Afeta o P1-8 e a cota das APIs.
  Não bloqueia mais o bloco de score (faixas absolutas).
- **Q3** — PCA/ARIMA entram no score como terceiro componente ou ficam só no
  notebook?
- **Q4** — dividend yield: entra em rentabilidade ou vira categoria própria?
- **Q8** — com que frequência revisar as faixas absolutas conforme Selic e
  inflação? Qual o gatilho?
- **Q9** — vale adicionar momentum 6–12m, dado que o `score_reversao` aposta
  na direção oposta? Depende de série de preço mais longa.

---

## Restrições conhecidas (não são bugs)

- **brapi**: o plano gratuito sem token cobre só PETR4, VALE3, MGLU3 e ITUB4.
  Com token, a cobertura depende do plano contratado. Se um ticker novo falhar
  com "token não fornecido", verificar o plano antes de suspeitar do código.
- **BolsAI**: cota diária limitada no plano free. Fundamentos são coletados uma
  vez por dia por ticker justamente por isso.
- **brapi, histórico**: o plano `free` só aceita os ranges `1d, 5d, 1mo, 3mo`.
  De `6mo` para cima exige o plano Pro (R$ 139,99/mês, valor informado pela
  própria API na resposta 400). Logo o teto é 63 pregões por chamada, e a
  janela desliza: em 26/10/2026 o alcance começava em 28/07/2026. **O que
  passar da janela sem ter sido coletado é perda permanente neste plano** —
  por isso `backfill_historico.py` precisa rodar de tempos em tempos.
- **brapi, limite de requisições**: 20 por minuto, concorrência 1 (headers
  `ratelimit-limit` e `x-brapi-concurrency-limit`). O backfill espaça as
  chamadas em 3,5s por causa disso.
- **IFIX não tem histórico**: `IFIX.SA` aparece em `/available`, mas com
  `range=3mo` devolve um único ponto (a cotação do dia). Como metade da
  carteira é FII, o benchmark deles fica provisoriamente torto — comparar FII
  contra Ibovespa não é comparação justa. Fica registrado para a tarefa dos
  índices.

---

## Notas de operação

- Rodar coleta: `python src/main.py` → `checknow` força uma coleta
- Registrar operações: `python src/gerenciar_posicoes.py`
- Ver ranking: `python src/analise.py`
- **Estender a série histórica: `cd src && python backfill_historico.py` e
  depois `python backfill_indices.py`.** Rodar os dois uma vez por mês. Juntos
  levam ~1 min, não duplicam nada se rodarem de novo, e são o que impede a
  série de ficar presa nos 3 meses da janela da brapi.
- Ver o que rendeu mais até agora: `cd src && python indices.py`
- Backup manual antes de mexer em schema (o automático tem throttle diário e
  pode já ter sido "gasto" hoje):
  `copy data\acoes.db data\acoes_backup_AAAAMMDD.db`
- Consultar o banco sem SQL na mão: pedir um script curto que imprime o
  resultado, em vez de digitar SQL no terminal.
- **Feriados**: a janela de pregão olha só dia da semana e hora. Feriado
  nacional que cai em dia útil (Natal numa terça, Carnaval, 7 de setembro)
  ainda dispara coleta, e o preço repetido do último fechamento entra na
  série. São ~9 dias por ano. Fechar isso pede calendário da B3 e é tarefa
  futura, não bug do P0-5.

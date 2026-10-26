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
- [x] **P1-1** lógica de score extraída de `analise.py` para `src/scoring.py`.
      `scoring.py` não lê o banco: recebe DataFrames e devolve DataFrames, para
      o bloco P1-11→P1-2 poder ser testado com dados sintéticos. `analise.py`
      ficou com os carregadores e ganhou `ranking_atual()`. Ranking conferido
      byte a byte contra o baseline: **idêntico**.
- [x] **Sanidade dos indicadores** (tarefa nova, fora do PRD) — `validacao.py`
      recusa o impossível (margem acima de 100%, CAGR abaixo de −100%) e avisa
      sobre incoerência entre indicadores, sem remover. Único descarte nos
      dados atuais: margem líquida de 212% da ITSA4. Efeito grande, porque com
      min-max esse valor ancorava a escala de rentabilidade de todo mundo.
- [x] **P1-12** `setores.py` com setor por ticker; financeiras não pontuam ROA,
      margens nem dívida/PL. **BBAS3 deixou de tirar 0.0 em segurança** (aceite
      cumprido) e ITUB4 deixou de tirar 100.0 pela mesma razão invertida.
- [x] **P1-13** `score_geral` removido, `fillna(median)` removido, cobertura
      exposta (`indicadores_usados` de `indicadores_aplicaveis`). Categoria sem
      indicador sai do cálculo com o peso redistribuído, em vez de virar 0.
      Divergi da 7A.6 em um ponto: inaplicável é tratado como ausente, não com
      nota neutra. Justificado no DECISOES.md e fácil de reverter.
- [x] **BUG-01** `carregar_fundamentos_mais_recentes()` ordenava por `MAX(data)`
      textual (`dd/mm/aaaa`), então `31/08/2026` saía maior que `14/09/2026` e
      o ranking rodava sobre o fundamento mais antigo do banco. Trocado por
      `data_hora_iso`. Efeito medido: só a categoria valuation mudou (P/L e
      P/VP se movem com o preço; ROE, margens e CAGR vêm de balanço trimestral
      e eram iguais nas duas datas), com no máximo 0,9 ponto de diferença no
      `score_geral` e **ordem do ranking inalterada**. `test_analise.py` cobre
      a armadilha com 6 testes.
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

- [ ] nada — próxima é **P1-11** (faixas absolutas). Virou prioridade real:
      ver o aviso sobre a coluna segurança logo abaixo

---

## Próximas tarefas — ORDEM REPRIORIZADA (PRD v1.2 §10)

A ordem mudou depois da revisão de metodologia. **P1-8 (ampliar whitelist)
saiu da frente**: com faixas absolutas, ampliar a lista deixa de recalibrar o
score inteiro, então não precisa mais vir antes dos ajustes de fórmula.
Todo o bloco de score vem **antes** do P1-4, para não gravar snapshots numa
escala que será trocada.

### Bloco de score (o miolo da revisão)
- [ ] **P1-11** faixas absolutas — **agora é urgente, não só desejável.** Com
      as financeiras fora de dívida/PL, segurança ficou com 1 indicador e 5
      papéis, e o min-max virou artefato puro (FIQE3 em 0,0 e WEGE3 em 100,0).
      Até o P1-11 entrar, **não use a coluna segurança para decidir nada.**
      Ver DECISOES.md.
      *Escopo (PRD §7A.3 a §7A.6):* faixas absolutas no lugar do min-max,
      separar margens de rentabilidade, dropar `margem_bruta` do score, cap de
      30% no CAGR de lucro.
      *Aceite:* mudar a whitelist não altera a nota de um ticker que não mudou.
      *Dois ajustes decididos na revisão de 26/10, antes de implementar:*
      1. **Interpolar** entre as âncoras em vez de degraus. ROE 15%=80 e
         ROE 20%=100 continuam valendo, mas ROE 17,5% vira 90 em vez de 80.
         Com degraus, 2,4 p.p. de CAGR valem 10 pontos de score e a mesma
         variação no meio da faixa vale 0 — ruim justamente para o O1, que é
         acompanhar a empresa no tempo.
      2. A regra "descartar CAGR de lucro se o ano-base for ≤ 0" **não é
         implementável**: a BolsAI devolve o CAGR pronto, sem o lucro do
         ano-base. Dá para aplicar o cap de 30%, não o descarte. A PETR4 com
         CAGR de 77,68% vai ser capada e receber nota máxima para um número
         que é quase certamente artefato de base deprimida.
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

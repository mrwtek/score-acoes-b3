# Estado do projeto

Atualizado em: 04/09/2026
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

---

## Em andamento

- [ ] nada — o P0 está fechado; próxima é **P1-1** (extrair score para
      `src/scoring.py`)

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

---

## Notas de operação

- Rodar coleta: `python src/main.py` → `checknow` força uma coleta
- Registrar operações: `python src/gerenciar_posicoes.py`
- Ver ranking: `python src/analise.py`
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

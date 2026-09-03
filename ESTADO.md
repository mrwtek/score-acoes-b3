# Estado do projeto

Atualizado em: 01/09/2026

Atualize este arquivo ao fim de cada tarefa e commite junto. Ele é o que te
orienta quando você voltar ao projeto depois de um tempo parado.

## Concluído

- [x] `config.py` — tokens das duas APIs carregados via `.env`
- [x] `coletor.py` — brapi (cotações) e BolsAI (fundamentos) funcionando
- [x] `banco.py` — SQLite com as tabelas `cotacoes`, `fundamentos`, `posicoes`
- [x] Dedupe diário de fundamentos (`ja_tem_fundamento_hoje`)
- [x] Join entre as duas fontes por `ticker` funcionando
- [x] `whitelist.py` — universo dinâmico (base ∪ tickers em carteira)
- [x] `main.py` — loop de coleta em thread + CLI
      (help / whitelistshow / pause / resume / checknow / exit)
- [x] `gerenciar_posicoes.py` — CLI de carteira com preço médio ponderado
      (buy / sell / show)
- [x] `analise.py` — score fundamentalista por categoria, score de preço e
      score geral (0,6 / 0,4)
- [x] `analise.ipynb` — descritiva, histogramas, boxplots, matriz de correlação,
      PCA (scree, PC1×PC2, loadings), série temporal, ADF, ACF/PACF,
      grid search de ARIMA por AIC
- [x] PRD escrito (`PRD_analise_acoes.txt` v1.1, com backlog priorizado)

## Antes de começar (setup do fluxo de trabalho)

- [x] `git init` + primeiro commit do estado atual
- [ ] `.gitignore` com `.env`, `data/*.db`, `__pycache__/`,
      `.ipynb_checkpoints/`, `exports/`
- [x] Salvar `CLAUDE.md`, `ESTADO.md` e `PRD_acoes.txt` na raiz
- [x] Criar `DECISOES.md` (vazio, append-only)

## Concluído
- [x] P0-2 caminho absoluto do banco (src/paths.py) — commit c54ab82
- [x] P0-6 backup automático do banco (throttle diário) — paths.py
- [x] P0-1 tabela `transacoes` + backfill das posições atuais.
- [x] config.py: caminho explícito do .env + falha imediata se token faltar
- [x] limpeza da posição de teste TESTE3

## Em andamento


## Próximas tarefas (ordem da seção 10 do PRD)

- [x] **P0-2** `paths.py` na raiz; eliminar `"../data/acoes.db"` hardcoded
      *Aceite:* `banco.py`, `analise.py` e o notebook abrem o banco rodando de
      qualquer diretório.
- [x] **P0-6** backup automático do `.db` antes de migração de schema
      *Aceite:* função de backup gera cópia com timestamp em `data/backups/`.
- [x] **P0-1** tabela `transacoes` + backfill das posições atuais
      *Aceite:* uma compra e uma venda geram 2 linhas corretas em `transacoes`,
      e `posicoes` continua funcionando como antes.
- [ ] **P0-3** gravar data também em ISO (`YYYY-MM-DD`)
      *Aceite:* `SELECT ... ORDER BY data_iso` retorna na ordem cronológica.
- [ ] **P0-4** P/L e P/VP negativos deixam de pontuar como "baratos"
      *Aceite:* ação com prejuízo aparece no fim do ranking de valuation, não
      no topo.
- [ ] **P0-5** coleta restrita ao pregão (dias úteis, 10h–18h)
      *Aceite:* rodar o loop às 22h não insere linha em `cotacoes`.
- [ ] **P1-8** ampliar whitelist para 20–30 tickers
- [ ] **P1-1** extrair lógica de score de `analise.py` para `src/scoring.py`
- [ ] **P1-2** winsorização (p5/p95) ou ranking percentual antes do min-max
- [ ] **P1-3** janela explícita no score de preço + flag de dado insuficiente
- [ ] **P1-5** `carteira.py` — lucro absoluto, relativo, peso, resultado
      realizado
- [ ] **P1-6** `sinais.py` — compra/manter/venda com justificativa
- [ ] **P1-4** `snapshots_score` + job diário
- [ ] **P1-7** dashboard Streamlit (abas Visão geral, Ranking, Carteira)

Depois disso: P1-9, P1-10 e a faixa P2 (robustez).

## Travas e decisões pendentes

Referência: seção 13 do PRD (questões em aberto).

- **Q2** — janela do score de preço: 52 semanas, 6 meses ou desde o início da
  coleta? Bloqueia o P1-3.
- **Q1** — tamanho alvo da whitelist. Bloqueia o P1-8 e afeta cota das APIs.
- **Q5** — comparar indicadores contra todo o universo ou contra o setor?
  (P/L de banco e de mineradora não são comparáveis). Afeta o P1-2.
- **Q3** — PCA/ARIMA entram no score como terceiro componente ou ficam só no
  notebook?
- **Q7** — onde registrar taxas e IR para o resultado realizado ficar fiel.
  Afeta o desenho de `transacoes` (P0-1) — vale decidir antes.

## Notas de operação

- Rodar coleta: `python src/main.py` → comando `checknow` força uma coleta
- Registrar operações: `python src/gerenciar_posicoes.py`
- Ver ranking: `python src/analise.py`
- Backup manual do banco antes de mexer em schema:
  `cp data/acoes.db data/acoes_backup_AAAAMMDD.db`
  - 02/09: .env foi encontrado fora do lugar (em exports/) e causou falha
  silenciosa de token em ambas as APIs por um tempo. Restaurado. Ainda falta
  o ajuste combinado em config.py para falhar de forma explicita se o
  token vier vazio (ver DECISOES.md).

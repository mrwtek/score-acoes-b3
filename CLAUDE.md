# Projeto: análise e score de ações da B3

## O que é

App local em Python que coleta cotações e indicadores fundamentalistas de uma
whitelist de ações brasileiras, guarda em SQLite, calcula um score de "boa e
barata" e (em breve) mostra num dashboard.

O sistema **não executa ordens e não decide nada**. Ele automatiza coleta,
cálculo e visualização. Toda decisão de compra e venda é minha.

Especificação completa: `PRD_analise_acoes.txt`
Onde parei: `ESTADO.md`
Backlog priorizado: seção 10 do PRD (itens P0/P1/P2/P3)

## Quem sou eu

Não sou desenvolvedor profissional — sei Python e estatística, mas trabalho
melhor com explicação em português simples. Prefira solução simples e legível a
solução elegante. Quando houver escolha técnica não óbvia, me explique o
trade-off antes de decidir por mim.

## Estrutura de arquivos

Atual:

    src/
      config.py               tokens BRAPI_TOKEN e BOLSAI_TOKEN via .env
      whitelist.py            universo = WHITELIST_BASE ∪ tickers em carteira
      coletor.py              chamadas às duas APIs
      banco.py                SQLite: cotações, fundamentos, posições
      main.py                 loop de coleta em thread + CLI
      gerenciar_posicoes.py   CLI de carteira (buy/sell/show)
      analise.py              cálculo dos scores
      test_bolsai.py          script solto de teste manual da API BolsAI
    data/
      acoes.db                banco SQLite
    notebooks/
      analise.ipynb           pesquisa livre (PCA, ADF, ACF/PACF, ARIMA)

Alvo (conforme o PRD vai sendo executado): `scoring.py`, `carteira.py`,
`sinais.py`, `snapshots.py`, `app.py` (Streamlit), `paths.py`.

## Fontes de dados

**brapi** — cotações
`GET https://brapi.dev/api/quote/{ticker}` com `?token=BRAPI_TOKEN`
Resposta usada: `results[0]` → `regularMarketPrice`, `regularMarketVolume`,
`marketCap`, `priceEarnings`, `earningsPerShare`.

**BolsAI** — fundamentos
`GET https://api.usebolsai.com/api/v1/fundamentals/{ticker}` com header
`X-API-Key: BOLSAI_TOKEN`
Resposta usada: `pl`, `pvp`, `roe`, `roa`, `roic`, `net_margin`, `gross_margin`,
`ebitda_margin`, `debt_equity`, `cagr_revenue_5y`, `cagr_earnings_5y`.

O **join entre as duas fontes é sempre por `ticker`**, em maiúsculo, sem sufixo
`.SA` e sem espaços. Normalizar na escrita, nunca só na leitura.

## Esquema do banco (data/acoes.db)

    cotacoes(id, ticker, data, hora_coleta, preco, volume, market_cap,
             preco_lucro, lucro_por_acao)
        série temporal, um registro por coleta

    fundamentos(id, ticker, data, hora_coleta, pl, pvp, roe, roa, roic,
                margem_liquida, margem_bruta, margem_ebitda, divida_patrimonio,
                cagr_receita_5a, cagr_lucro_5a, UNIQUE(ticker, data))
        um registro por ticker por dia; dedupe via ja_tem_fundamento_hoje()

    posicoes(ticker, quantidade, preco_medio, data_atualizacao)
        estado atual da carteira; preço médio ponderado no registrar_compra()

Datas hoje são texto no formato `%d/%m/%Y` e horas `%H:%M:%S` — o que impede
ordenar e filtrar por data em SQL (item P0-3 do backlog).

## Regras de lógica do score

- Normalização min-max por indicador dentro do universo, respeitando a direção
  (maior melhor / menor melhor), definida em `CATEGORIAS_FUNDAMENTALISTAS`.
- Categorias e pesos: valuation 25% | rentabilidade 25% | crescimento 25% |
  segurança 25% (`PESOS_CATEGORIA`).
- Score de preço = posição do preço atual no range histórico, invertida
  (perto da mínima = score alto).
- `score_geral = 0.6 × score_fundamentalista + 0.4 × score_preco`.
- Escala sempre 0–100.

## Regras de trabalho

- Código, nomes de função e variáveis em **português**, como o resto do projeto.
- **Não refatorar arquivo que não faz parte da tarefa atual.** Se achar que algo
  fora do escopo precisa mudar, me avise em vez de mudar.
- **Antes de escrever código, apresentar um plano curto** (até 10 linhas): o que
  vai mudar, em quais arquivos, o que pode quebrar.
- Não inventar nomes de função ou coluna: leia o arquivo antes de referenciá-lo.
  Se precisar de algo que não existe, diga.
- **Toda alteração de schema exige backup do .db antes.**
- O notebook `analise.ipynb` **lê** do banco e nunca escreve. Função que
  amadurecer lá migra para `scoring.py` com teste.
- Bibliotecas já em uso: requests, python-dotenv, pandas, numpy, scikit-learn,
  statsmodels, matplotlib, seaborn. Avisar antes de introduzir outra.
- Uma tarefa do backlog por vez. Terminou, commit.

## Armadilhas conhecidas deste código

Não são bugs a corrigir de passagem — são itens do backlog. Cite se atrapalharem
a tarefa atual, mas não conserte fora de hora.

- `"../data/acoes.db"` está hardcoded em `banco.py`, `analise.py` e no notebook;
  quebra conforme o diretório de execução (P0-2).
- `posicoes` guarda só o estado final — não há histórico de operações (P0-1).
- P/L e P/VP negativos (empresa com prejuízo) hoje pontuam como "baratos" (P0-4).
- Coleta roda 24h, inclusive fora do pregão, poluindo a série e distorcendo
  min/max (P0-5).
- Score de preço usa toda a base coletada como range; com histórico curto o
  número engana (P1-3).
- Min-max sem tratamento de outlier: um P/L de 300 achata todo o resto (P1-2).
- Whitelist tem 5 tickers — pouco para normalização relativa e PCA terem
  significado estatístico (P1-8).
- `pausado` e `encerrar` são globais compartilhadas entre threads sem
  sincronização (P2-4).
- Chamadas às APIs sem timeout, retry ou checagem de status HTTP (P2-1).

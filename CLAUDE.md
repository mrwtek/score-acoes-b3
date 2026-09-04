# Projeto: análise e score de ações da B3

## O que é

App local em Python que coleta cotações e indicadores fundamentalistas de uma
whitelist de ações brasileiras, guarda em SQLite, calcula scores de qualidade e
de preço, e (em breve) mostra num dashboard.

O sistema **não executa ordens e não decide nada**. Ele automatiza coleta,
cálculo e visualização. Toda decisão de compra e venda é minha.

Especificação completa: `PRD_analise_acoes.txt` (v1.2)
Metodologia do score: **seção 7A do PRD** — leia antes de mexer em scoring
Onde parei / próxima tarefa: `ESTADO.md`
Por que as coisas são como são: `DECISOES.md`
O que cada comando faz e como rodar: `COMANDOS.md`

## Quem sou eu

Não sou desenvolvedor profissional — sei Python e estatística, mas trabalho
melhor com explicação em português simples. Prefira solução simples e legível a
solução elegante. Quando houver escolha técnica não óbvia, me explique o
trade-off antes de decidir por mim.

## Estrutura de arquivos

    src/
      paths.py                caminhos absolutos (banco, .env, backups) +
                              fazer_backup() com throttle diário
      config.py               tokens via .env; falha imediata se faltar token
      whitelist.py            universo = WHITELIST_BASE ∪ tickers em carteira
      coletor.py              chamadas às duas APIs
      banco.py                SQLite: criar_tabelas, salvar/registrar
      main.py                 loop de coleta em thread + CLI
      gerenciar_posicoes.py   CLI de carteira (buy/sell/show)
      analise.py              cálculo dos scores (será extraído p/ scoring.py)
      backfill_transacoes.py  script de uso único, já executado
      migrar_datas_iso.py     script de uso único, já executado
      test_bolsai.py          script solto de teste manual da API BolsAI
    data/
      acoes.db                banco SQLite
      backups/                cópias automáticas com timestamp
    notebooks/
      analise.ipynb           pesquisa livre (PCA, ADF, ACF/PACF, ARIMA)
    .env                      NA RAIZ, não em subpasta (já causou bug)

A criar conforme o backlog: `scoring.py`, `carteira.py`, `sinais.py`,
`snapshots.py`, `app.py` (Streamlit).

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

**Limite de plano, não bug:** a cobertura de tickers da brapi depende do plano
contratado, e a BolsAI tem cota diária no free. Se um ticker falhar com "token
não fornecido" enquanto outros funcionam na mesma execução, suspeite do plano
antes do código.

## Esquema do banco (data/acoes.db)

    cotacoes(id, ticker, data, hora_coleta, data_hora_iso, preco, volume,
             market_cap, preco_lucro, lucro_por_acao)

    fundamentos(id, ticker, data, hora_coleta, data_hora_iso, pl, pvp, roe,
                roa, roic, margem_liquida, margem_bruta, margem_ebitda,
                divida_patrimonio, cagr_receita_5a, cagr_lucro_5a,
                UNIQUE(ticker, data))
        um registro por ticker por dia; dedupe via ja_tem_fundamento_hoje()

    posicoes(ticker, quantidade, preco_medio, data_atualizacao)
        estado atual da carteira; preço médio ponderado em registrar_compra()

    transacoes(id, ticker, tipo, quantidade, preco, data_operacao,
               data_operacao_iso, taxas, observacao)
        histórico append-only; `taxas` = só corretagem/emolumentos (IR fora,
        ver DECISOES.md)

**Duas representações de data convivem de propósito.** As colunas `data` /
`hora_coleta` / `data_operacao` seguem no formato brasileiro (`%d/%m/%Y`) e
continuam sendo gravadas — `ja_tem_fundamento_hoje()` depende delas. As colunas
`*_iso` (`YYYY-MM-DD HH:MM:SS`) são as que ordenam e filtram corretamente em
SQL. Use as ISO para qualquer consulta nova.

## Metodologia do score — leia a seção 7A do PRD antes de mexer

Resumo. Quatro categorias usam **faixas absolutas** (a nota depende só do valor
do indicador, nunca de quem está na whitelist); só valuation é relativo ao
universo. Isso é o que torna os snapshots comparáveis ao longo do tempo.

    rentabilidade   ROIC 40% | ROE 35% | ROA 25%          absoluto
    margens         líquida 60% | EBITDA 40%              absoluto
    crescimento     CAGR receita 60% | CAGR lucro 40%     absoluto
    seguranca       dívida/patrimônio 100%                absoluto
    valuation       E/P 50% | B/P 50%                     relativo

- Valuation usa **earnings yield (1/pl)** e **book-to-market (1/pvp)**, ambos
  "maior é melhor" — nunca P/L e P/VP diretos, que pontuam prejuízo como
  "barato".
- `score_geral` **não existe mais**. Ficam duas colunas independentes:
  `score_fundamentalista` e `score_reversao`.
- `score_reversao` (antigo `score_preco`) mede **queda de preço, não
  barateamento**. É uma aposta contrária deliberada. Nunca descreva como
  valuation.
- Financeiras não pontuam dívida/PL, ROA nem margens: nota neutra com flag
  `nao_aplicavel`, nunca 0.
- Escala sempre 0–100. Faixas ancoradas ao custo de capital brasileiro
  (Selic/inflação em `config_scoring`), não copiadas de tabela americana.

O estado atual do código ainda **não** reflete tudo isso — a migração é o bloco
P1-1 → P1-11 → P1-12 → P1-13 → P1-2 → P1-14 do backlog. Confira no `ESTADO.md`
o que já foi feito antes de assumir qualquer coisa.

## Regras de trabalho

- Código, nomes de função e variáveis em **português**, como o resto do projeto.
- **Não refatorar arquivo que não faz parte da tarefa atual.** Se achar que algo
  fora do escopo precisa mudar, me avise em vez de mudar.
- **Antes de escrever código, apresentar um plano curto** (até 10 linhas): o que
  vai mudar, em quais arquivos, o que pode quebrar.
- Não inventar nomes de função ou coluna: leia o arquivo antes de referenciá-lo.
  Se precisar de algo que não existe, diga.
- **Toda alteração de schema exige backup do .db antes.** `fazer_backup()` tem
  throttle diário — se já rodei algo hoje, o backup do dia já foi "gasto";
  nesse caso peça backup manual.
- Mudanças em lógica de cálculo vêm com teste (`pytest`), no padrão do P0-4:
  dados sintéticos, casos de borda explícitos, tabela de conferência manual
  impressa no final.
- O notebook `analise.ipynb` **lê** do banco e nunca escreve.
- Bibliotecas em uso: requests, python-dotenv, pandas, numpy, scikit-learn,
  statsmodels, matplotlib, seaborn, pytest. Avisar antes de introduzir outra.
- Uma tarefa do backlog por vez. Terminou, commit.

## Armadilhas conhecidas (abertas)

Não são bugs a corrigir de passagem — são itens do backlog. Cite se
atrapalharem a tarefa atual, mas não conserte fora de hora.

- Coleta roda 24h, inclusive fora do pregão, poluindo a série (P0-5).
- `normalizar()` faz `fillna(median)`: dado faltante vira nota média em
  silêncio, sem aviso (P1-13).
- Min-max sem tratamento de outlier nas categorias ainda não migradas; o pior
  colocado sempre tira exatamente 0 e o melhor 100, o que é artefato e não
  informação (P1-2, P1-11).
- `score_reversao` usa toda a base coletada como range; com histórico curto o
  número vira interruptor (0 ou 100) em vez de escala (P1-3).
- Book-to-market não tem teto para P/VP próximo de zero — o earnings yield tem.
  Será resolvido de forma geral pela winsorização (P1-2).
- Whitelist pequena para normalização relativa e PCA terem significado
  estatístico (P1-8).
- `pausado` e `encerrar` são globais compartilhadas entre threads sem
  sincronização (P2-4).
- Chamadas às APIs sem timeout, retry ou checagem de status HTTP (P2-1).
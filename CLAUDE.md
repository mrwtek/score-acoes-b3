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
      faixas.py               âncoras absolutas por indicador + interpolação.
                              Não depende do universo (P1-11)
      scoring.py              as fórmulas do score. NÃO lê o banco: recebe
                              DataFrames e devolve DataFrames
      validacao.py            recusa indicador impossível (vira ausente, nunca
                              nota); avisa incoerência sem remover
      setores.py              setor por ticker e quais indicadores não se
                              aplicam a cada setor. Só responde, não pontua
      teses.py                diário de teses: registra o que você achou, com
                              prazo e critério, e confere contra IBOV e CDI
      analise.py              carregadores do banco + `ranking_atual()` +
                              impressão do ranking. Sabe de SQLite, não de
                              fórmula
      indices.py              benchmarks: IBOV (brapi) e Selic/CDI (BCB), mais
                              as contas de rendimento; `python indices.py`
                              imprime a comparação ação × IBOV × CDI
      exportar_bi.py          camada de BI: lê o banco e grava CSVs em
                              `exports/bi/` para o Power BI. Só lê. `f_score`
                              é append — é ele que dá série ao score, que não
                              existe no banco
      backfill_historico.py   backfill de preços diários da brapi; NÃO é de uso
                              único — roda uma vez por mês para estender a série
      backfill_indices.py     idem, para IBOV, Selic e CDI
      backfill_transacoes.py  script de uso único, já executado
      migrar_datas_iso.py     script de uso único, já executado
      test_bolsai.py          script solto de teste manual da API BolsAI
    data/
      acoes.db                banco SQLite
      backups/                cópias automáticas com timestamp
    notebooks/
      analise.ipynb           pesquisa livre (PCA, ADF, ACF/PACF, ARIMA)
    .env                      NA RAIZ, não em subpasta (já causou bug)

A criar conforme o backlog: `carteira.py`, `sinais.py`,
`snapshots.py`, `app.py` (Streamlit).

## Fontes de dados

**brapi** — cotações
`GET https://brapi.dev/api/quote/{ticker}` com `?token=BRAPI_TOKEN`
Resposta usada: `results[0]` → `regularMarketPrice`, `regularMarketVolume`,
`marketCap`, `priceEarnings`, `earningsPerShare`.

**brapi** — histórico e Ibovespa
Mesma URL com `?range=3mo&interval=1d` → `results[0].historicalDataPrice`,
lista de `{date, open, high, low, close, volume, adjustedClose}`. `date` é
epoch em **segundos, na meia-noite de São Paulo** — converter com fuso
explícito, nunca com o fuso da máquina. O Ibovespa é o símbolo `^BVSP`.
Plano free: só os ranges `1d, 5d, 1mo, 3mo`, e 20 requisições por minuto.

**Banco Central (SGS)** — Selic e CDI
`GET https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados?formato=json`
com `dataInicial`/`dataFinal` em `DD/MM/AAAA`. Série 11 = Selic diária,
12 = CDI diária. **Aberta, não pede token.** Resposta devolve `data` no
formato brasileiro e `valor` como **string** — normalizar os dois na entrada.

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

    cotacoes_historicas(id, ticker, data, abertura, maxima, minima,
                        fechamento, fechamento_ajustado, volume, coletado_em,
                        UNIQUE(ticker, data))
        um ponto por pregão, vindo do histórico da brapi. Tabela nova, então
        `data` é só ISO (`YYYY-MM-DD`) — não herda a convivência de dois
        formatos. **Para retorno e série temporal, use esta tabela, não
        `cotacoes`**: `cotacoes` é a série de coleta, com várias linhas por dia
        e só o preço do momento. E use `fechamento_ajustado`, não `fechamento`,
        sempre que comparar rendimento — o ajustado considera proventos e o
        Ibovespa é índice de retorno total. Medido em 23/10/2026: PETR4 rendeu
        +46,34% pelo ajustado contra +42,39% pelo cru no mesmo período.
        **O pregão do dia corrente nunca é gravado aqui** — a barra ainda está
        se formando e o `INSERT OR IGNORE` congelaria o valor errado.

    teses(id, ticker, data_abertura, preco_abertura, premissa, criterio,
          horizonte_dias, score_abertura, status, data_encerramento,
          veredito, criado_em)
        diário de teses. `preco_abertura` e `score_abertura` ficam congelados
        de propósito — a metodologia do score ainda muda, e a nota de hoje
        precisa continuar sendo a de hoje na hora de conferir.
        **Prazo e critério são obrigatórios na abertura**: tese sem prazo não
        pode falhar, e só o que pode falhar ensina. Append-only na prática:
        encerrar escreve o veredito, nunca apaga.

    indices(id, codigo, data, valor, tipo, coletado_em, UNIQUE(codigo, data))
        benchmarks. `codigo` ∈ {IBOV, SELIC, CDI}; `data` em ISO.
        `tipo` decide como se lê o `valor`:
          'preco'       → nível do índice (IBOV); rendimento = variação %
          'taxa_diaria' → % ao dia (Selic, CDI); rendimento = produtório de
                          (1 + valor/100). **Somar taxa diária dá errado** —
                          em 252 pregões a 0,0505% a.d., somar dá 12,73% e
                          compor dá 13,57%.
        A taxa fica gravada crua, como o BCB manda; a acumulação é na leitura.
        O BCB publica Selic e CDI com alguns dias de atraso, então essa série
        costuma terminar antes da do Ibovespa — use `janela_comparavel()`.

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

Implementado no P1-11. As faixas da 7A são **âncoras interpoladas**, não
degraus: as notas nas âncoras são as do PRD, mas entre elas a nota varia em
linha reta. Sem isso, ROE 14,9 valeria 55 e ROE 15,0 valeria 80.
Peso das cinco categorias: 20% cada — número meu, não do PRD, ver DECISOES.md.

- Valuation usa **earnings yield (1/pl)** e **book-to-market (1/pvp)**, ambos
  "maior é melhor" — nunca P/L e P/VP diretos, que pontuam prejuízo como
  "barato".
- `score_geral` **não existe mais** (removido no P1-13). Ficam duas colunas
  independentes: `score_fundamentalista` e `score_reversao`, lidas lado a lado
  e nunca somadas.
- `score_reversao` (antigo `score_preco`, renomeado no P1-3) mede **queda de
  preço, não barateamento**. É uma aposta contrária deliberada. Nunca descreva
  como valuation. Lê `cotacoes_historicas` pelo **fechamento ajustado**, em
  janela de 252 pregões, com mínimo de 60 observações — abaixo disso devolve
  50 com flag `dados_insuficientes`. A flag `janela_completa` separa "passou
  do mínimo" de "tem um ano de série".
- Financeiras não pontuam dívida/PL, ROA nem margens (`setores.py`). O
  indicador inaplicável é tratado como ausente — sai do cálculo e o peso é
  redistribuído — e não com nota neutra como diz a 7A.6. Divergência
  deliberada, justificada no DECISOES.md de 26/10.
- **Dado ausente não vira nota.** `normalizar()` não imputa mais mediana, e o
  ranking expõe cobertura (`indicadores_usados` de `indicadores_aplicaveis`).
  Categoria sem indicador sai como ausente, nunca como 0 — 0 diz "ruim"
  quando a verdade é "não dá para saber".
- Antes de pontuar, os indicadores passam por `validacao.py`: o que é
  impossível (margem acima de 100%, CAGR abaixo de −100%) vira ausente. Faixa
  absoluta transforma número absurdo em nota confiante, então o filtro vem
  antes.
- Escala sempre 0–100. Faixas ancoradas ao custo de capital brasileiro
  (`SELIC_REFERENCIA` e `INFLACAO_REFERENCIA` em `faixas.py`; a tabela
  `config_scoring` do PRD ainda não existe), não copiadas de tabela americana.
- **Aberto:** as âncoras de crescimento são nominais e estão frouxas — 6 de 9
  tickers passam do teto de 15% no CAGR de receita. Num país com inflação de
  4,5%, 15% nominal não devia ser o teto. Ver ESTADO.md.

Desse bloco falta só o **P1-2** (winsorização + z-score no valuation) e o
**P1-14** (flag `premio_negativo`). Confira no `ESTADO.md` antes de assumir
qualquer coisa.

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
- `score_reversao` com janela parcial ainda é frágil: hoje são 63 de 252
  pregões, e quem está na mínima tira exatamente 100. A janela e o mínimo já
  são explícitos (P1-3 feito) e o ranking mostra `63/252`, mas só o tempo
  enche a janela.
- Book-to-market não tem teto para P/VP próximo de zero — o earnings yield tem.
  Será resolvido de forma geral pela winsorização (P1-2).
- Whitelist pequena para normalização relativa e PCA terem significado
  estatístico (P1-8).
- `pausado` e `encerrar` são globais compartilhadas entre threads sem
  sincronização (P2-4).
- Chamadas às APIs sem timeout, retry ou checagem de status HTTP (P2-1).
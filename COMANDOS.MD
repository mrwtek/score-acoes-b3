# Mapa de comandos

Referência rápida: o que cada arquivo faz, quando rodar, o que esperar na tela.
Rode tudo de dentro de `src/` (`cd src` primeiro), salvo indicação contrária.

---

## Uso do dia a dia

### `python analise.py`
**O que faz:** lê o banco e imprime o ranking de ações com os scores.
**Não coleta nada novo** — só calcula em cima do que já está salvo.
**Quando rodar:** sempre que quiser ver "como estão as ações agora", com o
dado mais recente que você já tem.
**Comportamento esperado:** imprime `Fundamentos: (N, 15)`, `Cotacoes: (N, 9)`,
`Posicoes: (N, 4)` e depois a tabela de ranking. Sem erro, sem travar.

### `python main.py`
**O que faz:** inicia o loop de coleta automática (roda em segundo plano,
dentro do horário de pregão) e abre um menu de comandos interativo.
**Quando rodar:** para deixar coletando cotações e fundamentos ao longo do
dia, ou para forçar uma coleta manual agora.
**Comandos dentro do menu:**
- `checknow` — força uma coleta imediata (funciona mesmo fora do pregão, com
  aviso na tela)
- `whitelistshow` — mostra quais tickers estão sendo monitorados
- `pause` / `resume` — pausa/retoma a coleta automática, sem fechar o programa
- `help` — reimprime esta lista
- `exit` — encerra
**Comportamento esperado:** dentro do pregão (dias úteis, 10h–18h, horário de
Brasília), coleta sozinho a cada hora. Fora disso, avisa "fora do horário de
pregão" e não coleta sozinho — mas `checknow` sempre funciona.
**Deixe essa janela aberta** se quiser coleta contínua; feche com `exit`
quando terminar o dia (ou deixe rodando, se preferir).

### `python gerenciar_posicoes.py`
**O que faz:** menu para registrar compras e vendas, e ver sua carteira atual.
**Quando rodar:** toda vez que você comprar ou vender uma ação de verdade e
quiser refletir isso no sistema.
**Comandos dentro do menu:**
- `buy TICKER QUANTIDADE PRECO` — ex.: `buy PETR4 100 44.30`
- `sell TICKER QUANTIDADE` — ex.: `sell PETR4 50`
- `show` — lista as posições atuais (quantidade, preço médio, data)
- `help`, `exit`
**Comportamento esperado:** cada `buy`/`sell` imprime confirmação com o novo
preço médio ou quantidade. `show` sem posições diz "Nenhuma posição
registrada ainda" — normal se a carteira estiver vazia.

---

### `python backfill_historico.py`
**O que faz:** baixa da brapi os últimos 3 meses de pregões de cada ticker da
whitelist e grava em `cotacoes_historicas` (um ponto por dia, com OHLC e
fechamento ajustado).
**Quando rodar:** **uma vez por mês.** Não é script de uso único. O plano free
da brapi só entrega 3 meses, e essa janela desliza todo dia — rodando
periodicamente, a série no banco cresce além dos 3 meses e buracos de coleta
se fecham sozinhos. Se ficar mais de 3 meses sem rodar, o pedaço que passou da
janela some para sempre.
**Comportamento esperado:** leva ~45s com 13 tickers (pausa de 3,5s entre
chamadas, por causa do limite de 20 requisições/minuto da brapi). Imprime
quantos pregões vieram e quantos eram novos por ticker, depois uma tabela com
o período que cada ticker tem no banco. Rodar de novo no mesmo dia é seguro:
dá "0 novos" e não duplica nada.
**Variante:** `python backfill_historico.py PETR4 VALE3` limita a esses
tickers, em vez da whitelist inteira.

### `python backfill_indices.py`
**O que faz:** baixa o Ibovespa (brapi) e as séries diárias de Selic e CDI
(Banco Central) e grava na tabela `indices`.
**Quando rodar:** junto com o `backfill_historico.py`, uma vez por mês. O
Ibovespa tem o mesmo teto de 3 meses; Selic e CDI não têm teto, a API do BCB
é aberta e não pede token.
**Comportamento esperado:** ~10s. Por padrão busca as taxas desde o primeiro
dia que existe em `cotacoes_historicas`, para o benchmark cobrir exatamente o
período comparável. Avisa se as séries terminarem em datas diferentes — o BCB
publica a taxa com alguns dias de atraso, e isso é da fonte, não erro.
**Variante:** `python backfill_indices.py 2026-01-01` busca desde a data dada.

### `python teses.py`
**O que faz:** mostra o painel das teses abertas — o que você achou, quando,
com que prazo e critério, e como está indo contra o IBOV e o CDI.
**Quando rodar:** de tempos em tempos, e sempre no vencimento de uma tese.
**Não coleta nada** — só lê. Para abrir uma tese nova, me peça; a função é
`abrir_tese()` e ela exige prazo e critério escritos antes.
**Comportamento esperado:** se não houver pregão novo desde a abertura, diz
"ainda sem pregão novo para medir" e não inventa número.

### `python indices.py`
**O que faz:** imprime a comparação de rendimento — cada ação, o Ibovespa e o
CDI no mesmo período, ordenados, com a diferença em pontos percentuais contra
o CDI.
**Quando rodar:** quando quiser responder "o que rendeu mais até agora?".
**Não coleta nada** — só lê o que os dois backfills já gravaram.
**Comportamento esperado:** usa automaticamente a janela em que todas as
séries existem, mostra quantos pregões cada papel tem, e usa o **fechamento
ajustado** das ações (considera proventos; o Ibovespa é índice de retorno
total, então comparar com preço cru subestimaria as ações).

---

## Scripts de manutenção (uso pontual, não diário)

### `python migrar_datas_iso.py`
**O que faz:** preenche a coluna `data_hora_iso`/`data_operacao_iso` nas
linhas antigas do banco, a partir das colunas de data no formato brasileiro.
**Quando rodar:** já rodou uma vez (P0-3). Só rodaria de novo se restaurasse
um backup antigo sem essas colunas preenchidas.
**Comportamento esperado:** faz backup antes, avisa quantas linhas migrou,
avisa e pula linhas que não conseguir converter (não trava).

### `python backfill_transacoes.py`
**O que faz:** cria uma transação de compra inicial para cada posição já
existente, dando um ponto de partida ao histórico de `transacoes`.
**Quando rodar:** já rodou uma vez (P0-1). Rodar de novo com `transacoes` já
populada não faz nada — ele detecta e avisa "backfill não executado".

---

## Testes (conferem que o código está calculando certo)

### `python test_valuation.py`
**O que faz:** confirma que earnings yield e book-to-market (P0-4) calculam
certo, inclusive nos casos de prejuízo, zero e P/L quase zero.
**Quando rodar:** depois de qualquer mudança em `analise.py` que toque no
valuation. Também serve de referência de como o cálculo deveria se comportar.
**Comportamento esperado:** lista de `ok    teste_...` terminando em
`10/10 testes passaram`, mais uma tabela de conferência manual.

### `python test_pregao.py`
**O que faz:** confirma que a janela de horário de pregão (P0-5) está
calculando os dias e horas certos, e que o loop de coleta respeita isso de
verdade.
**Quando rodar:** depois de qualquer mudança em `main.py` que toque no
horário de coleta.
**Comportamento esperado:** lista de testes passando, incluindo um teste que
existe só para lembrar que feriados não são considerados (limitação
conhecida, não bug).

### `python test_validacao.py`, `test_setores.py`, `test_scoring.py`
**O que fazem:** cobrem a camada de sanidade dos indicadores, o mapa de setor
e o cálculo do score (dado ausente, cobertura, peso redistribuído).
**Quando rodar:** depois de qualquer mudança em `validacao.py`, `setores.py`
ou `scoring.py` — ou seja, em toda tarefa do bloco de score.
**Comportamento esperado:** 15/15, 12/12 e 14/14, cada um terminando numa
tabela de conferência manual. Nenhum toca o banco nem a API.

### `python test_teses.py`
**O que faz:** confere o diário de teses — registro com prazo obrigatório,
cálculo contra IBOV e CDI, e o corte das séries na data mais curta.
**Quando rodar:** depois de mexer em `teses.py`.
**Comportamento esperado:** `13/13 testes passaram`, mais uma tabela que
mostra por que subir 8% com o IBOV em 20% não é acerto.

### `python test_analise.py`
**O que faz:** confirma que os carregadores do `analise.py` leem a linha
certa — principalmente que o fundamento escolhido é o mais recente de
verdade, e não o "maior" na comparação de texto `dd/mm/aaaa` (BUG-01).
**Quando rodar:** depois de mexer em qualquer consulta do `analise.py`.
**Comportamento esperado:** `6/6 testes passaram`, mais uma tabela mostrando
em quais pares de datas a ordem textual discorda da ordem cronológica.
Usa banco temporário — não toca no `data/acoes.db`.

### `python test_historico.py`
**O que faz:** confirma que o backfill de preços históricos grava certo —
conversão da data no fuso da B3, normalização de ticker, reexecução sem
duplicar, e descarte de pontos sem data ou sem fechamento.
**Quando rodar:** depois de qualquer mudança em `banco.py` que toque em
`cotacoes_historicas`, ou em `coletor.py` que toque em `buscar_historico()`.
**Comportamento esperado:** `15/15 testes passaram`, mais uma tabela mostrando
o que a API manda e o que vai (ou não) para o banco em cada caso de borda.
Usa banco temporário e não chama a API — não toca no `data/acoes.db`.

### `python test_indices.py`
**O que faz:** confirma que a tabela `indices` e os coletores de benchmark
estão certos — conversão do formato do BCB, produtório vs soma na taxa
diária, variação percentual do Ibovespa, reexecução sem duplicar.
**Quando rodar:** depois de mexer em `indices.py` ou em `salvar_indices()`.
**Comportamento esperado:** `18/18 testes passaram`, mais uma tabela que
mostra o erro de somar taxa diária em vez de compor, crescendo com o prazo.
As três linhas "pulando ponto que nao consegui converter" no meio da saída
são esperadas: fazem parte de um teste de dado malformado.

### `python test_bolsai.py`
**O que faz:** faz uma chamada direta e crua à API BolsAI para um ticker, sem
passar pelo resto do sistema. Só imprime a resposta.
**Quando rodar:** se suspeitar que o problema é a API em si (token, cota,
formato de resposta), não o seu código.

---

## Análise exploratória (não é pipeline)

### `notebooks/analise.ipynb` (abrir no VSCode ou Jupyter)
**O que faz:** descritiva, histogramas, correlação, PCA, teste de
estacionariedade (ADF), ACF/PACF, grid search de ARIMA.
**Regra importante:** só LÊ do banco, nunca grava nada nele. É bancada livre
para você explorar — nada que rodar aqui afeta o resto do sistema.
**Quando rodar:** quando quiser investigar algo além do que o ranking padrão
mostra (ex.: será que essas ações se movem juntas? há sazonalidade?).

---

## "Só quero ver o ranking, qual comando?"

```
cd src
python analise.py
```

## "Quero atualizar os dados antes de ver o ranking"

```
cd src
python main.py
```
digite `checknow`, espere terminar, digite `exit`, depois `python analise.py`.

## "Comprei/vendi uma ação, onde registro?"

```
cd src
python gerenciar_posicoes.py
```
digite `buy` ou `sell` com os dados da operação.
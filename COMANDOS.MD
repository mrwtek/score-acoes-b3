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

### `python test_historico.py`
**O que faz:** confirma que o backfill de preços históricos grava certo —
conversão da data no fuso da B3, normalização de ticker, reexecução sem
duplicar, e descarte de pontos sem data ou sem fechamento.
**Quando rodar:** depois de qualquer mudança em `banco.py` que toque em
`cotacoes_historicas`, ou em `coletor.py` que toque em `buscar_historico()`.
**Comportamento esperado:** `15/15 testes passaram`, mais uma tabela mostrando
o que a API manda e o que vai (ou não) para o banco em cada caso de borda.
Usa banco temporário e não chama a API — não toca no `data/acoes.db`.

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
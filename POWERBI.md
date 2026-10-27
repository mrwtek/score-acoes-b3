# Power BI sobre a camada de BI

Como ligar o Power BI nos CSVs de `exports/bi/`, que medidas criar e o que
**não** fazer. Os nomes de tabela e de coluna aqui são os reais, conferidos
contra os arquivos gerados em 26/10/2026.

Gere os arquivos antes de qualquer coisa:

```
cd src
python exportar_bi.py
```

O que cada comando faz está no `COMANDOS.md`. Por que a camada existe, no
`DECISOES.md` e no cabeçalho do `src/exportar_bi.py`.

---

## 1. Primeira conexão

### 1.1 Antes de importar: localidade do arquivo

**Faça isto primeiro, com o arquivo .pbix novo ainda vazio.** Os CSVs saem no
padrão brasileiro (separador `;`, decimal `,`), e se a localidade do arquivo
não for a brasileira todo número entra como texto — sem erro, sem aviso.

Arquivo → Opções e configurações → Opções → **Configurações do arquivo
atual** → Configurações regionais → **Português (Brasil)**.

### 1.2 Parâmetro com o caminho da pasta

Página Inicial → Transformar dados → Gerenciar Parâmetros → Novo:

| campo | valor |
|---|---|
| Nome | `PastaBI` |
| Tipo | Texto |
| Valor atual | `C:\Users\Dimlu\app-b3\exports\bi` |

Serve para que mudar a pasta de lugar seja um campo, e não nove consultas.

### 1.3 Função de leitura

Ainda no editor: Página Inicial → Nova Fonte → **Consulta Nula**. No Editor
Avançado, apague tudo e cole:

```m
let
    fnLerBI = (nomeArquivo as text) as table =>
        let
            Origem = Csv.Document(
                File.Contents(PastaBI & "\" & nomeArquivo),
                [Delimiter = ";", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
            ),
            Cabecalho = Table.PromoteHeaders(Origem, [PromoteAllScalars = true])
        in
            Cabecalho
in
    fnLerBI
```

Renomeie a consulta para `fnLerBI`. `Encoding = 65001` é o UTF-8 que o
exportador grava; sem ele os acentos das premissas das teses viram lixo.

### 1.4 Uma consulta por arquivo

Para cada um dos nove arquivos: Nova Fonte → Consulta Nula → Editor Avançado,
e cole uma linha, trocando o nome:

```m
= fnLerBI("f_preco_diario.csv")
```

Renomeie a consulta para o nome do arquivo sem a extensão (`f_preco_diario`).
Repita para:

```
dim_ativo        f_preco_diario   f_indice      f_fundamento   f_posicao
f_transacao      f_tese           f_score       meta_exportacao
```

Depois, em cada consulta: selecione todas as colunas → Transformar →
**Detectar Tipo de Dados**.

**Confira antes de seguir.** Em `f_preco_diario`, a coluna `data` tem que
ficar como **Data** e `fechamento_ajustado` como **Número Decimal**. Se
`fechamento_ajustado` ficou como Texto, a localidade do passo 1.1 não pegou —
volte lá, depois clique com o botão direito no passo "Tipo Alterado" de cada
consulta e refaça.

Se preferir não depender da detecção, tipe à mão. Para `f_preco_diario`:

```m
= Table.TransformColumnTypes(
    fnLerBI("f_preco_diario.csv"),
    {
        {"ticker", type text},
        {"data", type date},
        {"abertura", type number},
        {"maxima", type number},
        {"minima", type number},
        {"fechamento", type number},
        {"fechamento_ajustado", type number},
        {"volume", Int64.Type}
    },
    "pt-BR"
)
```

### 1.5 Não use "Combinar" no conector de Pasta

O Power BI oferece **Pasta** como fonte, com um botão "Combinar e
Transformar". **Não serve aqui.** Combinar empilha arquivos de mesmo formato
num só; os nove CSVs têm colunas diferentes, e o resultado seria uma tabela
única com dezenas de colunas quase todas vazias. Uma consulta por arquivo,
como acima.

### 1.6 Calendário

Página Inicial → Inserir → **Nova tabela**:

```dax
dim_calendario =
VAR PrimeiroDia = MIN ( f_preco_diario[data] )
VAR UltimoDia = MAX ( f_preco_diario[data] )
RETURN
ADDCOLUMNS (
    CALENDAR ( PrimeiroDia, UltimoDia ),
    "Ano", YEAR ( [Date] ),
    "Mes", FORMAT ( [Date], "mmm" ),
    "NumMes", MONTH ( [Date] ),
    "AnoMes", FORMAT ( [Date], "yyyy-MM" ),
    "DiaSemana", FORMAT ( [Date], "ddd" ),
    "EhPregao", [Date] IN DISTINCT ( f_preco_diario[data] )
)
```

Selecione a tabela → Design da tabela → **Marcar como tabela de data** →
coluna `Date`. Sem isso, inteligência temporal não funciona direito.

### 1.7 Relacionamentos

Todos de **um para muitos**, da dimensão para o fato, filtro **único**:

| de | para |
|---|---|
| `dim_calendario[Date]` | `f_preco_diario[data]` |
| `dim_calendario[Date]` | `f_indice[data]` |
| `dim_calendario[Date]` | `f_fundamento[data]` |
| `dim_calendario[Date]` | `f_transacao[data]` |
| `dim_calendario[Date]` | `f_score[data_snapshot]` |
| `dim_ativo[ticker]` | `f_preco_diario[ticker]` |
| `dim_ativo[ticker]` | `f_fundamento[ticker]` |
| `dim_ativo[ticker]` | `f_transacao[ticker]` |
| `dim_ativo[ticker]` | `f_score[ticker]` |
| `dim_ativo[ticker]` | `f_posicao[ticker]` |
| `dim_ativo[ticker]` | `f_tese[ticker]` |

**Três coisas que NÃO se relacionam, de propósito:**

- **`f_posicao` não entra no calendário.** `data_atualizacao` é quando você
  mexeu na posição, não o dia a que ela se refere — a posição é o estado de
  agora. Ligada ao calendário, a carteira inteira sumiria de qualquer visual
  filtrado por um período que não contenha 31/08/2026.
- **`f_tese` não entra no calendário** pela mesma razão: `data_abertura` é um
  marco, não o período da tese. Ligada, a tese só apareceria no dia em que foi
  aberta.
- **`f_indice` não se liga a `dim_ativo`.** IBOV, Selic e CDI não têm ticker.
  Como não há relacionamento, filtrar um papel não mexe nas medidas de
  benchmark — que é justamente o que se quer num gráfico comparativo.

`meta_exportacao` fica solta, sem relacionamento nenhum. Ela é sobre os
arquivos, não sobre o mercado.

---

## 2. Medidas

Crie uma tabela vazia só para guardá-las: Inserir → Nova tabela →
`_Medidas = {BLANK()}`, depois esconda a coluna. Mantém o painel limpo.

### 2.1 Preço

```dax
Preço =
LASTNONBLANKVALUE (
    dim_calendario[Date],
    CALCULATE ( AVERAGE ( f_preco_diario[fechamento_ajustado] ) )
)
```

```dax
Preço de tela =
LASTNONBLANKVALUE (
    dim_calendario[Date],
    CALCULATE ( AVERAGE ( f_preco_diario[fechamento] ) )
)
```

Duas medidas de propósito. **`Preço` usa o fechamento ajustado e é o que
entra em qualquer conta de rendimento** — no dia do provento o preço cru cai
sem a empresa ter piorado. `Preço de tela` é o fechamento cru, que é o número
que aparece no home broker; use só para conferência. Medido em 23/10/2026:
PETR4 rendeu +46,34% pelo ajustado contra +42,39% pelo cru.

### 2.2 Carteira

```dax
Quantidade = SUM ( f_posicao[quantidade] )
```

```dax
Custo = SUM ( f_posicao[custo_total] )
```

```dax
Valor de mercado =
SUMX ( VALUES ( dim_ativo[ticker] ), [Quantidade] * [Preço] )
```

```dax
Resultado não realizado = [Valor de mercado] - [Custo]
```

```dax
Resultado não realizado % = DIVIDE ( [Resultado não realizado], [Custo] )
```

`SUMX` sobre `VALUES(dim_ativo[ticker])` é o que faz o total somar certo: o
preço multiplica a quantidade papel a papel, e só depois soma. `[Quantidade] *
[Preço]` direto no total multiplicaria a soma das quantidades por uma média
de preços, que não quer dizer nada.

### 2.3 Benchmarks

```dax
Fim comparável = MAX ( meta_exportacao[janela_fim] )
```

A data em que preço, IBOV e CDI existem todos. O BCB publica a taxa com
alguns dias de atraso, então o CDI termina antes do Ibovespa — hoje
2026-10-23 contra 2026-10-26. Comparar rendimento acumulado sobre janelas de
tamanhos diferentes não compara nada, e quem tem a série mais longa parece
melhor sem ter sido.

```dax
Retorno do ativo % =
VAR Inicio =
    CALCULATE (
        FIRSTNONBLANKVALUE (
            dim_calendario[Date],
            CALCULATE ( AVERAGE ( f_preco_diario[fechamento_ajustado] ) )
        ),
        ALLSELECTED ( dim_calendario )
    )
RETURN
    DIVIDE ( [Preço], Inicio ) - 1
```

```dax
Retorno IBOV % =
VAR Ate = [Fim comparável]
VAR Serie =
    CALCULATETABLE (
        f_indice,
        f_indice[codigo] = "IBOV",
        f_indice[data] <= Ate,
        ALLSELECTED ( dim_calendario )
    )
VAR Primeiro = MINX ( Serie, f_indice[data] )
VAR Ultimo = MAXX ( Serie, f_indice[data] )
VAR Abertura = MAXX ( FILTER ( Serie, f_indice[data] = Primeiro ), f_indice[valor] )
VAR Fechamento = MAXX ( FILTER ( Serie, f_indice[data] = Ultimo ), f_indice[valor] )
RETURN
    DIVIDE ( Fechamento, Abertura ) - 1
```

```dax
Retorno CDI % =
VAR Ate = [Fim comparável]
RETURN
    CALCULATE (
        PRODUCTX ( f_indice, f_indice[fator_diario] ) - 1,
        f_indice[codigo] = "CDI",
        f_indice[data] <= Ate,
        ALLSELECTED ( dim_calendario )
    )
```

**O CDI é `PRODUCTX` sobre `fator_diario`, nunca `SUM` sobre `valor`.** A
coluna `valor` é a taxa em % ao dia e taxa diária se compõe. A coluna
`fator_diario` já vem do exportador como `1 + valor/100`, pronta para o
produtório. O erro de somar cresce com o prazo:

| pregões | somando | compondo | erro |
|---|---|---|---|
| 21 | 1,0605% | 1,0659% | +0,005 p.p. |
| 63 | 3,1815% | 3,2318% | +0,050 p.p. |
| 252 | 12,7260% | 13,5676% | **+0,842 p.p.** |

`fator_diario` vem vazio para o IBOV de propósito: nível de índice não tem
fator diário, e uma coluna vazia impede a conta errada melhor que um 1,0.

```dax
Ativo vs IBOV (p.p.) = ( [Retorno do ativo %] - [Retorno IBOV %] ) * 100
```

```dax
Ativo vs CDI (p.p.) = ( [Retorno do ativo %] - [Retorno CDI %] ) * 100
```

### 2.4 Base 100 (para o gráfico de linhas)

Três medidas no mesmo gráfico de linhas, com `dim_calendario[Date]` no eixo.

```dax
Ativo base 100 =
VAR Inicio =
    CALCULATE (
        FIRSTNONBLANKVALUE (
            dim_calendario[Date],
            CALCULATE ( AVERAGE ( f_preco_diario[fechamento_ajustado] ) )
        ),
        ALLSELECTED ( dim_calendario )
    )
VAR Atual = CALCULATE ( AVERAGE ( f_preco_diario[fechamento_ajustado] ) )
RETURN
    DIVIDE ( Atual, Inicio ) * 100
```

```dax
IBOV base 100 =
VAR Ate = MAX ( dim_calendario[Date] )
VAR Desde = CALCULATE ( MIN ( dim_calendario[Date] ), ALLSELECTED ( dim_calendario ) )
VAR Serie =
    CALCULATETABLE ( f_indice, f_indice[codigo] = "IBOV", ALL ( dim_calendario ) )
VAR Abertura =
    MAXX ( FILTER ( Serie, f_indice[data] = Desde ), f_indice[valor] )
VAR Atual =
    MAXX ( FILTER ( Serie, f_indice[data] = Ate ), f_indice[valor] )
RETURN
    DIVIDE ( Atual, Abertura ) * 100
```

```dax
CDI base 100 =
VAR Ate = MAX ( dim_calendario[Date] )
VAR Desde = CALCULATE ( MIN ( dim_calendario[Date] ), ALLSELECTED ( dim_calendario ) )
RETURN
    CALCULATE (
        PRODUCTX ( f_indice, f_indice[fator_diario] ) * 100,
        f_indice[codigo] = "CDI",
        f_indice[data] >= Desde,
        f_indice[data] <= Ate,
        ALL ( dim_calendario )
    )
```

A linha do CDI para de subir quando a série acaba, alguns dias antes das
outras. Isso é o atraso do BCB aparecendo, não um bug — e é o motivo de
`Fim comparável` existir para os números acumulados.

### 2.5 Score

```dax
Último snapshot = MAX ( f_score[data_snapshot] )
```

```dax
Score fundamentalista =
LASTNONBLANKVALUE (
    f_score[data_snapshot],
    CALCULATE ( AVERAGE ( f_score[score_fundamentalista] ) )
)
```

```dax
Score de reversão =
LASTNONBLANKVALUE (
    f_score[data_snapshot],
    CALCULATE ( AVERAGE ( f_score[score_reversao] ) )
)
```

```dax
Cobertura % =
VAR Ultimo = [Último snapshot]
RETURN
    CALCULATE (
        DIVIDE (
            SUM ( f_score[indicadores_usados] ),
            SUM ( f_score[indicadores_aplicaveis] )
        ),
        f_score[data_snapshot] = Ultimo
    )
```

```dax
Cobertura =
VAR Ultimo = [Último snapshot]
VAR Usados = CALCULATE ( SUM ( f_score[indicadores_usados] ), f_score[data_snapshot] = Ultimo )
VAR Aplicaveis = CALCULATE ( SUM ( f_score[indicadores_aplicaveis] ), f_score[data_snapshot] = Ultimo )
RETURN
    IF ( ISBLANK ( Aplicaveis ), BLANK (), Usados & " de " & Aplicaveis )
```

```dax
Janela de reversão =
VAR Ultimo = [Último snapshot]
VAR Obs = CALCULATE ( MAX ( f_score[observacoes] ), f_score[data_snapshot] = Ultimo )
VAR Insuficiente =
    CALCULATE ( SELECTEDVALUE ( f_score[dados_insuficientes] ), f_score[data_snapshot] = Ultimo )
RETURN
    IF ( ISBLANK ( Obs ), BLANK (), Obs & "/252" & IF ( Insuficiente = TRUE (), " !", "" ) )
```

`SELECTEDVALUE` e não `MAX` em `dados_insuficientes`: a coluna é lógica, e
`MAX` sobre coluna lógica não é confiável em DAX. Como a medida é para ir na
linha da tabela de ranking, o contexto já é de um ticker só e
`SELECTEDVALUE` devolve o valor. Num total de várias linhas devolve branco,
que é o certo — a flag é por papel, não somável.

`Cobertura` e `Janela de reversão` existem para ir no rótulo da tabela de
ranking, ao lado do score. Uma nota de 75 com cobertura "3 de 10" e outra com
"10 de 10" não são a mesma informação, e sem a coluna ao lado as duas se
parecem.

### 2.6 Teses

O exportador já fez a conferência contra IBOV e CDI em Python, cortando as
três séries na última data comum. Em DAX é só ler.

```dax
Teses abertas = CALCULATE ( COUNTROWS ( f_tese ), f_tese[status] = "aberta" )
```

```dax
Retorno da tese % = AVERAGE ( f_tese[retorno] ) / 100
```

```dax
Tese vs IBOV (p.p.) = AVERAGE ( f_tese[vs_ibov] )
```

```dax
Tese vs CDI (p.p.) = AVERAGE ( f_tese[vs_cdi] )
```

```dax
Dias restantes = SUM ( f_tese[dias_restantes] )
```

As colunas de conferência vêm vazias enquanto não houver pregão novo depois
da abertura. Tese aberta hoje mostra branco, não zero — e é assim que deve
ser.

### 2.7 Saúde dos dados

```dax
Última cotação = MAX ( f_preco_diario[data] )
```

```dax
Dias desde a última cotação = DATEDIFF ( [Última cotação], TODAY (), DAY )
```

```dax
Exportado em = MAX ( meta_exportacao[exportado_em] )
```

```dax
Ativos sem score = SELECTEDVALUE ( meta_exportacao[tickers_sem_score] )
```

A coluna é de texto e repete o mesmo valor nas oito linhas do
`meta_exportacao`, então `SELECTEDVALUE` devolve esse valor. É mais previsível
que `MAX` sobre texto.

```dax
Ativos na carteira = CALCULATE ( DISTINCTCOUNT ( f_posicao[ticker] ), f_posicao[quantidade] > 0 )
```

---

## 3. Telas

### 3.1 Carteira

Cartões: `Valor de mercado`, `Custo`, `Resultado não realizado`,
`Resultado não realizado %`, `Ativos na carteira`.
Barras horizontais de `Resultado não realizado` por `dim_ativo[ticker]`.
Rosca de `Valor de mercado` por `dim_ativo[classe]` — separa ação de FII.
Rosca de `Valor de mercado` por `dim_ativo[setor]`.
Tabela: ticker, `Quantidade`, `f_posicao[preco_medio]`, `Preço`,
`Valor de mercado`, `Resultado não realizado %`.

### 3.2 Desempenho contra benchmark

Gráfico de linhas com `dim_calendario[Date]` no eixo e as três medidas base
100. Segmentação por `dim_ativo[ticker]` e por período.
Cartões: `Retorno do ativo %`, `Retorno IBOV %`, `Retorno CDI %`,
`Ativo vs CDI (p.p.)`.
Caixa de texto com `Fim comparável`, para ficar explícito até onde a
comparação vale.

### 3.3 Ranking

Tabela: ticker, setor, `Score fundamentalista`, `Score de reversão`,
`Cobertura`, `Janela de reversão`, e as categorias (`valuation`,
`rentabilidade`, `margens`, `crescimento`, `seguranca`) do `f_score`.

E o visual que vale montar primeiro: **dispersão com `Score de reversão` no
eixo X e `Score fundamentalista` no eixo Y**, ticker nos detalhes, tamanho
pelo `Valor de mercado`. O canto superior direito é "empresa boa que caiu";
o inferior direito, "caiu e não era boa". Lê os dois scores lado a lado sem
somá-los — que é exatamente o que o P1-13 decidiu ao remover o `score_geral`.

### 3.4 Ficha do ativo

Drill-through por `dim_ativo[ticker]`. Linha de `Preço` no tempo; tabela de
`f_fundamento` filtrada por `mais_recente = True`; `f_transacao` do papel;
`f_tese` do papel.

### 3.5 Diário de teses

Tabela de `f_tese`: ticker, data de abertura, premissa, critério,
`Dias restantes`, `Retorno da tese %`, `Tese vs IBOV (p.p.)`,
`Tese vs CDI (p.p.)`, status.
Filtro por `status`. Cartão com `Teses abertas`.

### 3.6 Saúde dos dados

Tabela de `meta_exportacao` inteira — é o que ela existe para ser.
Cartões: `Exportado em`, `Última cotação`, `Dias desde a última cotação`,
`Ativos sem score`.
Barras de contagem de linhas por arquivo.

Essa tela parece burocrática e é a que evita ler número errado com cara de
certo. Se `Dias desde a última cotação` estiver em 14, nenhum outro visual do
relatório está falando do presente.

---

## 4. O que não dá para fazer ainda

Para você não montar visual que vai nascer vazio.

**Evolução do score** começa no primeiro dia em que você rodou o
`exportar_bi.py`. O score nunca foi gravado antes disso — não existe
histórico retroativo para recuperar. Em 26/10/2026 há exatamente um snapshot.

**Resultado realizado** não é calculável com o que existe. `f_transacao` tem
nove compras e nenhuma venda, e mesmo com vendas faltaria o preço médio no
momento de cada uma: o `preco_medio` é recalculado em `posicoes` a cada
compra e o valor antigo não é guardado em lugar nenhum. Qualquer medida de
lucro realizado hoje seria chute com casas decimais.

**Retorno de 12 meses, drawdown longo e volatilidade anualizada** não têm
base: a série tem 63 pregões, de 28/07 a 26/10/2026. O plano free da brapi
limita o histórico a 3 meses, e a série só cresce rodando o
`backfill_historico.py` uma vez por mês.

**Evolução de fundamentos** é fraca: 70 linhas, 10 tickers, concentradas em
agosto e setembro de 2026.

**Três FIIs ficam fora do ranking.** MXRF11, GARE11 e BTCI11 não aparecem em
`f_score` porque o ranking parte dos fundamentos e a BolsAI não devolve
fundamento para FII. Eles aparecem normalmente em preço, carteira e
benchmark. A coluna `tickers_sem_score` do `meta_exportacao` lista quem
ficou de fora — e ficar de fora é melhor que entrar com nota inventada.

---

## 5. Armadilhas

**Nunca some `score_fundamentalista` com `score_reversao`.** Não existe mais
um score geral, e isso foi uma decisão (P1-13): o composto antigo tinha 55%
de "está barato" disfarçados, muito mais viés de valor do que o desenho
aparentava. São duas colunas lidas lado a lado.

**`score_reversao` mede queda, não barateamento.** Uma ação pode cair 40% e
ficar mais cara, se o lucro caiu 60%. É uma aposta contrária deliberada —
nunca rotule esse campo como "valuation" num visual.

**Nota 100 em reversão hoje não quer dizer muito.** A janela é de 252
pregões e há 63. Quem está na mínima do período tira exatamente 100. Por isso
a medida `Janela de reversão` mostra `63/252` ao lado da nota.

**Categoria vazia no `f_score` é ausência, não zero.** BBAS3 vem com
`margens` e `seguranca` em branco porque é financeira, e os indicadores de
margem e alavancagem não se aplicam a banco. Em DAX isso é `BLANK()`, e
`AVERAGE` ignora. Se você trocar por zero num visual, estará dizendo "ruim"
onde a verdade é "não se aplica".

**Use `fechamento_ajustado` para rendimento, `fechamento` para exibir.**

**A coluna `data` é a canônica em todas as tabelas.** `f_transacao` ainda
leva `data_operacao` (formato brasileiro) e `data_operacao_iso` para
auditoria; `f_fundamento` leva `data_hora_iso`. Não construa visual sobre
elas — ordenam como texto, e `31/08/2026` sai depois de `14/09/2026`.

**Taxa em branco não é taxa zero.** `f_transacao[taxas]` está vazia em todas
as linhas porque nunca foi preenchida, não porque a corretagem foi zero. O
`valor_liquido` assume zero para poder existir; trate-o como aproximação.

**Atualizar o Power BI não atualiza os dados.** O botão lê os CSVs. Para ter
dado novo, rode a coleta e depois o `exportar_bi.py`, nessa ordem.

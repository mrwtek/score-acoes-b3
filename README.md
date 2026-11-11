# Score de ações da B3

Sistema local em Python que coleta cotações, fundamentos e indicadores macroeconômicos de ações brasileiras, armazena em SQLite, calcula duas notas independentes por ativo — **qualidade da empresa** e **queda de preço** — e entrega o resultado num painel de Power BI.

**O sistema não executa ordens e não recomenda nada.** Não há robô de trade, integração com corretora nem decisão autônoma. Ele automatiza coleta, cálculo e visualização; a decisão continua humana.

> ⚠️ **Aviso.** Projeto pessoal de estudo. Nada aqui é recomendação de investimento, análise profissional ou oferta de qualquer natureza. Os dados vêm de APIs públicas de terceiros e podem estar incorretos ou desatualizados. Use por sua conta e risco.

<!-- Print do painel entra aqui quando houver:  ![Painel](docs/painel-ranking.png)
     NÃO use a tela Carteira: ela mostra posições e preço médio pessoais.
     Imagem quebrada no README é pior que README sem imagem, por isso está comentado. -->

---

## Por que existe

Decidir compra e venda exigia abrir três ou quatro fontes separadas e comparar de cabeça. Não havia registro de como um papel estava numa data passada, então não dava para responder à pergunta que mais importa: **a empresa melhorou ou piorou desde a última vez que eu olhei?**

Esse requisito — comparar a mesma nota em datas diferentes — é o que determina quase toda decisão de desenho abaixo.

## Como funciona

```
FONTES  ->  COLETA          HTTP com timeout, retry e mascaramento de token
                            loop restrito ao horário de pregão
        ->  PERSISTÊNCIA    SQLite, backup antes de alteração de schema
        ->  REGRAS          validação, mapa setorial, faixas, scoring
                            (não lê banco: DataFrame entra, DataFrame sai)
        ->  LEITURA         carregadores, ranking, benchmarks, diário de teses
        ->  SAÍDA           CSV -> Power BI (.PBIP)  ·  notebook de pesquisa (só lê)
```

Camadas com responsabilidade única e dependência em sentido único: a camada de cálculo não conhece o banco, e a camada de banco não conhece fórmula. É isso que permite testar as fórmulas com dados sintéticos, sem subir banco nem tocar a rede.

### Fontes

| Fonte | O que traz | Limite assumido |
|---|---|---|
| brapi | Cotações, histórico diário, Ibovespa | Plano gratuito: janela de 3 meses (63 pregões/chamada), 20 req/min |
| BolsAI | Fundamentos (ROE, ROIC, ROA, margens, dívida/patrimônio, CAGR 5a) | Cota diária — 1 coleta por ticker/dia, com deduplicação |
| Banco Central (SGS) | Selic (série 11), CDI (12), IPCA (433) | Aberta; data em formato BR e valor em string, normalizados na entrada |

### Banco — 7 tabelas, sem sobreposição de papel

`cotacoes` · `cotacoes_historicas` · `fundamentos` · `posicoes` · `transacoes` (append-only) · `indices` · `teses`

Duas tabelas de preço **de propósito**: juntar a série de coleta (várias linhas por dia) com a série de pregão (um ponto por dia, com OHLC) deixaria metade das colunas nula em metade das linhas, e qualquer agrupamento por ticker e data passaria a misturar duas naturezas sem avisar.

A coluna `tipo` em `indices` impede um erro silencioso: nível de índice rende por variação percentual, taxa diária rende por produtório. Somar taxa diária não estoura — só devolve número menor. Em 252 pregões a 0,0505% ao dia, somar dá **12,73%** e compor dá **13,57%**.

## A metodologia

Duas notas, **nunca somadas**:

- **`score_fundamentalista`** — cinco categorias de peso igual: Rentabilidade (ROIC 40%, ROE 35%, ROA 25%), Margens (líquida 60%, EBITDA 40%), Crescimento (CAGR receita 60%, lucro 40%), Segurança (dívida/patrimônio) e Valuation (earnings yield 50%, book-to-market 50%).
- **`score_reversao`** — mede **queda de preço, não barateamento**. Janela de 252 pregões sobre fechamento ajustado, mínimo de 60 observações. É uma aposta contrária declarada, e o nome foi escolhido para não ser lido como valuation.

### Cinco decisões, cada uma com o número que a motivou

<details>
<summary><b>1. Faixa absoluta, não relativa ao grupo</b></summary>

Quatro das cinco categorias pontuam pelo valor do indicador, nunca pela posição dentro da lista analisada. Sem isso, uma nota de 76 hoje e 62 em dezembro não distingue *"a empresa piorou"* de *"entraram papéis melhores na lista"* — e comparar o score no tempo é o objetivo do produto.

Efeito colateral importante: ampliar a carteira monitorada de 10 para 30 ativos deixa de invalidar todo o histórico.
</details>

<details>
<summary><b>2. Âncoras interpoladas, não degraus</b></summary>

A tabela de faixas implementada ao pé da letra criava penhascos: ROE de 14,9 valia 55 e ROE de 15,0 valia 80 — **25 pontos de diferença por um décimo de ROE**, enquanto a mesma variação no meio da faixa valia zero.

Medido na carteira real: um dos bancos estava a 2,38 pontos percentuais de uma borda que valia 10 pontos de score.
</details>

<details>
<summary><b>3. Escala relativa = winsorização + z-score + CDF, não min-max</b></summary>

Com min-max, o pior colocado tirava exatamente 0 e o melhor exatamente 100, sempre, fossem quais fossem os números — dois ativos quase empatados na ponta apareciam a 100 pontos de distância.

A nota passou a se ler como percentil: 96 significa "mais barato que cerca de 96% do universo". O achatamento usa `math.erf` da biblioteca padrão, para não puxar o SciPy por causa de uma função.

Efeito medido nas pontas: 0,00 → 4,35 e 100,00 → 96,03.
</details>

<details>
<summary><b>4. Crescimento em termos reais</b></summary>

Os dois CAGR chegam nominais da fonte e são deflacionados antes de pontuar, por composição e não por subtração.

O caso que motivou: uma empresa crescendo exatamente a inflação — portanto parada em termos reais — tirava **56,5** de nota. Passou a tirar **25**.

Deflator: média de 5 anos do IPCA (5,30%, de 29,47% acumulado na série 433 do SGS).
</details>

<details>
<summary><b>5. Dado ausente não vira nota</b></summary>

Sem imputação de mediana, sem nota neutra para indicador inaplicável. Indicador que não se aplica ao setor sai do cálculo e tem o peso redistribuído, e o ranking expõe a cobertura (`indicadores_usados` de `indicadores_aplicaveis`).

Nota 0 diz *"ruim"*; a verdade, quando o dado falta, é *"não dá para saber"*. São coisas diferentes.
</details>

### A flag que fica fora do score

`premio_negativo` compara o earnings yield contra a Selic vigente.

Um valuation relativo só sabe dizer quem é o menos caro do grupo. Se o grupo inteiro estiver caro, ele continua distribuindo notas de 5 a 95 como se houvesse barganha.

O resultado que justificou a tarefa: **7 dos 10 ativos pagavam menos que título público.** O caso mais claro foi um banco com nota de valuation 78,3 — o segundo mais "barato" do grupo — e prêmio de −1,33 p.p. sobre a Selic. As duas afirmações eram verdadeiras ao mesmo tempo, e só a segunda era sobre o mundo.

A flag é deliberadamente flag, e não nota: não entra em peso, categoria, ordenação nem cobertura. Um teste calcula o mesmo ranking com Selic de 2% e de 40% e exige score idêntico.

## Testes

**227 testes em 13 scripts**, cobrindo fórmulas, carregadores, coleta, exportação e validação. Nenhum deles toca a rede, e nenhum depende de pytest ou de qualquer dependência além das do `requirements.txt`.

Cada script roda sozinho e imprime o próprio resumo:

```bash
cd src
python test_scoring.py      # 39/39 testes passaram
python test_faixas.py       # 23/23
python test_exportar_bi.py  # 22/22
```

| Script | Testes |
|---|---|
| `test_scoring.py` | 39 |
| `test_faixas.py` | 23 |
| `test_exportar_bi.py` | 22 |
| `test_coletor.py` · `test_historico.py` | 21 cada |
| `test_indices.py` | 19 |
| `test_premio.py` · `test_validacao.py` | 15 cada |
| `test_teses.py` | 13 |
| `test_setores.py` | 12 |
| `test_pregao.py` · `test_valuation.py` | 10 cada |
| `test_analise.py` | 7 |

> `test_bolsai.py` não entra nessa conta: são nove linhas que chamam a API de fundamentos e imprimem a resposta, para conferir formato à mão. Toca a rede e gasta cota — rode só quando quiser inspecionar o retorno cru.

Padrão em toda mudança de lógica de cálculo: dados sintéticos, casos de borda explícitos e uma tabela de conferência impressa no final — para o resultado poder ser lido por um humano, não só aprovado por um `assert`.

Três testes que travam um erro específico, em vez de exercitar o caminho feliz:

- Entra com 6 ativos novos no universo e exige que a nota de um ativo existente **não se mova um décimo** — prova que a régua é absoluta.
- Calcula o ranking com Selic de 2% e de 40% e exige **score idêntico** — prova que a flag de prêmio não contamina a nota.
- **Falha quando a winsorização começar a fazer efeito.** Hoje ela quase não morde, por aritmética de percentil com amostra pequena; o teste existe para avisar no dia em que o comentário que explica isso ficar desatualizado.

Armadilha de unidade travada por teste: earnings yield é fração (`0,1961`) e Selic vem em ponto percentual (`13,65`). Comparar os dois crus marca 10 de 10 ativos como prêmio negativo, inclusive o que paga 6 pontos acima — e a tela fica plausível, porque erro de escala não parece erro, parece mercado caro.

## Camada de BI

A exportação é em CSV, não conexão direta ao banco. O motivo fraco é de instalação (o conector SQLite do Power BI depende de driver de terceiros com permissão de administrador). O motivo forte é **onde as regras moram**: as decisões de schema que já custaram caro ficam em Python testado, não espalhadas em M e DAX dentro de um binário.

Preço sai sempre da tabela de pregão e nunca da de coleta; data sai sempre em ISO; a tabela de índices já leva o fator diário pronto para o CDI ser composto e não somado.

O painel é versionado em `.PBIP` (formato de pasta, texto), então cada mudança de medida aparece em diff — foi isso que permitiu construir três telas editando o projeto fora do Power BI, com `git checkout` disponível quando quebrou. O `.pbix` binário fica fora do versionamento, para os dois formatos não divergirem em silêncio.

**A régua macro é gravada junto do resultado.** Uma flag que depende da Selic muda sozinha quando o Copom se move, e um gráfico dessa flag ao longo do tempo não separa "a ação ficou cara" de "a Selic subiu". Por isso cada exportação grava a Selic usada, a taxa diária crua, a data do ponto, a defasagem em dias e a fonte. O par (resultado, régua) fica guardado.

## Diário de teses

Registra, **antes da compra**: a premissa, o prazo e o critério de falha. Depois do prazo, confere o resultado contra o Ibovespa e contra o CDI.

- Prazo e critério são obrigatórios na abertura. Tese sem prazo não pode falhar, e só o que pode falhar ensina.
- Preço e score de abertura ficam congelados de propósito: a metodologia ainda muda, e a nota de hoje precisa continuar sendo a de hoje na hora de conferir.

É o antídoto contra racionalização posterior — a resposta para *"por que eu comprei isso?"* fica escrita antes de o resultado existir.

## Limitações conhecidas

Nenhuma destas é defeito de implementação. Estão aqui porque um sistema que esconde o próprio limite é pior que um que não tem a funcionalidade.

- **Janela curta de série.** O plano gratuito da fonte entrega 3 meses, não um ano. O score de reversão opera com janela parcial e o ranking mostra a razão (`64/252`) para que ninguém leia a nota como se fosse de série anual. Medido: acrescentar **um único pregão** moveu um ativo de 81,7 para 65,1 — 16,6 pontos num dia em que a ação subiu 3,7%.
- **Winsorização quase não morde com 10 ativos.** Aritmética de percentil, não falha de código: com amostra pequena, o percentil 95 cai entre o extremo e o vizinho. Um outlier de 900 numa série de 10 é puxado só até 503; numa de 30, até 37,6. A proteção efetiva hoje vem de limites fixos aplicados antes.
- **Feriado nacional em dia útil ainda dispara coleta** (~9 dias por ano). A janela de pregão olha dia da semana e hora; fechar isso exige calendário oficial da bolsa.
- **Universo pequeno** para normalização relativa e PCA terem significado estatístico pleno.
- **Benchmark de FII provisoriamente torto** — o índice setorial não devolve histórico pela API disponível, e comparar fundo imobiliário contra Ibovespa não é comparação justa.
- **Peso de 20% por categoria é escolha própria**, não vem de literatura. Sensibilidade testada em quatro cenários de peso: o primeiro e o último colocados não mudam em nenhum; o que se move é o meio da tabela.

## Rodando localmente

Requer **Python 3.12**.

```bash
git clone https://github.com/mrwtek/score-acoes-b3.git
cd score-acoes-b3
python -m venv venv && venv\Scripts\activate    # Windows
pip install -r requirements.txt
cp .env.example .env                            # preencha com os seus tokens
```

Variáveis em `.env`:

| Variável | Onde obter |
|---|---|
| `BRAPI_TOKEN` | brapi.dev — plano gratuito |
| `BOLSAI_TOKEN` | usebolsai.com — plano gratuito (cota diária) |

A API do Banco Central (SGS) é aberta e não exige token.

### Comandos

Rode de dentro de `src/`:

| Comando | O que faz |
|---|---|
| `python analise.py` | Imprime o ranking com os scores. **Não coleta nada** — só calcula sobre o que já está no banco |
| `python main.py` | Inicia o loop de coleta (dias úteis, 10h–18h de Brasília) e abre um menu: `checknow`, `whitelistshow`, `pause`, `resume`, `exit` |
| `python gerenciar_posicoes.py` | Menu de carteira: `buy TICKER QTD PRECO`, `sell TICKER QTD`, `show` |
| `python backfill_historico.py` | Baixa os últimos 3 meses de pregões de cada ticker. **Rode uma vez por mês** — a janela do plano gratuito desliza, e o que passar dela some para sempre |
| `python exportar_bi.py` | Gera os nove CSVs em `exports/bi/` para o Power BI ler. Só lê, não altera o banco |

Referência completa de cada script em [`COMANDOS.MD`](COMANDOS.MD).

O carregamento do `.env` usa caminho explícito e **falha imediatamente se faltar token** — de propósito. Antes disso, um `.env` fora do lugar devolvia token nulo, a biblioteca HTTP descartava o parâmetro nulo sem erro, e a API respondia como se a chamada fosse anônima: horas depurando um "erro de API" que era um arquivo na pasta errada.

## Estrutura

```
coletor.py        chamadas HTTP, retry, mascaramento de token
main.py           loop de coleta em thread + CLI
banco.py          SQLite: schema e gravação
paths.py          caminhos absolutos + backup com throttle
validacao.py      recusa indicador impossível
setores.py        o que não se aplica a cada setor
faixas.py         âncoras absolutas + interpolação + deflator
scoring.py        as fórmulas (não lê banco)
analise.py        carregadores + ranking
indices.py        benchmarks e contas de rendimento
teses.py          diário de teses
exportar_bi.py    camada de BI em CSV
analise.ipynb     bancada de pesquisa (PCA, ADF, ACF/PACF, ARIMA — só lê)
```

## Documentação

| Arquivo | Papel |
|---|---|
| `PRD` | Contexto, requisitos, modelo de dados alvo, roadmap, dívidas técnicas |
| `ESTADO.md` | Onde o trabalho parou e qual é a próxima tarefa |
| `DECISOES.md` | Append-only: por que cada escolha foi feita, com o número medido e a alternativa descartada |
| `COMANDOS.md` | O que cada script faz e como rodar |
| `POWERBI.md` | Como conectar, o que cada tela tem, medidas prontas e armadilhas do modelo |

A regra do `DECISOES.md`: se levou mais de cinco minutos pesando uma escolha, ela merece uma entrada. Três meses depois ninguém lembra do raciocínio, só do resultado — e fica tentado a "consertar" o que já estava certo.

Isso foi testado na prática: o projeto ficou 7 semanas parado e, na retomada, três coisas estavam fora do lugar. Foi o registro de decisões que permitiu diagnosticar e seguir sem refazer análise já feita.

## Backlog

- [ ] Universo para 20–30 ativos
- [ ] Módulo de carteira com resultado realizado
- [ ] Módulo de sinais (compra / manutenção / venda) com justificativa textual
- [ ] Versionamento da metodologia gravado junto de cada nota
- [ ] Tabela de snapshots com job diário
- [ ] Dashboard em Streamlit

## Stack

Python · pandas · NumPy · scikit-learn · statsmodels · matplotlib · seaborn · requests · python-dotenv · SQLite · Jupyter · Git · Power BI · DAX · Power Query (M)

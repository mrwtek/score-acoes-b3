# Dossiê do projeto — Sistema de análise e score de ações da B3

Documento de contexto completo, escrito para ser lido por uma pessoa ou por
outra IA que precise adaptar este conteúdo a um currículo, carta de
apresentação, portfólio ou entrevista.

Todos os números aqui vêm do próprio repositório (`ESTADO.md`, `DECISOES.md`,
`PRD_analise_acoes.txt`, histórico do git e contagem no código). Onde há
estimativa ou limitação conhecida, está dito no texto.

Período: setembro a outubro de 2026. Projeto pessoal, autoria individual.

---

## 1. O que é, em uma frase

Um sistema local em Python que coleta cotações, indicadores fundamentalistas e
benchmarks macroeconômicos de ações brasileiras, armazena tudo em SQLite,
calcula duas notas independentes por ativo (qualidade da empresa e queda de
preço) e entrega o resultado num painel de Power BI.

## 2. O problema de origem

A decisão de comprar ou vender uma ação dependia de abrir três ou quatro
fontes separadas — site de fundamentos, home broker, planilha de posições — e
comparar tudo de cabeça. Não existia registro de **como um papel estava numa
data passada**, então não havia como responder se a empresa tinha melhorado ou
piorado desde a última vez que foi avaliada.

O projeto consolida numa base local única: fundamentos, cotações, a carteira
própria, um score que resume "está boa" e "está barata", e o histórico desse
score para comparação ao longo do tempo.

## 3. O princípio de desenho que organiza tudo

> **O sistema não executa ordens e não decide nada.**

Ele automatiza coleta, cálculo e visualização. A decisão de compra e venda
continua inteiramente humana. Isso não é modéstia — é a fronteira que define o
escopo: não há robô de trade, não há integração com corretora, não há decisão
autônoma, e nenhuma saída do sistema é apresentada como recomendação.

A consequência prática aparece em quase toda decisão técnica do projeto: o
sistema prefere **dizer que não sabe** a inventar um número plausível.

## 4. Números do projeto

| Dimensão | Valor |
|---|---|
| Período de desenvolvimento | 01/09/2026 a 28/10/2026 |
| Commits | 44 |
| Linhas de Python | 7.817 (código + testes) |
| Módulos de aplicação | 13 |
| Arquivos de teste | 14 |
| Testes automatizados | 227 |
| Fontes de dados integradas | 3 (brapi, BolsAI, Banco Central/SGS) |
| Tabelas no banco | 7 |
| Ativos monitorados | 13 (10 ações + 3 FIIs) |
| Telas do painel Power BI | 6 |
| Visuais / medidas DAX / relacionamentos | 26 / 32 / 11 |
| Arquivos de documentação viva | 5 (PRD, estado, decisões, comandos, Power BI) |

## 5. Arquitetura

Organizada em camadas com responsabilidade única e dependência em sentido
único — a camada de cálculo não conhece o banco, e a camada de banco não
conhece fórmula.

```
  FONTES          brapi (cotações, histórico, Ibovespa)
                  BolsAI (fundamentos)
                  Banco Central / SGS (Selic, CDI, IPCA)
                        |
  COLETA          coletor.py      chamadas HTTP com timeout, retry e
                                  mascaramento de token
                  main.py         loop em thread + CLI, restrito ao pregão
                        |
  PERSISTÊNCIA    banco.py        SQLite, criação de tabelas, gravação
                  paths.py        caminhos absolutos + backup com throttle
                        |
  REGRAS          validacao.py    recusa indicador impossível
                  setores.py      o que não se aplica a cada setor
                  faixas.py       âncoras absolutas + interpolação + deflator
                  scoring.py      as fórmulas (não lê banco: DataFrame entra,
                                  DataFrame sai)
                        |
  LEITURA         analise.py      carregadores + ranking
                  indices.py      benchmarks e contas de rendimento
                  teses.py        diário de teses de investimento
                        |
  SAÍDA           exportar_bi.py  camada de BI em CSV
                  Power BI        painel de 6 telas, versionado em .PBIP
                  analise.ipynb   bancada de pesquisa livre (só lê)
```

**Separação entre motor e bancada.** O pipeline automático (coleta, score,
exportação) é independente do notebook de pesquisa exploratória. O notebook
lê do banco e nunca escreve, então qualquer experimento estatístico — PCA,
ADF, ACF/PACF, ARIMA — pode ser feito sem risco de quebrar o pipeline.

## 6. Fontes de dados e os limites reais de cada uma

**brapi** — cotações, histórico diário e Ibovespa. Plano gratuito: só os
intervalos de 1 dia a 3 meses, 20 requisições por minuto, concorrência 1. O
plano Pro, que daria série anual, custa R$ 139,99/mês (valor informado pela
própria API na resposta de erro). O teto é portanto 63 pregões por chamada, e
a janela desliza — o que passar dela sem ter sido coletado é perda permanente.

**BolsAI** — indicadores fundamentalistas (P/L, P/VP, ROE, ROA, ROIC, margens,
dívida/patrimônio, CAGR de receita e de lucro em 5 anos). Cota diária limitada
no plano gratuito, por isso os fundamentos são coletados uma vez por dia por
ticker, com deduplicação explícita.

**Banco Central (SGS)** — Selic (série 11), CDI (série 12) e IPCA (série 433).
API aberta, sem token. Devolve data em formato brasileiro e valor como string,
ambos normalizados na entrada.

O join entre as fontes é sempre por ticker, normalizado na escrita e nunca só
na leitura.

## 7. Modelo de dados

Sete tabelas em SQLite, cada uma com um papel que não se sobrepõe ao das
outras:

- `cotacoes` — série de **coleta**: várias linhas por dia, preço do momento.
- `cotacoes_historicas` — série de **pregão**: um ponto por dia, com OHLC e
  fechamento ajustado. É a tabela de retorno e série temporal.
- `fundamentos` — um registro por ticker por dia.
- `posicoes` — estado atual da carteira, com preço médio ponderado.
- `transacoes` — histórico append-only das operações.
- `indices` — benchmarks (IBOV, Selic, CDI) com uma coluna `tipo` que diz se o
  valor é nível de índice ou taxa diária.
- `teses` — diário de teses de investimento.

**Duas tabelas de preço, de propósito.** Juntar coleta e histórico obrigaria
metade das colunas a ficar nula em metade das linhas, e qualquer agrupamento
por ticker e data passaria a misturar duas naturezas diferentes sem avisar.

**A coluna `tipo` em `indices` impede um erro silencioso.** Nível de índice
rende por variação percentual; taxa diária rende por produtório. Somar taxa
diária não estoura — só devolve número menor. Em 252 pregões a 0,0505% ao dia,
somar dá 12,73% e compor dá 13,57%.

## 8. A metodologia de score — o coração do projeto

Duas notas independentes, nunca somadas:

**`score_fundamentalista`** — cinco categorias com peso de 20% cada:

| Categoria | Indicadores | Natureza da régua |
|---|---|---|
| Rentabilidade | ROIC 40%, ROE 35%, ROA 25% | absoluta |
| Margens | líquida 60%, EBITDA 40% | absoluta |
| Crescimento | CAGR receita 60%, CAGR lucro 40% | absoluta, em termos **reais** |
| Segurança | dívida/patrimônio 100% | absoluta |
| Valuation | earnings yield 50%, book-to-market 50% | relativa ao universo |

**`score_reversao`** — mede **queda de preço, não barateamento**. Janela de 252
pregões sobre o fechamento ajustado, mínimo de 60 observações. É uma aposta
contrária declarada, e o nome foi trocado justamente para que ninguém a leia
como valuation.

### As cinco escolhas metodológicas que sustentam o resto

**1. Faixa absoluta, não relativa.** Quatro das cinco categorias pontuam pelo
valor do indicador, nunca pela posição dentro da lista analisada. Sem isso, uma
nota de 76 hoje e 62 em dezembro não distingue "a empresa piorou" de "entraram
papéis melhores na lista" — e comparar o score no tempo é o objetivo principal
do produto. Efeito colateral importante: ampliar a whitelist de 10 para 30
ativos deixa de invalidar todo o histórico.

**2. Âncoras interpoladas, não degraus.** A tabela de faixas, implementada ao
pé da letra, criava penhascos: ROE de 14,9 valia 55 e ROE de 15,0 valia 80 — 25
pontos de diferença por um décimo de ROE, enquanto a mesma variação no meio da
faixa valia zero. Medido na carteira real, um dos bancos estava a 2,38 pontos
percentuais de uma borda que valia 10 pontos de score.

**3. A escala relativa é winsorização + z-score + CDF, não min-max.** Com
min-max, o pior colocado tirava exatamente 0 e o melhor exatamente 100,
sempre, fossem quais fossem os números. Dois ativos quase empatados na ponta
apareciam a 100 pontos de distância. A nota passou a se ler como percentil: 96
significa "mais barato que cerca de 96% do universo". A função de achatamento
veio do `math.erf` da biblioteca padrão, para não puxar o SciPy por uma função
só. Efeito medido nas pontas: de 0,00 para 4,35 e de 100,00 para 96,03.

**4. Crescimento em termos reais.** Os dois CAGR chegam nominais da fonte e são
deflacionados antes de pontuar, por composição e não por subtração. O caso que
motivou: uma empresa crescendo exatamente a inflação — portanto parada em termos
reais — tirava 56,5 de nota; passou a tirar 25. O deflator é a média de 5 anos
do IPCA (5,30%, medido na série 433 do SGS: 29,47% acumulado em cinco anos).

**5. Dado ausente não vira nota.** Não há imputação de mediana, não há nota
neutra para indicador inaplicável. Indicador que não se aplica ao setor sai do
cálculo e tem o peso redistribuído, e o ranking expõe a cobertura
(`indicadores_usados` de `indicadores_aplicaveis`). Nota 0 diz "ruim"; a
verdade, quando o dado falta, é "não dá para saber" — são coisas diferentes.

### A flag que fica fora do score

`premio_negativo` compara o earnings yield contra a Selic vigente. Um valuation
relativo só sabe dizer quem é o menos caro **do grupo**; se o grupo inteiro
estiver caro, ele continua distribuindo notas de 5 a 95 como se houvesse
barganha.

O resultado que justificou a tarefa: **7 dos 10 ativos pagavam menos que título
público**. O caso mais claro foi um banco com nota de valuation 78,3 — o segundo
mais "barato" do grupo — e prêmio de −1,33 ponto percentual sobre a Selic. As
duas afirmações eram verdadeiras ao mesmo tempo, e só a segunda era sobre o
mundo.

A flag é deliberadamente **flag, e não nota**: não entra em peso, categoria,
ordenação nem cobertura. Um teste calcula o mesmo ranking com Selic de 2% e de
40% e exige score idêntico nos dois. Misturá-la recriaria o score composto que
tinha sido removido justamente por esconder qual dos componentes estava falando.

## 9. Linha do tempo e marcos

### Fase 0 — Consolidação (até 01/09/2026)
Coleta das duas APIs funcionando, banco estruturado, join por ticker, CLI de
carteira com preço médio ponderado, primeira versão do score, notebook de
análise exploratória. Versionamento iniciado.

### Fase 1 — Fundação de dados (01/09 a 04/09)
- Caminho do banco resolvido de forma absoluta, a partir da raiz do projeto.
- Backup automático do `.db` antes de alterações de schema, com throttle diário.
- Tabela `transacoes` append-only + backfill a partir das posições existentes.
- Coluna ISO de data e hora ao lado das colunas em formato brasileiro, sem
  quebrar o que dependia delas.
- Valuation migrado de P/L e P/VP diretos para earnings yield e book-to-market.
- Coleta restrita ao horário de pregão, em fuso explícito de Brasília.
- Carregamento do `.env` com caminho explícito e falha imediata se faltar token.

### Hiato de sete semanas (04/09 a 26/10)
O projeto ficou parado. Ao retomar, três coisas estavam fora do lugar e foram
diagnosticadas antes de qualquer código novo: o arquivo de estado no disco
tinha regredido para uma versão antiga, a tabela de transações estava vazia
apesar de constar como concluída (provável restauração de backup anterior ao
backfill), e um dos arquivos de documentação nunca tinha entrado no git.

Esse episódio é a razão de a documentação do projeto ter o formato que tem.

### Fase 2 — Série histórica e benchmarks (26/10)
- Tabela `cotacoes_historicas` e backfill de preços diários — primeira carga de
  819 linhas, 63 pregões por ativo.
- Tabela `indices` com Ibovespa, Selic e CDI, e as contas de rendimento que
  distinguem nível de índice de taxa diária.
- Comparação ativo × Ibovespa × CDI disponível por linha de comando.

### Fase 3 — Revisão da metodologia de score (26/10 a 28/10)
O bloco mais denso do projeto. Em ordem:
- Lógica de score extraída para um módulo que não lê o banco, para poder ser
  testada com dados sintéticos. Ranking conferido byte a byte contra o
  baseline: idêntico.
- Camada de sanidade que recusa indicador impossível (margem acima de 100%,
  CAGR abaixo de −100%) e o trata como ausente, nunca como nota.
- Mapa de setor, com os indicadores que não se aplicam a financeiras.
- Fim do score composto e da imputação de mediana; cobertura exposta.
- Faixas absolutas interpoladas; margens viraram categoria própria.
- Score de reversão lendo a série histórica, com janela e flags explícitas.
- Crescimento deflacionado para termos reais.
- Escala relativa migrada de min-max para winsorização + z-score + CDF.
- Flag de prêmio sobre a Selic, com a régua gravada a cada exportação.

### Fase 4 — Camada de BI e painel (26/10)
- Exportador que lê o banco e grava CSVs modelados para consumo analítico.
- Painel de Power BI com 6 telas: Carteira, Desempenho contra benchmark,
  Ranking, Saúde dos dados, Ficha do ativo e Diário de teses.
- Painel versionado em formato texto (`.PBIP`) e editado fora do Power BI,
  clonando estruturas já existentes — o que torna cada alteração visível em
  diff e reversível por `git checkout`.

### Fase 5 — Robustez (28/10)
Timeout, retry com backoff e verificação de status nas chamadas de API; a
thread de coleta deixou de morrer com falha de rede.

## 10. Incidentes reais e o que cada um ensinou

Esta seção é a mais útil para entrevista, porque descreve falhas encontradas e
corrigidas, não funcionalidades entregues.

### O programa que parecia vivo
Uma interrupção de handshake TLS derrubou a thread de coleta. Como a thread é
daemon e o prompt interativo continuava respondendo a comandos, **nada na tela
indicava que a coleta tinha morrido**. O dano só apareceu ao conferir o banco.

A correção não foi só capturar a exceção. Foi distinguir o que adianta repetir:
erro de rede e 5xx repetem; 400, 401, 403 e 404 não, porque a resposta será a
mesma na segunda vez e insistir esconde o diagnóstico — "token não fornecido"
em um ativo enquanto outros passam é limite de plano, não falha de rede. O 429
espera o minuto inteiro, porque a janela de limite da API é por minuto.

A parte mais importante é a que não aparece: **o timeout**. Retry trata o
crash, que pelo menos deixa rastro. Sem timeout, o risco é pior — conexão
pendurada trava a thread para sempre, sem erro, sem traceback, sem nada para
investigar depois.

### O token que vazou no traceback
A API de cotações recebe o token na query string, e mensagem de exceção da
biblioteca HTTP costuma trazer a URL completa. Foi exatamente assim que um
token vazou num traceback. A correção fecha a origem: nada sai do coletor nem
da guarda da thread sem passar por uma função de mascaramento, e cada chamada
é identificada no log por descrição ("cotação de PETR4"), nunca por URL. Dois
testes travam isso.

O raciocínio registrado: o terminal vira print de tela, o print vira anexo, e o
anexo vira token público. E o conserto **não desfaz o vazamento** — o token
antigo continua precisando ser trocado, e isso ficou registrado como pendência
em aberto em vez de ser dado como resolvido.

### O ranking que rodava sobre o dado errado
Uma consulta escolhia o registro mais recente com `MAX(data)`, sobre uma coluna
de texto em formato brasileiro. SQLite compara texto caractere a caractere,
então "31/08/2026" saía maior que "14/09/2026", porque "3" é maior que "1".
Todos os ativos vinham sendo avaliados com o fundamento mais antigo do banco.

O que torna o caso instrutivo: **não dava erro**. A consulta devolvia
exatamente dez linhas, uma por ativo, com números plausíveis. Só eram os
números errados. O impacto medido foi pequeno — até 0,9 ponto, sem mudança na
ordem — mas só porque havia duas semanas de distância entre os registros; com
a coleta rodando por meses, o erro cresceria junto. A defesa que ficou são seis
testes sobre os carregadores, dois deles cobrindo virada de mês e de ano, que é
onde a comparação textual erra mais.

### A barra do pregão em formação
O histórico passou a ignorar o pregão do dia corrente. O sintoma que motivou:
o Ibovespa aparecia com amplitude de 20,98% no dia, contra 1,1% a 1,7% nos três
pregões anteriores; entre os ativos, dois bancos caíam 29% e 21% enquanto uma
mineradora e uma industrial subiam 4% — padrão que nenhum crash de mercado
produz. Como a gravação é idempotente e nunca corrige linha já gravada, o valor
parcial ficaria congelado errado para sempre, dentro de uma série que parece
confiável. Treze linhas foram removidas do banco.

### O arquivo de configuração fora do lugar
O arquivo de variáveis de ambiente foi parar numa subpasta durante manutenção.
A biblioteca de carregamento não avisa quando não encontra — apenas devolve
tokens nulos; a biblioteca HTTP então descarta o parâmetro nulo sem erro; e a
API responde como se a chamada fosse anônima. Resultado: horas depurando um
"erro de API" que era um arquivo fora do lugar. A correção transformou isso num
erro claro no momento do import.

### A mudança de tipo que travou o painel
Depois de corrigir o tipo de doze colunas, o projeto de BI parou de abrir com
erro de conversão. A causa: o leitor de CSV devolve string vazia para célula
vazia, e string vazia não vira número nem data. A regra que ficou — campo vazio
é ausência, vira nulo — é a mesma que já valia no motor de score para indicador
faltante. Em DAX o nulo é ignorado pelas agregações; a string vazia seria um
texto que nenhuma conta aceita.

## 11. Qualidade: como o projeto se defende de si mesmo

**227 testes automatizados** em 14 arquivos, cobrindo fórmulas, carregadores,
coleta, exportação e validação. Nenhum teste de coleta toca a rede.

O padrão adotado em toda mudança de lógica de cálculo: dados sintéticos, casos
de borda explícitos e uma tabela de conferência manual impressa no final — para
o resultado poder ser lido por um humano, não só aprovado por um assert.

Três exemplos de teste que travam um erro específico, em vez de só exercitar
o caminho feliz:

- Um teste entra com seis ativos novos no universo e exige que a nota de um
  ativo existente **não se mova um décimo** — é o que prova que a régua é
  absoluta e não relativa.
- Um teste calcula o ranking com Selic de 2% e de 40% e exige score idêntico —
  é o que prova que a flag de prêmio não contamina a nota.
- Um teste **falha quando a winsorização começar a fazer efeito**. Hoje ela
  quase não morde, por aritmética de percentil com amostra pequena; o teste
  existe para avisar no dia em que o comentário que explica isso ficar
  desatualizado.

Há também a armadilha de unidade que um teste trava antes de tudo: o earnings
yield é fração (0,1961) e a Selic vem em ponto percentual (13,65). Comparar os
dois crus marca 10 de 10 ativos como prêmio negativo, inclusive o que paga 6
pontos acima — **e a tela fica plausível, porque erro de escala não parece
erro, parece mercado caro**.

## 12. Documentação como parte do produto

Cinco arquivos mantidos vivos, com papéis distintos:

- **PRD** — a especificação: contexto, objetivos, requisitos funcionais e não
  funcionais, modelo de dados alvo, roadmap, backlog priorizado, dívidas
  técnicas e questões em aberto.
- **Estado** — onde o trabalho parou e qual é a próxima tarefa.
- **Decisões** — append-only, mais recente no topo, registrando **por que** cada
  escolha foi feita, com o número medido que a sustenta e a alternativa que foi
  descartada. A regra: se levou mais de cinco minutos pesando uma escolha, ela
  merece uma entrada.
- **Comandos** — o que cada script faz e como rodar.
- **Power BI** — como conectar, o que cada tela tem, as medidas prontas e as
  armadilhas do modelo.

O registro de decisões existe por um motivo prático: três meses depois ninguém
lembra do raciocínio, só do resultado — e fica tentado a "consertar" o que já
estava certo. Esse arquivo é o que permitiu retomar o projeto depois de sete
semanas sem refazer análises já feitas.

## 13. Camada de BI e painel

**A exportação em CSV foi escolhida em vez de conexão direta ao banco.** O
motivo fraco é de instalação — o conector de SQLite depende de driver de
terceiros com permissão de administrador, e a instalação local do Power BI roda
em sandbox. O motivo forte é **onde as regras moram**: as decisões de schema que
já custaram caro neste projeto ficam em Python testado, não espalhadas em M e
DAX dentro de um binário. Preço sai sempre da tabela de pregão e nunca da de
coleta; data sai sempre em ISO; a tabela de índices já leva o fator diário
pronto para o CDI ser composto e não somado.

**O arquivo de score é append e isso é de propósito.** O score não existe no
banco — é calculado na hora. Cada execução congela o snapshot do dia no CSV, o
que dá série de evolução sem antecipar a tabela de snapshots ainda não
construída. Rodar duas vezes no mesmo dia reescreve o dia, não duplica.

**A régua macro é gravada junto.** Uma flag que depende da Selic muda sozinha
quando o Copom se move, e um gráfico dessa flag ao longo do tempo não separa
"a ação ficou cara" de "a Selic subiu". Por isso cada exportação grava uma
linha com a Selic usada, a taxa diária crua, a data do ponto, a defasagem em
dias e a fonte. O par (resultado, régua) fica guardado.

**O painel é versionado em texto.** Em formato de pasta, cada mudança de medida
aparece em diff — e foi isso que permitiu construir três telas inteiras
editando o projeto por fora do Power BI, clonando estruturas já existentes, com
`git checkout` disponível quando quebrou. O arquivo binário equivalente fica
fora do versionamento, para os dois formatos não divergirem em silêncio.

## 14. O diário de teses

Funcionalidade que não estava no plano original e virou uma das mais usadas.
Registra, **antes** da compra: a premissa, o prazo e o critério de falha. Depois
do prazo, confere o resultado contra o Ibovespa e contra o CDI.

Duas regras explícitas:
- **Prazo e critério são obrigatórios na abertura.** Tese sem prazo não pode
  falhar, e só o que pode falhar ensina.
- **Preço e score de abertura ficam congelados de propósito.** A metodologia do
  score ainda muda; a nota de hoje precisa continuar sendo a de hoje na hora de
  conferir.

É o antídoto contra a racionalização posterior — a resposta para "por que eu
comprei isso?" fica escrita antes de o resultado existir.

## 15. Limitações conhecidas e assumidas

Registradas explicitamente em vez de escondidas. Nenhuma é defeito de
implementação:

- **Janela curta de série.** O plano gratuito da fonte entrega 3 meses, não um
  ano. O score de reversão opera com janela parcial e o ranking mostra a razão
  (`64/252`) para que ninguém leia a nota como se fosse de série anual. Medido:
  acrescentar **um único pregão** moveu um ativo de 81,7 para 65,1 — 16,6 pontos
  num dia em que a ação subiu 3,7%. Não é bug; é o que "64 de 252" quer dizer.
- **Winsorização quase não morde com 10 ativos.** Aritmética de percentil, não
  falha de código: com amostra pequena, o percentil 95 cai entre o extremo e o
  vizinho. Um outlier de 900 numa série de 10 é puxado só até 503; numa de 30,
  até 37,6. Hoje a proteção efetiva vem de limites fixos aplicados antes.
- **Feriado nacional em dia útil ainda dispara coleta** (~9 dias por ano). A
  janela de pregão olha dia da semana e hora; fechar isso exige calendário
  oficial da bolsa.
- **Universo pequeno** para normalização relativa e PCA terem significado
  estatístico pleno.
- **Benchmark de FII provisoriamente torto** — o índice setorial não devolve
  histórico pela API disponível, e comparar fundo imobiliário contra Ibovespa
  não é comparação justa.
- **Peso de 20% por categoria é escolha própria**, não vem da especificação.
  Testada a sensibilidade em quatro cenários de peso: o primeiro e o último
  colocados não mudam em nenhum; o que se move é o meio da tabela.

## 16. O que ficou planejado e ainda não foi feito

Ampliação do universo para 20–30 ativos; módulo de carteira com resultado
realizado; módulo de sinais de compra, manutenção e venda com justificativa
textual; versionamento da metodologia junto de cada nota gravada; tabela de
snapshots com job diário; dashboard em Streamlit.

A ordem do backlog foi **repriorizada** durante o projeto: com a régua absoluta
implementada, ampliar o universo deixou de recalibrar o score inteiro e saiu da
frente da fila. Todo o bloco de metodologia foi colocado antes dos snapshots,
para não gravar histórico numa escala que seria trocada depois.

## 17. Competências demonstradas

**Engenharia de dados**
Integração de três APIs com características diferentes (autenticação por query
string, por header, e aberta); normalização de formato e de fuso na entrada;
tratamento de limite de requisição e de cota; pipeline de coleta agendada com
deduplicação; backfill reexecutável e idempotente; modelagem de banco com
separação explícita de granularidade.

**Modelagem analítica e estatística**
Construção de índice composto multidimensional com pesos declarados;
normalização por winsorização, z-score e função de distribuição acumulada;
interpolação linear entre âncoras; deflação de séries para termos reais;
composição de taxas (produtório, não soma); análise de sensibilidade de
parâmetros; análise exploratória com PCA, ADF, ACF/PACF e ARIMA.

**Qualidade de software**
227 testes automatizados; separação de camadas para testabilidade; testes de
caso de borda e de regressão escritos a partir de falhas reais; tratamento de
erro que distingue o que vale repetir; mascaramento de segredo em log e
traceback; backup automático antes de alteração de schema.

**Business Intelligence**
Modelagem dimensional em fatos e dimensões; decisão arquitetural sobre onde as
regras de negócio devem morar; painel multi-tela com medidas DAX; versionamento
de artefato de BI em formato texto; documentação de modelo e de armadilhas.

**Comunicação técnica e processo**
Especificação de produto escrita antes da implementação; registro de decisões
com alternativa descartada e número medido; documentação de estado que permite
retomar depois de semanas; backlog priorizado e repriorizado com justificativa;
linguagem e nomenclatura consistentes em todo o código.

**Domínio de negócio**
Análise fundamentalista; estrutura do mercado de capitais brasileiro; custo de
capital local (Selic, CDI, IPCA) como régua em vez de parâmetro importado;
ajuste setorial para instituições financeiras; retorno total versus retorno de
preço; tributação de renda variável modelada no lugar certo (apuração mensal
consolidada, não por operação).

## 18. Stack

Python · pandas · NumPy · scikit-learn · statsmodels · matplotlib · seaborn ·
requests · python-dotenv · pytest · SQLite · SQL · Jupyter · Git · Power BI ·
DAX · Power Query (M) · APIs REST · ETL · Modelagem dimensional ·
Séries temporais

## 19. Três frases que resumem o projeto para quem tem pressa

1. Construí um sistema que coleta, pontua e visualiza ações da B3 — e que foi
   desenhado para nunca decidir nada, só para sustentar a decisão com dado
   rastreável.
2. A parte difícil não foi o código: foi descobrir que a régua estava errada
   três vezes — relativa quando devia ser absoluta, em degraus quando devia ser
   contínua, e nominal quando devia ser real — e corrigir cada uma medindo o
   efeito antes e depois.
3. O que o projeto ensinou cabe numa linha: **erro de escala não parece erro,
   parece mercado**; por isso cada decisão foi registrada com o número que a
   justifica e cada correção virou um teste.

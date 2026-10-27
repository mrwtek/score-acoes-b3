# Registro de decisões

Append-only, mais recente no topo. Registra **por que** algo foi escolhido,
não o que foi feito (isso está no ESTADO.md e no histórico do git).

Regra: se você levou mais de cinco minutos pesando uma escolha, ela merece
uma entrada aqui. Daqui a três meses você não vai lembrar do raciocínio, só
do resultado — e vai ficar tentado a "consertar" o que já estava certo.

---

## 26/10/2026 — Faixas absolutas interpoladas, não em degraus

**Decisão (P1-11):** as faixas da 7A viram **âncoras** e o meio é interpolado
em linha reta. As notas nas âncoras são exatamente as do PRD; o que muda é que
entre elas a nota varia de forma contínua. ROE 17,5 vira 90 em vez de 80.

**Por quê:** implementada ao pé da letra, a tabela cria penhascos. ROE 14,9
vale 55 e ROE 15,0 vale 80 — 25 pontos por 0,1 ponto de ROE, enquanto a mesma
variação no meio da faixa vale zero. Medido na carteira real, a ITUB4 estava a
2,38 p.p. de uma borda que valia 10 pontos de score.

Isso é ruim justamente para o O1. Acompanhando a empresa no tempo você não
conseguiria separar "a empresa mudou" de "a empresa cruzou uma linha
arbitrária" — e é para responder essa pergunta que os snapshots existem.

**O que isso não muda:** continua absoluto. A nota segue dependendo só do
valor do indicador, nunca de quem está na whitelist. O teste de aceite entra
seis tickers novos, incluindo extremos nos dois sentidos, e confere que a nota
da PETR4 não se move um décimo.

**Único ponto em que fui além da 7A:** onde o PRD diz "<X = 0" sem dizer onde
a reta encosta no zero, escolhi a âncora de baixo para a curva ficar contínua
em vez de criar um degrau novo. Vale para roe, roa, margem_liquida e os dois
CAGR, e está comentado no `faixas.py`.

---

## 26/10/2026 — Peso das categorias: 20% cada, e isso é provisório

**Decisão:** com margens virando categoria própria são cinco, e o PRD não diz
quanto cada uma vale nesse desenho. Adotei 20% para todas.

**Por quê:** é o default honesto quando não há base para preferir. Mas tem um
efeito que precisa ficar registrado: antes margens estava **dentro** de
rentabilidade, e as duas juntas valiam 25%. Com 20% cada, qualidade
(rentabilidade + margens) passa a valer **40%** do score — o oposto do motivo
da separação, que era tirar a dominância dessa categoria.

Agora a dominância é por decisão explícita e não por contagem de indicadores,
o que já é um ganho. Mas o número em si é meu, não do PRD.

**Medido:** a sensibilidade é menor do que eu esperava. Em quatro cenários de
peso (iguais, qualidade 25%, valor pesado, qualidade pesada), PETR4 fica em 1º
nos quatro e VALE3 em 10º nos quatro. O que muda é o meio da tabela — ISAE4 vai
de 6º para 2º no cenário "valor pesado". Então a escolha importa para decidir
entre papéis parecidos, não para o topo e o fundo.

---

## 26/10/2026 — Score de reversão: janela de 252, mínimo de 60, fechamento ajustado

**Decisão (P1-3):** o score de reversão passa a ler `cotacoes_historicas` em
vez de `cotacoes`, com janela fixa de 252 pregões, mínimo de 60 observações e
cálculo sobre o **fechamento ajustado**.

**Por que a troca de tabela era urgente:** `cotacoes` é a série de COLETA —
várias linhas por dia, só o preço do momento, e só nos dias em que o loop
rodou. Eram **7 observações** contra os 63 pregões reais que já existiam ao
lado. Na prática o sistema não enxergou a queda de 26/10: mostrava BBAS3 com
preço de R$ 22,20 (de 14/09) e nota de reversão 30,8, quando o papel estava a
R$ 17,47 na mínima de três meses.

**Por que o ajustado:** no dia do provento o preço cai sem a empresa ter
piorado. Com o fechamento cru, todo ex-dividendo entraria na conta como queda
— e o score de reversão existe justamente para medir queda.

**Por que 252 e 60:** 252 pregões é um ano de bolsa, a mesma janela da "máxima
e mínima de 52 semanas" que o mercado usa. Abaixo de 60 observações o range
não descreve distribuição nenhuma: com 20 pregões o último preço é quase
sempre a máxima ou a mínima, e a nota vira interruptor de 0 ou 100.

**Duas flags, não uma.** `dados_insuficientes` dispara abaixo de 60;
`janela_completa` só é verdadeira com 252. Hoje temos 63 pregões — passa do
mínimo e **falha a janela completa**, que é exatamente a situação que merece
aviso. Sem a segunda flag, 25% da janela passaria por série de um ano.

**Limitação que fica:** com 63 pregões a nota ainda é frágil. BBAS3 tira 100,0
porque está na mínima literal da janela. Não é erro de cálculo — é o que uma
janela curta permite dizer. O `63/252` no ranking existe para você não ler
esse 100 como se fosse de uma série anual.

---

## 26/10/2026 — Inaplicável é tratado como ausente, não como nota neutra

**Decisão:** no P1-12/P1-13, indicador que não se aplica ao setor sai do
cálculo e tem o peso redistribuído — o mesmo tratamento do dado faltante.
**Isto diverge da 7A.6 do PRD**, que pede "nota NEUTRA + flag `nao_aplicavel`".

**Por quê:** nota neutra continua sendo número inventado. Com 50 em segurança,
todo banco é puxado para o meio da escala por uma medida que ninguém fez — e
20% do score passa a ser preenchimento. A 7A.8 já define o mecanismo certo
("não pontuar, recalcular o peso sobre os disponíveis") para o dado ausente;
usar dois mecanismos para o mesmo problema só dobra o que precisa ser mantido.

A decisão original de 03/09 (nota neutra, nunca 0) nasceu do BBAS3 tirando 0,0
em segurança contra ITUB4 com 100. Excluir resolve isso igualmente bem — e sem
inventar o 50.

**O que preserva a comparabilidade:** as colunas `indicadores_usados`,
`indicadores_aplicaveis` e `categorias_usadas`. O score de um banco é média de
3 categorias e o da PETR4 de 5; isso agora está escrito na tabela em vez de
escondido. Se o número incomodar, é porque a informação por trás dele é mesmo
mais fina — e era isso que a nota neutra mascarava.

**Fácil de reverter** se preferir a letra do PRD: basta `_mascarar_nao_aplicaveis`
gravar 50 em vez de NaN.

---

## 26/10/2026 — Efeito colateral de ordenar P1-12/P1-13 antes do P1-11

**Registro, não decisão.** Tirar as financeiras do cálculo de dívida/PL deixou
a categoria segurança com **um indicador e cinco papéis**. Com min-max, isso
piorou o artefato que o P1-2 existe para corrigir: FIQE3 tira exatamente 0,0 e
WEGE3 exatamente 100,0, e a PETR4 desabou de 85,2 para 16,9 sem a empresa ter
mudado nada.

O número anterior era ruído (as financeiras alongavam a escala e faziam todo
mundo parecer seguro). O novo é artefato de amostra pequena. Nenhum dos dois é
medida.

**Isso é transitório e esperado:** o P1-11 troca min-max por faixa absoluta e
o problema desaparece — dívida/PL de 0,76 vira nota pela régua, não pela
companhia. Mas enquanto o P1-11 não chegar, **não use a coluna segurança para
decidir nada.**

Foi o preço de inverter a ordem. Valeu, porque o P1-11 agora entra num terreno
que já sabe o que é inaplicável e o que é ausente — mas o preço existe e está
aqui registrado.

---

## 26/10/2026 — BUG-01: o ranking rodava sobre o fundamento mais antigo

**O que era:** `carregar_fundamentos_mais_recentes()` escolhia a linha com
`MAX(data)`. A coluna `data` é texto em `dd/mm/aaaa`, e SQLite compara texto
caractere a caractere — então `'31/08/2026' > '14/09/2026'`, porque `'3' > '1'`.
Os dez tickers vinham pegando o registro de 31/08 em vez do de 14/09.

**Por que não apareceu antes:** não dava erro, não faltava linha, não havia
`NULL`. A consulta devolvia exatamente dez linhas, uma por ticker, com números
plausíveis. Só eram os números errados. É a falha que o `data_hora_iso` do P0-3
foi criado para evitar, numa consulta escrita antes dele existir.

**Impacto medido, e ele é menor do que parece:** só a categoria valuation mudou.
P/L e P/VP se movem com o preço todo dia; ROE, margens, CAGR e dívida/PL vêm de
balanço trimestral e eram idênticos nas duas datas. Maior diferença no
`score_geral` foi 0,9 ponto (ISAE4), e a ordem do ranking não mudou.

Isso não torna o bug inofensivo — só mostra que ele estava sendo mascarado por
duas semanas de distância entre os registros. Com a coleta rodando meses, as
duas datas se afastam e o erro cresce junto.

**O que ficou como defesa:** `test_analise.py`, seis testes sobre os
carregadores. Antes não existia nenhum, porque "escolher qual linha ler" não
parece lógica de cálculo — mas é a entrada de todo o cálculo. Dois dos testes
cobrem a virada de mês e a de ano, que é onde a comparação textual erra mais.
Conferido que a consulta antiga reprova no teste novo.

---

## 26/10/2026 — `scoring.py` não lê o banco

**Decisão:** no P1-1, em vez de mover o código inteiro, separar em duas
camadas: `scoring.py` recebe DataFrames e devolve DataFrames; `analise.py`
carrega do SQLite e orquestra.

**Por quê:** o bloco seguinte (P1-11 a P1-2) reescreve o miolo do cálculo, e o
CLAUDE.md pede teste com dados sintéticos e casos de borda em toda mudança de
lógica. Com o cálculo amarrado ao banco, conferir "ROE de 18% vira nota 80"
exige montar um banco temporário — foi o que precisei fazer no
`test_historico.py`, onde valeu a pena porque o que estava sob teste *era* a
gravação. Para uma fórmula, é maquinário demais.

Há também a questão de determinismo: teste que lê o `acoes.db` real muda de
resultado quando entram dados novos. Falha sem bug é o pior tipo de falha —
custa meia hora procurando defeito onde não tem.

**Não é padrão novo no projeto:** nove dos dez testes do `test_valuation.py` já
montavam DataFrame na mão e chamavam `normalizar()` direto. O P1-1 só terminou
de levar o código para onde o teste já estava.

**Custo aceito:** as assinaturas mudaram, então foi mais que recortar e colar.
Mitigado com `ranking_atual()` no `analise.py`, que mantém a chamada sem
argumentos para quem só quer o ranking.

**Alternativa descartada:** recorte-e-cole puro, com `scoring.py` lendo o banco.
Menor risco imediato, mas empurraria o atrito para as quatro tarefas seguintes.

---

## 26/10/2026 — O pregão do dia corrente nunca entra no histórico

**Decisão:** `salvar_cotacoes_historicas()` e `salvar_indices()` ignoram
qualquer ponto cuja data seja hoje (fuso da B3).

**Por quê:** a barra do dia em andamento vem inconsistente da brapi, e o
`INSERT OR IGNORE` nunca corrige uma linha já gravada — então um valor parcial
ficaria congelado errado para sempre, dentro de uma série que parece confiável.

Sintoma concreto que motivou, medido em 26/10/2026 às 17h43 (13 linhas já
tinham sido gravadas e precisaram ser removidas): o `^BVSP` aparecia com
amplitude de 20,98% no dia, contra 1,1%–1,7% nos três pregões anteriores.
Entre as ações, BBAS3 caía 29,33% e BBDC4 21,70% enquanto VALE3 subia 4,01% e
WEGE3 4,21% — padrão que nenhum crash de mercado produz. Os três FIIs, que
quase não oscilam, marcavam 6% a 9% de amplitude.

**Não é perda de informação:** o preço de hoje já está em `cotacoes`, que é a
série de coleta e existe justamente para isso. O histórico só precisa de
pregão fechado.

**Alternativa descartada:** gravar com `UPSERT` e deixar o dia seguinte
corrigir. Funcionaria, mas faria toda reexecução do backfill reescrever linhas
antigas — perderia a garantia simples de "rodar de novo não muda nada" e
abriria espaço para um dado ruim da fonte sobrescrever um dado bom.

---

## 26/10/2026 — `tipo` separa nível de índice de taxa diária

**Decisão:** a tabela `indices` guarda IBOV, Selic e CDI juntos, com uma
coluna `tipo` (`'preco'` ou `'taxa_diaria'`) em vez de tabelas separadas.

**Por quê:** são o mesmo formato (código, data, valor) com a mesma chave, mas
não se acumulam do mesmo jeito. Nível de índice rende por variação percentual
entre as pontas; taxa diária rende por produtório de (1 + valor/100). O `tipo`
é o que impede alguém de somar taxa diária achando que está certo — erro que
não estoura, só devolve número menor. Em 252 pregões a 0,0505% ao dia, somar
dá 12,73% e compor dá 13,57%; a tabela do `test_indices.py` mostra o erro
crescendo com o prazo.

**A taxa fica crua no banco**, como o BCB manda. Gravar acumulado obrigaria a
recalcular tudo a cada data inicial diferente e perderia o dado de origem.

**Selic e CDI vieram idênticos** nos 62 dias coletados (ambos 3,237%
acumulados). Mantidos os dois assim mesmo: custa duas linhas por dia e
protege o dia em que divergirem.

---

## 26/10/2026 — Histórico fica em tabela própria, não dentro de `cotacoes`

**Decisão:** criar `cotacoes_historicas` separada, em vez de gravar o histórico
da brapi dentro de `cotacoes`.

**Por quê:** são duas coisas diferentes com o mesmo nome. `cotacoes` é a série
de coleta: várias linhas por dia, só o preço do momento, hora granular de
propósito (sazonalidade intradiária). O histórico é um ponto por pregão, com
OHLC e fechamento ajustado, e sem hora. Juntar as duas obrigaria metade das
colunas a ficar nula em metade das linhas, e qualquer `GROUP BY ticker, data`
passaria a misturar as duas naturezas sem avisar.

**Efeito colateral:** quem for calcular retorno tem que saber qual tabela usar.
Regra: retorno e série temporal vêm de `cotacoes_historicas`; "preço agora" vem
de `cotacoes`.

---

## 26/10/2026 — O backfill de histórico é rotina, não script de uso único

**Decisão:** `backfill_historico.py` nasce reexecutável (`UNIQUE(ticker, data)`
+ `INSERT OR IGNORE`) e entra nas notas de operação como tarefa mensal. Difere
de `backfill_transacoes.py` e `migrar_datas_iso.py`, que rodaram uma vez.

**Por quê:** o plano free da brapi só entrega 3 meses, mas essa janela desliza
todo dia. Rodando periodicamente, a série no banco cresce além dos 3 meses e
buracos de coleta se fecham sozinhos — desde que o buraco ainda esteja dentro
da janela. É o que transforma um limite de plano em algo aproveitável a longo
prazo, sem pagar R$ 139,99/mês pelo Pro.

**O que isso custa:** se o projeto ficar parado mais de 3 meses, o pedaço que
passou da janela some para sempre neste plano. Em 26/10 o buraco de coleta de
14/09 ainda era recuperável; por volta de meados de dezembro não seria mais.

**Alternativa descartada:** yfinance, que dá anos de histórico de graça.
Descartada por ser dependência nova e fonte não-oficial. Decisão do usuário,
não limitação técnica — se a série curta incomodar, é para reabrir.

---

## 26/10/2026 — Data do histórico convertida no fuso da B3, não no da máquina

**Decisão:** `_data_do_ponto()` converte o epoch da brapi com
`ZoneInfo("America/Sao_Paulo")` explícito, em vez de `datetime.fromtimestamp()`
puro.

**Por quê:** a brapi manda a meia-noite de São Paulo (03:00 UTC). Com o fuso da
máquina, dá o dia certo aqui e em UTC — mas erra por um dia em qualquer fuso a
oeste de UTC-3, onde 03:00 UTC ainda é a véspera. Como a data é parte do
`UNIQUE`, o erro não apareceria como exceção: apareceria como linha duplicada
e retorno calculado errado.

**Dívida aceita:** `FUSO_B3` agora existe em `main.py` e em `banco.py`. Não
centralizei para não refatorar `main.py` fora da tarefa. Se um terceiro arquivo
precisar, vale mover para `paths.py`.

---

## 26/10/2026 — `adjustedClose` ausente vira NULL, não cópia do fechamento

**Decisão:** quando a API não manda o fechamento ajustado, gravar NULL.

**Por quê:** copiar o fechamento cru pareceria razoável e seria errado em
silêncio — esconderia proventos não contabilizados dentro de um número que diz
contabilizá-los. NULL deixa o buraco visível para quem for calcular retorno.
Na primeira carga, 422 das 819 linhas tinham ajustado diferente do fechamento,
ou seja, o campo carrega informação de verdade e não é decorativo.

**Vale lembrar:** o Ibovespa é índice de retorno total. Comparar ação contra
IBOV usando `fechamento` em vez de `fechamento_ajustado` subestima a ação em
todo dividendo pago. Para os FIIs da carteira, onde quase todo o retorno é
provento, o erro seria grosseiro.

---

## 04/09/2026 — Teto no earnings yield para evitar outlier de P/L quase zero

Decisao: earnings_yield capado em 1.0 (equivalente a P/L=1). Acima disso,
o valor e clampeado, nao descartado.
Por que: P/L positivo proximo de zero (ex.: 0.05) gera yield gigante (20.0)
que e legitimo mas distorce a normalizacao min-max de todo o universo.
Nao aplicado ainda a book-to-market (pvp) - fica pendente, mesmo problema
pode ocorrer com PVP proximo de zero. Ver P1-2 (winsorizacao substitui isso
de forma mais geral).

## 03/09/2026 — Metodologia de score: absoluto vs relativo

**Decisão:** rentabilidade, margens, crescimento e segurança passam a usar
faixas absolutas. Só valuation permanece relativo ao universo.

**Por quê:** o score era 100% relativo (min-max contra os tickers da
whitelist). Isso torna a comparação histórica impossível — se PETR4 tira 76
hoje e 62 em dezembro, não dá para saber se a empresa piorou ou se entraram
papéis melhores na lista. Como o objetivo O1 do produto é justamente comparar
scores no tempo (snapshots), a régua não pode se mexer junto com o universo.

Efeito colateral importante: ao ampliar a whitelist de 10 para 30 tickers,
todo o histórico anterior viraria incomparável. Com faixas absolutas, não vira.

**Alternativa descartada:** manter tudo relativo e normalizar os snapshots
retroativamente a cada mudança de universo. Complexo, e ainda assim não
resolve — a nota passaria a depender de uma decisão de composição de lista.

---

## 03/09/2026 — P/L e P/VP viram earnings yield e book-to-market

**Decisão:** usar `1/pl` (E/P) e `1/pvp` (B/P), ambos "maior melhor", em vez
de tratar valores negativos como caso especial.

**Por quê:** ranquear P/L negativo coloca empresas com prejuízo abaixo do
menor P/L positivo — quando na verdade são as mais caras. O inverso ordena
corretamente em todo o domínio, sem nenhum `if` no código. Ganho extra:
permite comparar duas empresas com prejuízo entre si (yield levemente negativo
é diferente de yield muito negativo).

É a solução padrão do mercado para esse problema, não um workaround.

**Alternativa descartada:** clamp de negativos para o pior valor. Funciona,
mas perde a ordenação entre as empresas com prejuízo e exige caso especial.

---

## 03/09/2026 — score_geral removido

**Decisão:** parar de calcular `score_geral = 0.6*fundamentalista + 0.4*preco`.
Ficam duas colunas independentes.

**Por quê:** as regras de sinal (RF-07) já usavam os dois scores separadamente,
então o composto não era consumido por nada. Ele só misturava "empresa boa" com
"caiu recentemente" num número único que esconde qual dos dois está falando.

Descoberta ao revisar: 0.6×25% (valuation) + 40% (preço) = 55% do score final
era alguma forma de "está barato". Um viés de valor muito mais agressivo do que
o desenho aparentava.

---

## 03/09/2026 — score_preco renomeado para score_reversao

**Decisão:** trocar o nome e documentar a natureza da aposta.

**Por quê:** a métrica não mede se a ação está barata, mede se ela caiu. Uma
ação pode cair 40% e ficar mais cara, se o lucro caiu 60%. O nome antigo
sugeria valuation e induzia leitura errada — exatamente o tipo de erro que
gera decisão ruim olhando um dashboard bonito.

Vale saber: é uma aposta contrária deliberada. A literatura de fatores
(Asness, Moskowitz, Pedersen) aponta na direção oposta — valor combinado com
momentum positivo tende a funcionar melhor que comprar o que está caindo.
Mantido como fator informativo, com o trade-off explícito.

---

## 03/09/2026 — margem_bruta sai do score

**Decisão:** manter a coluna no banco, remover do cálculo.

**Por quê:** é o indicador mais dependente de setor do conjunto — 25% é ótimo
para varejo e péssimo para software. Sem ajuste setorial, não informa nada
comparável entre VALE3 e ITUB4. Só adiciona ruído.

---

## 03/09/2026 — margens separadas de rentabilidade

**Decisão:** virar categoria própria.

**Por quê:** estavam juntas, dando 6 dos 11 indicadores a uma única categoria.
Ela dominava o score fundamentalista por peso de contagem, não por decisão
deliberada.

---

## 03/09/2026 — financeiras não pontuam alavancagem, ROA e margens

**Decisão:** nota neutra + flag `nao_aplicavel`, nunca 0.

**Por quê:** alavancagem é o modelo de negócio de um banco, não um defeito.
ROA de banco é estruturalmente baixo (1–2% é normal). Banco não tem EBITDA no
sentido usual. O Piotroski F-Score explicitamente não se aplica a bancos,
seguradoras e REITs pelo mesmo motivo.

Sintoma concreto que motivou: BBAS3 tirou 0.0 em segurança no ranking, contra
ITUB4 com 100 — ruído puro entrando na ordenação, com metade da carteira sendo
financeira.

**Alternativa descartada:** z-score dentro do setor (como faz a MSCI). Correto
em princípio, mas com 10–30 papéis não há massa — 2 ou 3 ações por setor não
formam distribuição. Fica para quando o universo comportar.

---

## 03/09/2026 — CAGR de lucro com cap e descarte

**Decisão:** cap em 30%; descartar com flag se o lucro do ano-base for ≤ 0.

**Por quê:** se o ano-base teve lucro perto de zero, o CAGR explode (+800%) ou
fica indefinido. Empresa que saiu de R$1mi para R$50mi aparece como crescimento
espetacular quando só normalizou.

---

## 03/09/2026 — faixas ancoradas ao custo de capital brasileiro

**Decisão:** não copiar faixas de tabela americana. Guardar
`SELIC_REFERENCIA` e `INFLACAO_REFERENCIA` em `config_scoring`.

**Por quê:** ROE de 12% nos EUA é aceitável; no Brasil, com Selic de dois
dígitos, é uma empresa que rende menos que título público sem o risco de ação.
CAGR nominal de 4% com inflação de 4,5% é encolhimento real.

Pendência registrada como Q8 no PRD: definir gatilho de revisão das faixas.

---

## 03/09/2026 — taxas em transacoes; IR fora

**Decisão:** a coluna `taxas` guarda apenas corretagem e emolumentos (custo por
operação). IR não entra em `transacoes`.

**Por quê:** IR sobre ações no Brasil não incide por operação — incide sobre o
resultado consolidado do mês, com compensação de prejuízo anterior e isenção
até R$20 mil de vendas no mês. Não existe "o IR desta venda". Um campo de IR
por linha modelaria errado: criaria um número que não significa nada sozinho.

Quando for implementado, vira apuração mensal separada, derivada de
`transacoes` — nunca gravada na transação em si.

---

## 02/09/2026 — .env com caminho explícito via paths.py

**Decisão:** `load_dotenv(RAIZ_PROJETO / ".env")` + erro imediato se algum
token vier vazio.

**Por quê:** o `.env` foi parar em `exports/` durante manutenção de arquivos e
o dotenv não avisa quando não encontra — apenas retorna tokens `None`
silenciosamente. O `requests` então descarta o parâmetro `token=None` sem erro,
e a API responde como se a chamada fosse anônima. Resultado: horas depurando um
"erro de API" que era um arquivo fora do lugar.

A falha rápida transforma isso num erro claro no momento do import.

---

## 02/09/2026 — data_hora_iso como coluna nova, não substituição

**Decisão:** adicionar `data_hora_iso` (e `data_operacao_iso`) ao lado das
colunas existentes, mantendo o formato `%d/%m/%Y` intacto.

**Por quê:** trocar o formato quebraria `ja_tem_fundamento_hoje()`, que compara
string exata contra `hoje()`. Adicionar é reversível e não quebra nada.

Hora mantida granular de propósito: permite analisar sazonalidade intradiária
(preço de manhã vs tarde) no futuro.

---

## 01/09/2026 — fazer_backup() com throttle diário

**Decisão:** no máximo um backup por dia, não um por execução. Sem rotação ou
limite de quantidade ainda.

**Por quê:** `criar_tabelas()` roda a cada start de `main.py` e
`gerenciar_posicoes.py`. Sem throttle, seriam vários backups idênticos por dia.

**Efeito colateral a lembrar:** se você já rodou algo hoje, o backup do dia já
foi "gasto" — antes de mudança de schema, fazer backup manual explícito.

---

## 01/09/2026 — transacoes é append-only; posicoes segue derivada

**Decisão:** `transacoes` guarda o histórico imutável. `posicoes` continua
existindo como tabela materializada, em vez de ser calculada on-the-fly.

**Por quê:** simplicidade de leitura no dashboard. Recalcular preço médio a
partir de todo o histórico a cada consulta é desnecessário nesta escala.
---

## Crescimento é pontuado em termos reais, não nominais (26/10/2026)

**Decisão:** os dois CAGR são deflacionados pela inflação antes de pontuar.
`INFLACAO_REFERENCIA` passou de 4,5 (chutado, e sem uso em cálculo nenhum)
para **5,30%** — o IPCA médio anualizado de 5 anos, medido na série 433 do
SGS/BCB: 29,47% acumulado entre out/2021 e set/2026.

**Por quê:** a régua nominal premiava repasse de preço. Empresa cuja receita
subiu 5,30% ao ano — exatamente a inflação, portanto parada em termos reais —
tirava **56,5** de nota. A própria seção 7A.2 do PRD chama isso de
encolhimento. O sintoma visível era a categoria ter parado de discriminar:
6 de 9 tickers acima do teto de 15% no CAGR de receita, 5 de 9 no de lucro,
e 22% de todas as notas de categoria exatamente em 100,0.

**Por que deflacionar o indicador em vez de subir as âncoras.** As duas contas
dão o mesmo número — conferido, diferença abaixo de 0,1 ponto. A escolha é de
onde a inflação entra:

- deflacionando, a tabela de âncoras continua dizendo uma relação econômica
  ("15% real = 100"), e revisar a inflação mexe numa constante;
- inflando as âncoras, a tabela vira `(21.09, 100.0)`, que não diz nada
  sozinho, e toda revisão de inflação é uma edição do `FAIXAS` — justamente o
  arquivo que o P1-11 criou para ser estável.

O custo é que o CAGR usado no score deixa de bater com o que se lê no
Investidor10. O valor nominal continua no banco, intacto.

**Descartada:** esticar o teto para 25% sem âncora econômica. Medido, tira os
empates no topo mas deixa a amplitude igual à de antes (83,8 contra 83,3) —
comprime embaixo o que descomprime em cima. Troca um artefato por outro.

**Por que o deflator é fixo e não puxado do BCB a cada rodada.** Medido na
carteira real: variar o deflator de 4,50% a 7,05% — a faixa inteira que o IPCA
de 5 anos percorreu nos últimos 17 anos — move o `score_fundamentalista` em no
máximo **4,3 pontos**, e não muda a ordem do ranking entre 4,50% e 5,89%. Como
a precisão não compensa, vale a simplicidade: um deflator dinâmico faria a nota
se mexer todo mês sem a empresa ter mudado, que é exatamente o ruído que o
P1-11 acabou de remover. Pendência Q8 do PRD: revisar quando o IPCA de 5 anos
sair da faixa de 4,5% a 6,5%.

**Efeito medido:** notas de categoria em 100,0 caíram de 22% para 15%; a
amplitude de crescimento subiu de 83,3 para 91,9; uma troca de posição no
ranking (ISAE4 passou a ITUB4). Foi barato fazer agora porque o `snapshots.py`
ainda não existe — não há histórico de score para invalidar. Depois que existir
e acumular meses, trocar a régua passa a custar caro.

**Limitação conhecida:** não sabemos a janela exata que a BolsAI usa no CAGR de
5 anos, então o deflator é aproximado. Um erro de um ano na janela vale 1 a 2
pontos de nota — irrelevante, pela medição de sensibilidade acima.

---

## P1-2: a escala relativa virou z-score com CDF, não min-max (26/10/2026)

**Decisão:** `normalizar()` (min-max) foi substituída por `nota_relativa()`:
winsoriza em p5/p95, calcula o z-score sobre o já winsorizado e mapeia de
volta para 0–100 pela CDF da normal padrão. Vale só no valuation, a única
categoria relativa.

**Por quê:** o min-max tinha um defeito estrutural. O pior colocado tirava
**exatamente 0** e o melhor **exatamente 100**, sempre, fossem quais fossem os
números — então dois tickers quase empatados na ponta apareciam a 100 pontos
de distância, e um único outlier esticava a régua e espremia todos os outros
no meio. Isso é artefato de escala, não informação.

**Por que CDF e não corte linear em ±2 desvios.** O z-score não tem limite e a
escala precisa ter, então falta um mapeamento. Cortar em ±2 e esticar
linearmente é mais simples, e com os 10 tickers de hoje as duas opções dão o
mesmo resultado — ninguém passa de 2 desvios. Mas com a whitelist em 30 (P1-8)
todo mundo além de 2 desvios voltaria a empatar em 0 e 100 exatos, que é
exatamente o artefato que este item veio remover. A CDF nunca chega às pontas.

Usar a CDF **não** afirma que o indicador é normalmente distribuído. Ela entra
como função de achatamento monótona e limitada: preserva a ordem e devolve
algo que se lê como percentil. Nota 96 quer dizer "mais barato que ~96% do
universo", não "está a tantos desvios numa normal".

Veio do `math.erf` da biblioteca padrão, para não puxar o scipy por uma função
só.

**Limitação medida, e vale conhecer:** a winsorização p5/p95 quase não faz
efeito com 10 tickers. Não é defeito da implementação, é aritmética de
percentil — com n pequeno, p95 cai *entre* o extremo e o vizinho dele, não
dentro do grupo. Medido: um outlier de 900 numa série de 10 é puxado só até
503; numa de 30, até 37,6. Nenhum percentil resolve isso com 10 pontos.

Na prática o valuation está protegido por outra coisa: `LIMITE_YIELD` (1,0) e
`LIMITE_BOOK_TO_MARKET` (5,0) cortam a métrica em
`adicionar_metricas_valuation()`, antes de chegar na escala. A winsorização é
a segunda linha de defesa e só passa a valer de verdade quando a whitelist
crescer. Está registrado no `teste_35`, que **falha se ela começar a morder** —
aí o comentário é que estará desatualizado.

**Efeito medido nas pontas:**

    earnings_yield    VALE3    0,00 -> 4,35     PETR4  100,00 -> 96,03
    book_to_market    WEGE3    0,00 -> 6,65     BBAS3  100,00 -> 96,12

A ordem do ranking não mudou. As notas de valuation dos 10 mudaram.

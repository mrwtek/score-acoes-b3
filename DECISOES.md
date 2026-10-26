# Registro de decisões

Append-only, mais recente no topo. Registra **por que** algo foi escolhido,
não o que foi feito (isso está no ESTADO.md e no histórico do git).

Regra: se você levou mais de cinco minutos pesando uma escolha, ela merece
uma entrada aqui. Daqui a três meses você não vai lembrar do raciocínio, só
do resultado — e vai ficar tentado a "consertar" o que já estava certo.

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
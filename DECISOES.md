# Registro de decisões

Append-only, mais recente no topo. Registra **por que** algo foi escolhido,
não o que foi feito (isso está no ESTADO.md e no histórico do git).

Regra: se você levou mais de cinco minutos pesando uma escolha, ela merece
uma entrada aqui. Daqui a três meses você não vai lembrar do raciocínio, só
do resultado — e vai ficar tentado a "consertar" o que já estava certo.

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
# Como este projeto foi construído

Este documento conta o que deu errado durante o desenvolvimento e o que cada erro deixou no código. É a porta de entrada para o [`DECISOES.md`](../DECISOES.md), que tem o raciocínio completo de cada escolha em 30 entradas — bom para consulta, ruim para leitura corrida.

Os números aqui foram medidos no próprio projeto. Onde há estimativa ou limite conhecido, está dito.

---

## Linha do tempo

O desenvolvimento aconteceu em duas janelas curtas e intensas, separadas por sete semanas de pausa.

| Fase | Quando | O que entrou |
|---|---|---|
| **0 — Consolidação** | até 01/09/2026 | Coleta das duas APIs, banco estruturado, join por ticker, carteira com preço médio ponderado, primeira versão do score, notebook exploratório |
| **1 — Fundação de dados** | 01/09 a 04/09 | Caminho do banco resolvido de forma absoluta; backup automático antes de alteração de schema; `transacoes` append-only com backfill; coluna ISO ao lado da brasileira; valuation migrado para earnings yield e book-to-market; coleta restrita ao pregão em fuso explícito; `.env` com falha imediata se faltar token |
| *(pausa)* | 04/09 a 26/10 | — |
| **2 — Série histórica** | 26/10 | Tabela `cotacoes_historicas` com backfill (819 linhas, 63 pregões por ativo); tabela `indices` com IBOV, Selic e CDI; comparação ativo × Ibovespa × CDI |
| **3 — Revisão da metodologia** | 26/10 a 28/10 | O bloco mais denso: scoring extraído para módulo sem banco, camada de sanidade, mapa setorial, fim do score composto, faixas interpoladas, score de reversão, crescimento real, escala por CDF, flag de prêmio |
| **4 — Camada de BI** | 26/10 | Exportador em CSV, painel de 6 telas, versionamento em `.PBIP` |
| **5 — Robustez** | 28/10 | Timeout, retry com backoff, verificação de status |

### A pausa de sete semanas

Na retomada, três coisas estavam fora do lugar, e foram diagnosticadas antes de qualquer código novo:

- o arquivo de estado no disco tinha regredido para uma versão antiga;
- a tabela `transacoes` estava vazia, apesar de constar como concluída — provável restauração de um backup anterior ao backfill;
- um dos arquivos de documentação nunca tinha entrado no git.

Esse episódio é a razão de a documentação do projeto ter o formato que tem. O `DECISOES.md` é append-only e registra, em cada entrada, **o número medido que sustentou a escolha e a alternativa descartada**. A regra adotada: se levou mais de cinco minutos pesando uma decisão, ela merece uma entrada. Três meses depois ninguém lembra do raciocínio, só do resultado — e fica tentado a "consertar" o que já estava certo.

---

## Seis coisas que deram errado

### 1. O ranking rodava sobre o dado errado

Uma consulta escolhia o registro mais recente de cada ativo com `MAX(data)`, sobre uma coluna de **texto em formato brasileiro**. SQLite compara texto caractere a caractere, então `"31/08/2026"` saía maior que `"14/09/2026"`, porque `3` é maior que `1`.

Todos os ativos vinham sendo avaliados com o fundamento **mais antigo** do banco.

O que torna o caso instrutivo é que **não dava erro**. A consulta devolvia exatamente dez linhas, uma por ativo, com números plausíveis. Só eram os números errados.

O impacto medido foi pequeno — até 0,9 ponto de score, sem mudança na ordem — mas só porque havia duas semanas de distância entre os registros. Com a coleta rodando por meses, o erro cresceria junto.

**O que ficou:** data gravada também em coluna ISO, e seis testes sobre os carregadores, dois deles cobrindo virada de mês e de ano, que é onde a comparação textual erra mais.

> Detalhe completo em `DECISOES.md` → *BUG-01: o ranking rodava sobre o fundamento mais antigo*.

### 2. O programa que parecia vivo

Uma interrupção de handshake TLS derrubou a thread de coleta. Como a thread é daemon e o prompt interativo continuava respondendo a comandos, **nada na tela indicava que a coleta tinha morrido**. O dano só apareceu ao conferir o banco.

A correção não foi só capturar a exceção, foi distinguir o que adianta repetir:

| Situação | Comportamento |
|---|---|
| Erro de rede, 5xx | repete com backoff |
| 400, 401, 403, 404 | **não** repete — a resposta será a mesma, e insistir esconde o diagnóstico |
| 429 | espera o minuto inteiro, porque a janela de limite da API é por minuto |

"Token não fornecido" em um ativo enquanto outros passam é limite de plano, não falha de rede. Repetir transformaria um diagnóstico claro em ruído.

**A parte mais importante é a que não aparece: o timeout.** Retry trata o crash, que pelo menos deixa rastro. Sem timeout, o risco é pior — conexão pendurada trava a thread para sempre, sem erro, sem traceback, sem nada para investigar depois.

> `DECISOES.md` → *P2-1: a thread de coleta engole exceção, de propósito*.

### 3. O token que vazou no traceback

A API de cotações recebe o token na query string, e mensagem de exceção de biblioteca HTTP costuma trazer a URL completa. Foi exatamente assim que um token vazou num traceback.

A correção fecha a origem: nada sai do coletor nem da guarda da thread sem passar por uma função de mascaramento, e cada chamada é identificada no log por descrição (`"cotação de PETR4"`), nunca por URL. Dois testes travam isso.

O raciocínio registrado na época: o terminal vira print de tela, o print vira anexo, e o anexo vira token público. E o conserto **não desfaz o vazamento** — o token antigo continuou precisando ser trocado, e isso ficou registrado como pendência em aberto em vez de ser dado como resolvido.

### 4. A barra do pregão em formação

O histórico passou a ignorar o pregão do dia corrente. O sintoma que motivou: o Ibovespa aparecia com amplitude de **20,98% no dia**, contra 1,1% a 1,7% nos três pregões anteriores. Entre os ativos, dois bancos caíam 29% e 21% enquanto uma mineradora e uma industrial subiam 4% — padrão que nenhum crash de mercado produz.

Como a gravação é idempotente e nunca corrige linha já gravada, o valor parcial ficaria congelado errado para sempre, dentro de uma série que parece confiável. Treze linhas foram removidas do banco.

> `DECISOES.md` → *O pregão do dia corrente nunca entra no histórico*.

### 5. O arquivo de configuração fora do lugar

O arquivo de variáveis de ambiente foi parar numa subpasta durante manutenção. A cadeia de silêncios:

1. a biblioteca de carregamento não avisa quando não encontra — apenas devolve tokens nulos;
2. a biblioteca HTTP descarta o parâmetro nulo sem erro;
3. a API responde como se a chamada fosse anônima.

Resultado: horas depurando um "erro de API" que era um arquivo fora do lugar. A correção transformou isso num **erro claro no momento do import**.

### 6. A mudança de tipo que travou o painel

Depois de corrigir o tipo de doze colunas, o projeto de BI parou de abrir com erro de conversão. A causa: o leitor de CSV devolve **string vazia** para célula vazia, e string vazia não vira número nem data.

A regra que ficou — campo vazio é ausência, vira nulo — é a mesma que já valia no motor de score para indicador faltante. Em DAX o nulo é ignorado pelas agregações; a string vazia seria um texto que nenhuma conta aceita.

> `DECISOES.md` → *Campo vazio no CSV vira nulo, não string vazia*.

---

## A armadilha que um teste pega antes de tudo

O earnings yield é fração (`0,1961`) e a Selic vem em ponto percentual (`13,65`). Comparar os dois crus marca **10 de 10 ativos** como prêmio negativo, inclusive o que paga 6 pontos acima da Selic.

E a tela fica plausível, porque **erro de escala não parece erro, parece mercado caro**.

Esse é o fio que liga os seis casos acima: nenhum deles quebrou o programa. Todos devolveram número plausível. Por isso cada decisão aqui foi registrada com o número que a justifica, e cada correção virou teste.

---

## O que o projeto ensinou

A parte difícil não foi o código. Foi descobrir que a régua estava errada três vezes — **relativa** quando devia ser absoluta, em **degraus** quando devia ser contínua, e **nominal** quando devia ser real — e corrigir cada uma medindo o efeito antes e depois.

As três correções estão no [`README`](../README.md), na seção de metodologia, com o número que motivou cada uma.

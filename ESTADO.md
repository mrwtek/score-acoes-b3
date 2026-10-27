# Estado do projeto

Atualizado em: 26/10/2026
Referência de prioridade: seção 10 do PRD v1.2

Atualize este arquivo ao fim de cada tarefa e commite junto. Ele é o que te
orienta quando você voltar ao projeto depois de um tempo parado.

---

## Concluído

### Base (antes do backlog)
- [x] `config.py` — tokens das duas APIs carregados via `.env`
- [x] `coletor.py` — brapi (cotações) e BolsAI (fundamentos) funcionando
- [x] `banco.py` — SQLite com `cotacoes`, `fundamentos`, `posicoes`
- [x] Dedupe diário de fundamentos (`ja_tem_fundamento_hoje`)
- [x] Join entre as duas fontes por `ticker`
- [x] `whitelist.py` — universo dinâmico (base ∪ tickers em carteira)
- [x] `main.py` — loop de coleta em thread + CLI
- [x] `gerenciar_posicoes.py` — CLI de carteira com preço médio ponderado
- [x] `analise.py` — score fundamentalista, score de preço, score geral
- [x] `analise.ipynb` — descritiva, correlação, PCA, ADF, ACF/PACF, ARIMA

### Setup do fluxo de trabalho
- [x] `git init` + primeiro commit
- [x] `.gitignore` (`.env`, `*.db`, `__pycache__/`, `.ipynb_checkpoints/`,
      `exports/`)
- [x] `CLAUDE.md`, `ESTADO.md`, `DECISOES.md` e PRD na raiz

### Backlog
- [x] **P0-2** caminho absoluto do banco (`src/paths.py`) — commit c54ab82
- [x] **P0-6** backup automático do `.db` (throttle diário) — em `paths.py`
- [x] **P0-1** tabela `transacoes` + backfill das posições
- [x] **P0-3** coluna `data_hora_iso` nas três tabelas + script de migração
- [x] **P0-4** valuation via earnings yield e book-to-market — commit a253fbe
- [x] **P0-5** coleta automática restrita ao pregão (dias úteis, 10h–18h,
      horário de Brasília) — `esta_no_horario_de_pregao()` em `main.py`;
      feriados nacionais ficaram fora de propósito, ver §Restrições
- [x] `config.py` com caminho explícito do `.env` + falha imediata se faltar
      token
- [x] Limpeza da posição de teste TESTE3
- [x] Revisão da metodologia de score (PRD v1.2, seção 7A + DECISOES.md)
- [x] **P3-4** backfill de preços históricos — tabela `cotacoes_historicas`,
      `buscar_historico()` em `coletor.py` e `backfill_historico.py`, com
      `test_historico.py` (15 testes). Primeira carga: 819 linhas, 63 pregões
      por ticker, 28/07 a 23/10/2026. **Puxado fora da ordem do backlog**, a
      pedido, antes do P1-1.
- [x] **Benchmarks** (tarefa não prevista no PRD) — tabela `indices` com IBOV
      (brapi) e Selic/CDI (BCB, API aberta), `indices.py`,
      `backfill_indices.py` e `test_indices.py` (18 testes). 62 linhas por
      série, mesmo período da série de preços. `python indices.py` imprime a
      comparação de rendimento ação × IBOV × CDI.
- [x] **P1-1** lógica de score extraída de `analise.py` para `src/scoring.py`.
      `scoring.py` não lê o banco: recebe DataFrames e devolve DataFrames, para
      o bloco P1-11→P1-2 poder ser testado com dados sintéticos. `analise.py`
      ficou com os carregadores e ganhou `ranking_atual()`. Ranking conferido
      byte a byte contra o baseline: **idêntico**.
- [x] **Sanidade dos indicadores** (tarefa nova, fora do PRD) — `validacao.py`
      recusa o impossível (margem acima de 100%, CAGR abaixo de −100%) e avisa
      sobre incoerência entre indicadores, sem remover. Único descarte nos
      dados atuais: margem líquida de 212% da ITSA4. Efeito grande, porque com
      min-max esse valor ancorava a escala de rentabilidade de todo mundo.
- [x] **P1-12** `setores.py` com setor por ticker; financeiras não pontuam ROA,
      margens nem dívida/PL. **BBAS3 deixou de tirar 0.0 em segurança** (aceite
      cumprido) e ITUB4 deixou de tirar 100.0 pela mesma razão invertida.
- [x] **P1-13** `score_geral` removido, `fillna(median)` removido, cobertura
      exposta (`indicadores_usados` de `indicadores_aplicaveis`). Categoria sem
      indicador sai do cálculo com o peso redistribuído, em vez de virar 0.
      Divergi da 7A.6 em um ponto: inaplicável é tratado como ausente, não com
      nota neutra. Justificado no DECISOES.md e fácil de reverter.
- [x] **P1-11** faixas absolutas em `src/faixas.py`, **interpoladas** entre as
      âncoras. Margens viraram categoria própria, `margem_bruta` saiu do score,
      cap de 30% no CAGR de lucro. Aceite cumprido: o teste entra seis tickers
      novos e a nota da PETR4 não se move.
      **A coluna segurança voltou a ser utilizável** — era 0,0 / 100,0 puro
      artefato, agora FIQE3 67,0, ISAE4 70,0, PETR4 72,0, VALE3 86,7.
      Peso das 5 categorias: 20% cada, número meu e não do PRD (DECISOES.md).
- [x] **P1-3** `score_reversao` (antigo `score_preco`) agora lê
      `cotacoes_historicas` pelo fechamento ajustado, janela de 252 pregões,
      mínimo de 60. Aceite cumprido: abaixo de 60 devolve 50 com flag.
      **O sistema passou a enxergar a queda de 26/10** — antes mostrava BBAS3
      a R$ 22,20 (preço de 14/09) com nota 30,8; agora R$ 17,47 e nota 100,0.
      Ressalva: com 63 de 252 pregões a nota ainda é frágil; o ranking mostra
      a razão `63/252` para isso ficar visível.
- [x] **Diário de teses** (tarefa nova, fora do PRD) — tabela `teses` e
      `src/teses.py`. Registra premissa, prazo e critério ANTES, e confere
      contra IBOV e CDI depois. Primeiras duas teses abertas em 26/10/2026
      (BBAS3 e BBDC4, queda pós-eleição), vencimento em 24/01/2027.
      Relacionado ao P1-4, mas não é a mesma coisa: o P1-4 fotografa o score,
      este guarda o raciocínio.
- [x] **BUG-01** `carregar_fundamentos_mais_recentes()` ordenava por `MAX(data)`
      textual (`dd/mm/aaaa`), então `31/08/2026` saía maior que `14/09/2026` e
      o ranking rodava sobre o fundamento mais antigo do banco. Trocado por
      `data_hora_iso`. Efeito medido: só a categoria valuation mudou (P/L e
      P/VP se movem com o preço; ROE, margens e CAGR vêm de balanço trimestral
      e eram iguais nas duas datas), com no máximo 0,9 ponto de diferença no
      `score_geral` e **ordem do ranking inalterada**. `test_analise.py` cobre
      a armadilha com 6 testes.
- [x] **Correção:** o pregão do dia corrente deixou de ser gravado no
      histórico. A barra em formação vinha inconsistente da brapi e o
      `INSERT OR IGNORE` a congelaria errada para sempre — 13 linhas do dia
      26/10 foram removidas do banco. Ver DECISOES.md.

- [x] **Camada de BI para Power BI** (tarefa nova, fora do PRD) —
      `src/exportar_bi.py` gera oito CSVs em `exports/bi/`, mais
      `meta_exportacao.csv`. Escolhido exportar em vez de ligar o Power BI
      direto no `.db`: o conector de SQLite depende de driver ODBC de
      terceiros instalado com admin, e o Power BI aqui é o da Microsoft Store,
      que roda em sandbox. A razão melhor é que as regras do schema ficam em
      Python testado, não espalhadas em DAX — preço sempre de
      `cotacoes_historicas`, data sempre ISO na saída, e `f_indice` com a
      coluna `fator_diario` pronta para o CDI ser composto e não somado.
      `test_exportar_bi.py` com 22 testes. Primeira exportação: 819 linhas de
      preço, 188 de índice, 70 de fundamento, 10 de score.
      **`f_score.csv` é append e não substitui o P1-4.** O score não existe no
      banco, só é calculado na hora; cada execução congela o snapshot do dia
      no CSV, o que dá a série de evolução sem antecipar o `snapshots.py`.
      Quando o P1-4 existir, a fonte do `f_score` passa a ser a tabela.
      Ressalva conhecida: os três FIIs (MXRF11, GARE11, BTCI11) não aparecem
      no `f_score` porque `calcular_ranking()` parte dos fundamentos e eles
      não têm. Ficam contados em `meta_exportacao.csv` em vez de entrar com
      nota inventada.
      `POWERBI.md` na raiz tem o passo a passo da primeira conexão, os
      relacionamentos e as medidas DAX prontas — inclusive as três que não se
      deve relacionar ao calendário (`f_posicao` e `f_tese` são estado, não
      período) e o que ainda não dá para montar (evolução de score só a
      partir do primeiro snapshot; resultado realizado não é calculável, o
      preço médio antigo não é guardado em nenhuma transação).

- [x] **AFINAR-FAIXAS** as âncoras de crescimento viraram **termos reais**.
      Os dois CAGR chegam nominais da BolsAI e `faixas.nota()` deflaciona
      antes de interpolar; as âncoras não mudaram de número, mudaram de
      significado — 15% ali agora quer dizer 15% acima da inflação.
      `INFLACAO_REFERENCIA` foi de 4,5 (chutado, e não usado em conta nenhuma)
      para **5,30%**, que é o IPCA médio de 5 anos medido na série 433 do
      SGS/BCB (29,47% acumulado entre out/2021 e set/2026).

      **O caso que motivou:** empresa crescendo 5,30% ao ano — exatamente a
      inflação, portanto parada em termos reais — tirava **56,5**. A 7A.2
      chama isso de encolhimento. Agora tira 25.

      Efeito medido: notas de categoria em 100,0 caíram de 22% para 15%; a
      amplitude de crescimento subiu de 83,3 para 91,9; uma troca no ranking
      (ISAE4 passou a ITUB4). Escolhido deflacionar o indicador em vez de subir
      as âncoras — as duas contas dão o mesmo número, a diferença é de onde a
      inflação entra. Ver DECISOES.md.

      **Deflator fixo de propósito**, não puxado do BCB a cada rodada: medido,
      variar o deflator de 4,50% a 7,05% (a faixa inteira dos últimos 17 anos)
      move o score em no máximo 4,3 pontos e não mexe na ordem entre 4,50% e
      5,89%. Um deflator dinâmico custaria notas se mexendo todo mês sem a
      empresa ter mudado — o ruído que o P1-11 acabou de tirar.

- [x] **P1-2** `normalizar()` (min-max) virou `nota_relativa()`:
      winsorização em p5/p95, z-score sobre o winsorizado e CDF normal para
      voltar a 0–100. Vale só no valuation, que é a única categoria relativa.
      A CDF sai do `math.erf` da biblioteca padrão — sem dependência nova.

      **Aceite cumprido.** Nas pontas, antes e depois:

          earnings_yield    VALE3    0,00 -> 4,35     PETR4  100,00 -> 96,03
          book_to_market    WEGE3    0,00 -> 6,65     BBAS3  100,00 -> 96,12

      A ordem do ranking não mudou; as notas de valuation de todos os 10
      mudaram. A nota agora se lê como percentil.

      **Escolhida a CDF em vez de corte linear em ±2 desvios.** Com 10 tickers
      ninguém passa de 2 desvios e as duas opções cumprem o aceite igual; com
      30 (P1-8) o corte linear voltaria a amarrar as pontas em 0 e 100 exatos.

      **Limitação medida, e importante:** a winsorização p5/p95 quase não faz
      efeito com 10 tickers — p95 cai entre o 9º valor e o 10º, então um
      outlier de 900 é puxado só até 503. Com 30 tickers vai até 37,6. Hoje
      quem segura outlier no valuation é o `LIMITE_YIELD` /
      `LIMITE_BOOK_TO_MARKET`, que cortam antes; a winsorização é a segunda
      linha e só passa a valer com a whitelist maior. Está no `teste_35`, que
      falha se um dia ela começar a morder (sinal de que o comentário
      envelheceu).

### Limpeza de 26/10/2026 (ao retomar o projeto)
Três coisas estavam fora do lugar depois de ~7 semanas parado:
- `ESTADO.md` no disco tinha regredido para a versão de 02/09; restaurado da
  versão commitada.
- `transacoes` estava vazia apesar do P0-1 constar como feito — provável
  restore de backup anterior ao backfill. `backfill_transacoes.py` e
  `migrar_datas_iso.py` rodados; 9 transações criadas.
- `COMANDOS.MD` nunca tinha entrado no git (o commit 81c2e7d só alterou o
  `CLAUDE.md`); agora versionado.

---

## Em andamento

- [ ] **Painel do Power BI** — montado em 26/10/2026 em `Power BI/`, nos dois
      formatos (`.PBIP/` em texto, `.PBIX/` binário). Abre-se pelo
      `Painel Analise B3.pbip`.

      **Pronto:** as 9 consultas via `fnLerBI` + parâmetro `PastaBI`, tipagem
      e cultura pt-BR (é o que faz o decimal com vírgula entrar como número),
      `dim_calendario` marcada como tabela de data, os 11 relacionamentos —
      e nenhum dos três que o `POWERBI.md` §1.7 manda não criar —, as 32
      medidas com formatação, e 3 das 6 telas: Carteira, Desempenho contra
      benchmark e Ranking.

      **Falta:** telas de Ficha do ativo (§3.4), Diário de teses (§3.5) e
      Saúde dos dados (§3.6), mais a segmentação por período na tela de
      benchmark. Essa última não é enfeite: as três medidas `base 100` usam
      `ALLSELECTED(dim_calendario)`, então sem um filtro de data elas nunca
      são reancoradas e o gráfico só sabe mostrar a série inteira.

      **Versionamento decidido em 26/10/2026:** vai para o git só o `.PBIP/`,
      com os 41 arquivos de definição em texto. Ficam de fora o `.PBIX/` (o
      mesmo painel em binário, que entraria em duplicidade e poderia divergir
      em silêncio), o `cache.abf` (cache que se regenera) e o
      `localSettings.json` (assinatura presa a esta máquina). Regras no
      `.gitignore`, razões no `POWERBI.md` §0.2.
      Quem clonar o repositório abre o `.pbip` com o painel inteiro e sem
      dados: `exports/bi/` também é gerado e fica fora do git.

- [ ] próxima tarefa de código: **P1-14**

---

## Próximas tarefas — ORDEM REPRIORIZADA (PRD v1.2 §10)

A ordem mudou depois da revisão de metodologia. **P1-8 (ampliar whitelist)
saiu da frente**: com faixas absolutas, ampliar a lista deixa de recalibrar o
score inteiro, então não precisa mais vir antes dos ajustes de fórmula.
Todo o bloco de score vem **antes** do P1-4, para não gravar snapshots numa
escala que será trocada.

### Bloco de score (o miolo da revisão)
- [ ] **P1-14** flag `premio_negativo` quando earnings yield < Selic

### Universo
- [ ] **P1-8** ampliar whitelist para 20–30 tickers

      **Bloqueado parcialmente:** o plano free da brapi entrega 3 meses (63
      pregões), não 252. A janela cheia só existe depois de uns 9 meses
      rodando `backfill_historico.py` periodicamente. Dá para implementar a
      flag agora e deixar a janela de 252 valendo quando a série alcançar.

### Carteira, sinais e histórico
- [ ] **P1-5** `carteira.py` — lucro absoluto, relativo, peso, resultado
      realizado
- [ ] **P1-6** `sinais.py` — compra/manter/venda com justificativa
- [ ] **VERSAO-SCORE** gravar sob qual metodologia cada score foi calculado:
      coluna no `f_score.csv` do `exportar_bi.py` e, quando o P1-4 existir,
      também na tabela de snapshots. Irmão do P1-4 — faça os dois juntos.

      **Por que, medido em 26/10/2026:** o AFINAR-FAIXAS (commit e95715a)
      entrou com o snapshot do dia já gravado na escala anterior. Crescimento
      caiu em 9 dos 10 tickers, ITSA4 foi de 55,0 para 47,2, e a ordem do
      ranking mudou num par — ITUB4 era 5º e virou 6º, trocando com ISAE4.
      Resolvido reexportando (o append é idempotente por dia), mas só deu
      para resolver assim porque havia **um** snapshot.
      Com a série mais longa, notas de réguas diferentes vão conviver no
      mesmo gráfico de linha parecendo evolução do papel quando são troca de
      régua. É o mesmo risco que a nota do topo desta seção antecipa, só que
      do lado de fora do banco.
      *Aceite:* um gráfico de score ao longo do tempo consegue separar — ou
      ao menos marcar — o ponto em que a metodologia mudou.
- [ ] **P1-4** `snapshots_score` + job diário
- [ ] **P1-7** dashboard Streamlit (Visão geral, Ranking, Carteira)

Depois: P1-9, P1-10 e a faixa P2 (robustez).

---

## Travas e decisões

### Resolvidas (ver DECISOES.md)
- ~~**Q5**~~ — universo vs setor: resolvida parcialmente em 02/09. Sem massa
  para z-score setorial com 10–30 papéis; adotado marcar setor e não pontuar
  o inaplicável (P1-12).
- ~~**Q7**~~ — taxas e IR: resolvida em 02/09. `taxas` = só corretagem e
  emolumentos; IR é apuração mensal separada, fora de `transacoes`.
- ~~**Q2**~~ — janela do score de reversão: adotado 252 pregões, mínimo de 60
  observações (PRD §RF-05).

### Abertas
- **Q1** — tamanho alvo da whitelist. Afeta o P1-8 e a cota das APIs.
  Não bloqueia mais o bloco de score (faixas absolutas).
- **Q3** — PCA/ARIMA entram no score como terceiro componente ou ficam só no
  notebook?
- **Q4** — dividend yield: entra em rentabilidade ou vira categoria própria?
- **Q8** — com que frequência revisar as faixas absolutas conforme Selic e
  inflação? Qual o gatilho?
- **Q9** — vale adicionar momentum 6–12m, dado que o `score_reversao` aposta
  na direção oposta? Depende de série de preço mais longa.

---

## Restrições conhecidas (não são bugs)

- **brapi**: o plano gratuito sem token cobre só PETR4, VALE3, MGLU3 e ITUB4.
  Com token, a cobertura depende do plano contratado. Se um ticker novo falhar
  com "token não fornecido", verificar o plano antes de suspeitar do código.
- **BolsAI**: cota diária limitada no plano free. Fundamentos são coletados uma
  vez por dia por ticker justamente por isso.
- **brapi, histórico**: o plano `free` só aceita os ranges `1d, 5d, 1mo, 3mo`.
  De `6mo` para cima exige o plano Pro (R$ 139,99/mês, valor informado pela
  própria API na resposta 400). Logo o teto é 63 pregões por chamada, e a
  janela desliza: em 26/10/2026 o alcance começava em 28/07/2026. **O que
  passar da janela sem ter sido coletado é perda permanente neste plano** —
  por isso `backfill_historico.py` precisa rodar de tempos em tempos.
- **brapi, limite de requisições**: 20 por minuto, concorrência 1 (headers
  `ratelimit-limit` e `x-brapi-concurrency-limit`). O backfill espaça as
  chamadas em 3,5s por causa disso.
- **IFIX não tem histórico**: `IFIX.SA` aparece em `/available`, mas com
  `range=3mo` devolve um único ponto (a cotação do dia). Como metade da
  carteira é FII, o benchmark deles fica provisoriamente torto — comparar FII
  contra Ibovespa não é comparação justa. Fica registrado para a tarefa dos
  índices.

---

## Notas de operação

- Rodar coleta: `python src/main.py` → `checknow` força uma coleta
- Registrar operações: `python src/gerenciar_posicoes.py`
- Ver ranking: `python src/analise.py`
- **Estender a série histórica: `cd src && python backfill_historico.py` e
  depois `python backfill_indices.py`.** Rodar os dois uma vez por mês. Juntos
  levam ~1 min, não duplicam nada se rodarem de novo, e são o que impede a
  série de ficar presa nos 3 meses da janela da brapi.
- Ver o que rendeu mais até agora: `cd src && python indices.py`
- Backup manual antes de mexer em schema (o automático tem throttle diário e
  pode já ter sido "gasto" hoje):
  `copy data\acoes.db data\acoes_backup_AAAAMMDD.db`
- Consultar o banco sem SQL na mão: pedir um script curto que imprime o
  resultado, em vez de digitar SQL no terminal.
- **Feriados**: a janela de pregão olha só dia da semana e hora. Feriado
  nacional que cai em dia útil (Natal numa terça, Carnaval, 7 de setembro)
  ainda dispara coleta, e o preço repetido do último fechamento entra na
  série. São ~9 dias por ano. Fechar isso pede calendário da B3 e é tarefa
  futura, não bug do P0-5.

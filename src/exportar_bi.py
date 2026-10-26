"""
Camada de BI: le o banco e grava CSVs em exports/bi/ para o Power BI ler.

Por que exportar em vez de ligar o Power BI direto no .db: o conector de
SQLite nao e nativo, depende de um driver ODBC de terceiros instalado com
admin, e a versao do Power BI Desktop instalada aqui vem da Microsoft Store,
que roda em sandbox e costuma nao enxergar o DSN. Exportar nao depende de
nada disso.

A razao melhor, porem, nao e a instalacao -- e onde as decisoes ficam. As
regras do schema que ja custaram caro neste projeto moram aqui, em Python
testado, e nao espalhadas em formulas M e DAX dentro de um .pbix:

- preco sai de `cotacoes_historicas`, nunca de `cotacoes` (a serie de coleta
  tem varias linhas por dia e so existe nos dias em que o loop rodou);
- data sempre em ISO na saida, inclusive a convertida do formato brasileiro
  (ordenar '31/08/2026' como texto poe agosto depois de setembro);
- taxa diaria de Selic e CDI sai com o fator do dia (1 + taxa/100) pronto,
  porque taxa diaria se compoe e nao se soma;
- `score_fundamentalista` e `score_reversao` saem lado a lado, nunca somados.

O f_score.csv e o unico arquivo em modo APPEND, e isso e de proposito: o
score nao e gravado no banco, so calculado na hora. Cada execucao acrescenta
o snapshot do dia, e e isso que vai permitir um grafico de evolucao de score
daqui a alguns meses. Rodar duas vezes no mesmo dia reescreve o dia, nao
duplica.

Rodar: cd src && python exportar_bi.py
"""

import sqlite3
from datetime import datetime

import pandas as pd

import analise
import setores
import teses as modulo_teses
from banco import TIPO_TAXA_DIARIA, hoje_b3, listar_teses
from indices import janela_comparavel
from paths import RAIZ_PROJETO, CAMINHO_BANCO
from whitelist import WHITELIST_BASE

PASTA_BI = RAIZ_PROJETO / "exports" / "bi"

# Formato brasileiro de CSV: ponto e virgula separa campo, virgula separa
# decimal. E o que o Power BI em portugues importa sem pedir ajuste de
# localidade coluna por coluna.
#
# Se o seu Power BI estiver configurado em ingles, troque para SEPARADOR = ","
# e DECIMAL = "." -- senao todo numero vai chegar como texto. Os dois precisam
# mudar juntos.
SEPARADOR = ";"
DECIMAL = ","

# utf-8-sig escreve o BOM, que e como o Power BI reconhece o acento sem que
# voce precise escolher 65001 na mao.
ENCODING = "utf-8-sig"

ARQUIVO_SNAPSHOT = "f_score.csv"
COLUNA_SNAPSHOT = "data_snapshot"


# --------------------------------------------------------------------------
# Conversoes. Ficam separadas do acesso ao banco para poderem ser testadas
# com dados sinteticos -- sao elas que erram em silencio, nao o SELECT.
# --------------------------------------------------------------------------
FORMATOS_DE_ENTRADA = (
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
)


def para_data_iso(texto):
    """Qualquer data do banco -> 'YYYY-MM-DD'. None se nao der para converter.

    O banco guarda tres formatos ao mesmo tempo: 'dd/mm/aaaa' em `data`,
    'dd/mm/aaaa HH:MM:SS' em `data_atualizacao` e ISO nas colunas `*_iso`.
    A saida e sempre ISO; hora e descartada, porque o grao de todo fato aqui
    e o dia.

    Devolver None em vez de levantar e deliberado: uma linha com data ilegivel
    aparece como vazia na tela de saude dos dados, em vez de derrubar a
    exportacao inteira.
    """
    if texto is None:
        return None
    texto = str(texto).strip()
    if not texto or texto.lower() in ("nan", "none", "nat"):
        return None

    for formato in FORMATOS_DE_ENTRADA:
        try:
            return datetime.strptime(texto, formato).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def fator_diario(valor, tipo):
    """(1 + taxa/100) para taxa diaria; None para nivel de indice.

    Existe para que o DAX nao precise saber dessa regra. Rendimento acumulado
    de CDI e PRODUCTX sobre esta coluna, e nao SUM sobre `valor`: em 252
    pregoes a 0,0505% ao dia, somar da 12,73% e compor da 13,57%.

    Para IBOV devolve None de proposito -- nivel de indice nao tem fator
    diario, e uma coluna vazia impede a conta errada melhor que um 1,0.
    """
    if tipo != TIPO_TAXA_DIARIA or valor is None:
        return None
    return 1 + float(valor) / 100


def mesclar_snapshot(anterior, novo, coluna_data=COLUNA_SNAPSHOT):
    """Append idempotente: o snapshot do dia substitui o do mesmo dia.

    Sem isso, rodar a exportacao tres vezes numa tarde criaria tres linhas
    para o mesmo ticker no mesmo dia, e qualquer media no Power BI passaria a
    pesar esse dia o triplo. Mesma logica do ja_tem_fundamento_hoje().
    """
    if anterior is None or anterior.empty:
        return novo.copy()
    if novo.empty:
        return anterior.copy()

    dias_do_novo = set(novo[coluna_data])
    mantido = anterior[~anterior[coluna_data].isin(dias_do_novo)]

    juntos = pd.concat([mantido, novo], ignore_index=True)
    ordem = [coluna_data] + (["ticker"] if "ticker" in juntos.columns else [])
    return juntos.sort_values(ordem).reset_index(drop=True)


# --------------------------------------------------------------------------
# Leitura do banco, uma funcao por arquivo de saida
# --------------------------------------------------------------------------
def montar_dim_ativo(conexao):
    """Um registro por ticker conhecido, com setor, classe e flags."""
    tickers = set(WHITELIST_BASE)
    for sql in (
        "SELECT DISTINCT ticker FROM cotacoes_historicas",
        "SELECT DISTINCT ticker FROM fundamentos",
        "SELECT DISTINCT ticker FROM posicoes",
        "SELECT DISTINCT ticker FROM transacoes",
        "SELECT DISTINCT ticker FROM teses",
    ):
        tickers |= {linha[0] for linha in conexao.execute(sql) if linha[0]}

    em_carteira = {
        linha[0] for linha in
        conexao.execute("SELECT ticker FROM posicoes WHERE quantidade > 0")
    }

    linhas = []
    for ticker in sorted(tickers):
        setor = setores.setor_de(ticker)
        linhas.append({
            "ticker": ticker,
            "setor": setor or "sem_setor",
            "classe": ("fundo_imobiliario"
                       if setor == setores.FUNDO_IMOBILIARIO else "acao"),
            "em_carteira": ticker in em_carteira,
            "na_whitelist_base": ticker in WHITELIST_BASE,
            "setor_mapeado": setor is not None,
            "indicadores_nao_aplicaveis": len(
                setores.indicadores_nao_aplicaveis(ticker)),
        })
    return pd.DataFrame(linhas)


def montar_f_preco_diario(conexao):
    """A serie de pregao. Sai de cotacoes_historicas, nunca de cotacoes.

    `data` ja nasce ISO nessa tabela. Leva os dois fechamentos: o ajustado,
    que e o que deve entrar em qualquer conta de rendimento, e o cru, que e o
    que aparece na tela do home broker e serve para conferencia.
    """
    return pd.read_sql_query("""
        SELECT ticker, data, abertura, maxima, minima,
               fechamento, fechamento_ajustado, volume
        FROM cotacoes_historicas
        ORDER BY ticker, data
    """, conexao)


def montar_f_indice(conexao):
    """IBOV, Selic e CDI, com o fator diario pronto para as taxas."""
    df = pd.read_sql_query("""
        SELECT codigo, data, valor, tipo
        FROM indices
        ORDER BY codigo, data
    """, conexao)
    if df.empty:
        df["fator_diario"] = []
        return df

    df["fator_diario"] = [
        fator_diario(valor, tipo) for valor, tipo in zip(df["valor"], df["tipo"])
    ]
    return df


def montar_f_fundamento(conexao):
    """Fundamentos com a data normalizada e o mais recente marcado.

    A coluna `data` da tabela esta em dd/mm/aaaa e nao ordena como texto; a
    saida leva `data` ja em ISO. `mais_recente` poupa o Power BI de refazer o
    desempate por ticker, que e justamente onde o BUG-01 nasceu.
    """
    df = pd.read_sql_query("""
        SELECT ticker, data, data_hora_iso, pl, pvp, roe, roa, roic,
               margem_liquida, margem_bruta, margem_ebitda,
               divida_patrimonio, cagr_receita_5a, cagr_lucro_5a
        FROM fundamentos
    """, conexao)
    if df.empty:
        df["mais_recente"] = []
        return df

    # a data_hora_iso manda quando existe; a `data` em formato BR e o reserva
    df["data"] = [
        para_data_iso(iso) or para_data_iso(data_br)
        for iso, data_br in zip(df["data_hora_iso"], df["data"])
    ]

    ordem = df["data_hora_iso"].fillna("")
    ultimo_por_ticker = ordem.groupby(df["ticker"]).transform("max")
    df["mais_recente"] = ordem.eq(ultimo_por_ticker) & ordem.ne("")

    return df.sort_values(["ticker", "data"]).reset_index(drop=True)


def montar_f_posicao(conexao):
    """Carteira atual, com o custo total ja somado."""
    df = pd.read_sql_query("SELECT * FROM posicoes ORDER BY ticker", conexao)
    if df.empty:
        return df

    df["data_atualizacao"] = [para_data_iso(v) for v in df["data_atualizacao"]]
    df["custo_total"] = df["quantidade"] * df["preco_medio"]
    return df


def montar_f_transacao(conexao):
    """Historico de compras e vendas, com valores ja calculados.

    `taxas` e so corretagem e emolumentos -- IR fica de fora, ver DECISOES.md.
    Por isso `valor_liquido` nao e resultado liquido de imposto, e sim o
    desembolso (compra) ou o recebimento antes de IR (venda).
    """
    df = pd.read_sql_query("""
        SELECT id, ticker, tipo, quantidade, preco,
               data_operacao, data_operacao_iso, taxas, observacao
        FROM transacoes
    """, conexao)
    if df.empty:
        df["data"] = []
        return df

    df["data"] = [
        para_data_iso(iso) or para_data_iso(br)
        for iso, br in zip(df["data_operacao_iso"], df["data_operacao"])
    ]
    df["valor_bruto"] = df["quantidade"] * df["preco"]

    # to_numeric antes do fillna: hoje `taxas` esta NULL em todas as linhas, e
    # uma coluna so de NULL volta do SQLite como object. Somar object com
    # float devolve object, e o to_csv so troca o ponto pela virgula em coluna
    # numerica -- o valor_liquido saia com separador decimal diferente do
    # resto do arquivo, que e exatamente o tipo de coisa que o Power BI le
    # como texto sem avisar.
    df["taxas"] = pd.to_numeric(df["taxas"], errors="coerce")

    # O fillna(0) vale para a CONTA, nao para a coluna: taxa ausente continua
    # ausente no arquivo. Gravar 0,0 onde nao se sabe afirmaria "nao houve
    # corretagem", que e diferente de "nao foi registrada".
    taxas = df["taxas"].fillna(0)
    sinal = df["tipo"].eq("compra").map({True: 1, False: -1})
    df["valor_liquido"] = df["valor_bruto"] + sinal * taxas

    return df.sort_values(["data", "ticker"]).reset_index(drop=True)


COLUNAS_DE_CONFERENCIA = (
    "medido_ate", "preco_atual", "retorno", "ibov", "cdi", "vs_ibov",
    "vs_cdi", "dias_corridos", "dias_restantes", "vencimento", "vencida",
)


def montar_f_tese(conferencia=True):
    """Teses do diario, com a conferencia contra IBOV e CDI ja feita.

    A conferencia reusa o teses.conferir(), que corta as tres series na
    ultima data comum. Repetir essa logica em DAX daria errado em silencio no
    dia em que o BCB atrasar mais que o costume.
    """
    registros = listar_teses()
    if not registros:
        return pd.DataFrame()

    linhas = []
    for tese in registros:
        linha = dict(tese)
        resultado = modulo_teses.conferir(tese) if conferencia else None

        if resultado is None:
            linha.update({coluna: None for coluna in COLUNAS_DE_CONFERENCIA})
        else:
            linha.update({
                "medido_ate": resultado["ate"],
                "preco_atual": resultado["preco_atual"],
                "retorno": resultado["retorno"],
                "ibov": resultado["ibov"],
                "cdi": resultado["cdi"],
                "vs_ibov": resultado["vs_ibov"],
                "vs_cdi": resultado["vs_cdi"],
                "dias_corridos": resultado["dias_corridos"],
                "dias_restantes": resultado["dias_restantes"],
                "vencimento": resultado["vencimento"],
                "vencida": resultado["vencida"],
            })
        linhas.append(linha)

    return pd.DataFrame(linhas)


def montar_f_score(data_snapshot=None):
    """O ranking de hoje, com a data em que foi calculado.

    O score nao mora no banco: `ranking_atual()` calcula na hora, sobre o
    fundamento mais recente de cada ticker. Congelar aqui e o que transforma
    "a nota de hoje" em serie.

    Quem nao tem fundamento nao aparece -- o ranking parte dos fundamentos, e
    os tres FIIs da carteira nao tem. Ausente nao vira nota: ficam de fora da
    tabela e aparecem contados na meta_exportacao.
    """
    ranking = analise.ranking_atual()
    if ranking.empty:
        return pd.DataFrame()

    df = ranking.reset_index().rename(columns={"index": "ticker"})
    df.insert(0, COLUNA_SNAPSHOT, data_snapshot or hoje_b3())
    return df


# --------------------------------------------------------------------------
# Gravacao
# --------------------------------------------------------------------------
def gravar(df, nome):
    """Grava um CSV na pasta de BI e devolve o caminho."""
    PASTA_BI.mkdir(parents=True, exist_ok=True)
    caminho = PASTA_BI / nome
    df.to_csv(caminho, index=False, sep=SEPARADOR, decimal=DECIMAL,
              encoding=ENCODING)
    return caminho


def gravar_snapshot(df, nome=ARQUIVO_SNAPSHOT):
    """Grava em modo append, trocando o snapshot do dia se ele ja existir."""
    PASTA_BI.mkdir(parents=True, exist_ok=True)
    caminho = PASTA_BI / nome

    anterior = None
    if caminho.exists():
        anterior = pd.read_csv(caminho, sep=SEPARADOR, decimal=DECIMAL,
                               encoding=ENCODING)

    combinado = mesclar_snapshot(anterior, df)
    combinado.to_csv(caminho, index=False, sep=SEPARADOR, decimal=DECIMAL,
                     encoding=ENCODING)
    return caminho, len(combinado)


def montar_meta(resumos, tickers_sem_score):
    """Uma linha por arquivo exportado, para a tela de saude dos dados.

    `janela_inicio` e `janela_fim` vem repetidos em todas as linhas de
    proposito: assim um cartao no Power BI le MAX(janela_fim) sem precisar de
    uma tabela so para dois valores.
    """
    inicio, fim = janela_comparavel()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    linhas = []
    for nome, df, coluna_data in resumos:
        datas = None
        if coluna_data and coluna_data in df.columns:
            datas = df[coluna_data].dropna()

        linhas.append({
            "arquivo": nome,
            "linhas": len(df),
            "data_min": datas.min() if datas is not None and len(datas) else None,
            "data_max": datas.max() if datas is not None and len(datas) else None,
            "janela_inicio": inicio,
            "janela_fim": fim,
            "tickers_sem_score": tickers_sem_score,
            "exportado_em": agora,
        })
    return pd.DataFrame(linhas)


def exportar_tudo():
    """Gera todos os arquivos e devolve (meta, tickers sem score)."""
    conexao = sqlite3.connect(CAMINHO_BANCO)
    try:
        dim_ativo = montar_dim_ativo(conexao)
        f_preco = montar_f_preco_diario(conexao)
        f_indice = montar_f_indice(conexao)
        f_fundamento = montar_f_fundamento(conexao)
        f_posicao = montar_f_posicao(conexao)
        f_transacao = montar_f_transacao(conexao)
    finally:
        conexao.close()

    f_tese = montar_f_tese()

    try:
        f_score = montar_f_score()
    except Exception as erro:
        print(f"AVISO: nao consegui calcular o ranking. O f_score.csv fica "
              f"como estava, com os snapshots anteriores. Motivo: {erro}")
        f_score = pd.DataFrame()

    com_score = set(f_score["ticker"]) if not f_score.empty else set()
    sem_score = sorted(set(dim_ativo["ticker"]) - com_score)

    escritos = []
    for nome, df, coluna_data in (
        ("dim_ativo.csv", dim_ativo, None),
        ("f_preco_diario.csv", f_preco, "data"),
        ("f_indice.csv", f_indice, "data"),
        ("f_fundamento.csv", f_fundamento, "data"),
        ("f_posicao.csv", f_posicao, "data_atualizacao"),
        ("f_transacao.csv", f_transacao, "data"),
        ("f_tese.csv", f_tese, "data_abertura"),
    ):
        gravar(df, nome)
        escritos.append((nome, df, coluna_data))

    if not f_score.empty:
        _, total = gravar_snapshot(f_score)
        print(f"{ARQUIVO_SNAPSHOT}: {len(f_score)} linhas do snapshot de "
              f"{f_score[COLUNA_SNAPSHOT].iloc[0]}, {total} no acumulado.")
        escritos.append((ARQUIVO_SNAPSHOT, f_score, COLUNA_SNAPSHOT))

    meta = montar_meta(escritos, ", ".join(sem_score))
    gravar(meta, "meta_exportacao.csv")

    return meta, sem_score


if __name__ == "__main__":
    meta, sem_score = exportar_tudo()

    print(f"\nExportado para {PASTA_BI}\n")
    print(meta[["arquivo", "linhas", "data_min", "data_max"]].to_string(index=False))

    inicio = meta["janela_inicio"].iloc[0]
    fim = meta["janela_fim"].iloc[0]
    print(f"\nJanela em que preco, IBOV e CDI existem juntos: {inicio} a {fim}.")
    print("Comparacao de rendimento no Power BI deve ficar dentro dela -- series")
    print("que terminam em dias diferentes nao comparam nada.")

    if sem_score:
        print(f"\nSem score fundamentalista: {', '.join(sem_score)}")
        print("Sao tickers sem fundamento no banco. FII nao tem mesmo, e a cota")
        print("diaria da BolsAI pode ter cortado os outros. Ficam de fora da")
        print("tabela de score em vez de entrar com nota inventada.")

    print(f"\nNo Power BI: Obter dados > Pasta > {PASTA_BI}")
    print(f"CSV em padrao brasileiro (separador '{SEPARADOR}', decimal "
          f"'{DECIMAL}').")
    print("Se os numeros chegarem como texto, o Power BI esta em outra")
    print("localidade -- o topo deste arquivo diz o que trocar.")

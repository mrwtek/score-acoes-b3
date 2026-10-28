"""
Coleta dos benchmarks: Ibovespa (brapi) e Selic/CDI (Banco Central).

Duas fontes, dois formatos, duas naturezas de dado:

- Ibovespa vem junto com o historico de acoes da brapi, pelo simbolo `^BVSP`.
  E um nivel de indice, entao o rendimento sai da variacao percentual entre
  duas datas. O Ibovespa ja e indice de retorno total (reinveste proventos),
  por isso o `adjustedClose` vem igual ao `close` - conferido em 26/10/2026,
  63 de 63 pontos identicos. Guardamos o fechamento.

- Selic e CDI vem do SGS do Banco Central, que e aberto e nao pede token.
  Sao taxas em % AO DIA, nao niveis: 0.052531 quer dizer 0,052531% naquele dia.
  Acumular e produtorio de (1 + valor/100), nunca soma.

O BCB publica a taxa de um dia depois do fechamento, entao essa serie chega
com dois ou tres dias de atraso em relacao ao Ibovespa. Em 26/10/2026 a brapi
ja tinha o dia 23/10 e o BCB tambem parava em 23/10, mas a defasagem varia.
Quem comparar rendimento acumulado precisa cortar as series na mesma data.
"""
import sqlite3
from datetime import datetime

import requests

from coletor import TIMEOUT_SEGUNDOS, buscar_historico
import faixas
from banco import TIPO_PRECO, TIPO_TAXA_DIARIA, _data_do_ponto, hoje_b3
from paths import CAMINHO_BANCO

# Simbolo na brapi -> codigo que usamos no banco. `^BVSP` e detalhe da fonte;
# dentro do projeto o indice se chama IBOV.
SIMBOLO_IBOV = "^BVSP"
CODIGO_IBOV = "IBOV"

# Series do SGS: 11 = taxa Selic diaria, 12 = CDI diario.
# https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados
SERIES_BCB = {
    "SELIC": 11,
    "CDI": 12,
}

URL_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados"

# O que cada codigo e, para o `tipo` da tabela indices.
TIPOS = {
    CODIGO_IBOV: TIPO_PRECO,
    "SELIC": TIPO_TAXA_DIARIA,
    "CDI": TIPO_TAXA_DIARIA,
}

CODIGO_SELIC = "SELIC"

# Pregoes num ano, para anualizar a taxa diaria do BCB. E a convencao da B3 e
# a mesma JANELA_REVERSAO do scoring.py: ano de bolsa tem 252 dias uteis, nao
# 365 corridos. Taxa diaria do SGS so existe em dia util.
PREGOES_NO_ANO = 252

# Faixa plausivel da Selic diaria, em % AO DIA. Serve para um ponto corrompido
# nao virar regua: 0,0508% ao dia da 13,65% ao ano, e 1% ao dia daria 1.100%.
# Mesma ideia do validacao.py -- o impossivel nao vira numero, vira ausente.
# O limite de baixo e aberto porque taxa zero existe (Selic a 0 nao e o caso
# brasileiro, mas zero no banco e quase sempre linha vazia convertida).
SELIC_DIARIA_MAXIMA = 0.5

# Procedencia da regua usada no premio do P1-14. Vai gravada no
# f_referencia.csv todo dia, porque a flag `premio_negativo` so quer dizer
# alguma coisa se voce souber contra o que ela comparou.
FONTE_SELIC_BANCO = "indices/BCB serie 11, anualizada em 252 pregoes"
FONTE_SELIC_FIXA = "faixas.SELIC_REFERENCIA (sem serie utilizavel no banco)"


def buscar_ibov(intervalo=None):
    """Devolve [(data_iso, fechamento)] do Ibovespa, ou None se a chamada falhar.

    Reusa o buscar_historico() do coletor, entao herda o mesmo teto de 3 meses
    do plano free da brapi.
    """
    pontos = buscar_historico(SIMBOLO_IBOV) if intervalo is None else buscar_historico(SIMBOLO_IBOV, intervalo)
    if pontos is None:
        return None

    convertidos = []
    for ponto in pontos:
        data_iso = _data_do_ponto(ponto)
        if data_iso is None or ponto.get("close") is None:
            continue
        convertidos.append((data_iso, float(ponto["close"])))
    return convertidos


def buscar_serie_bcb(nome, data_inicial, data_final=None):
    """Devolve [(data_iso, valor)] de uma serie do SGS, ou None se falhar.

    `nome` e uma chave de SERIES_BCB ('SELIC' ou 'CDI'). As datas entram e
    saem em ISO ('YYYY-MM-DD'); a conversao para o formato brasileiro que o
    BCB exige acontece aqui dentro.
    """
    if nome not in SERIES_BCB:
        raise ValueError(f"serie desconhecida: {nome!r}. Conhecidas: {sorted(SERIES_BCB)}.")

    params = {"formato": "json", "dataInicial": _para_formato_bcb(data_inicial)}
    if data_final is not None:
        params["dataFinal"] = _para_formato_bcb(data_final)

    url = URL_SGS.format(serie=SERIES_BCB[nome])

    try:
        resposta = requests.get(url, params=params, timeout=TIMEOUT_SEGUNDOS)
    except requests.RequestException as erro:
        print(f"ERRO de rede ao buscar {nome} no BCB: {erro}")
        return None

    if resposta.status_code != 200:
        print(f"ERRO HTTP {resposta.status_code} na serie {nome} do BCB: {resposta.text[:200]}")
        return None

    try:
        dados = resposta.json()
    except ValueError:
        # o SGS responde HTML quando o intervalo e invalido, em vez de JSON
        print(f"ERRO ao ler a resposta da serie {nome}: nao veio JSON. {resposta.text[:200]}")
        return None

    return _converter_pontos_bcb(dados, nome)


def _converter_pontos_bcb(dados, nome):
    """O SGS manda data em DD/MM/AAAA e valor como string. Normaliza os dois."""
    convertidos = []
    for item in dados:
        try:
            data_iso = datetime.strptime(item["data"], "%d/%m/%Y").strftime("%Y-%m-%d")
            valor = float(item["valor"])
        except (KeyError, ValueError, TypeError):
            print(f"[{nome}] pulando ponto que nao consegui converter: {item}")
            continue
        convertidos.append((data_iso, valor))
    return convertidos


def _para_formato_bcb(data_iso):
    return datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")


def acumular_taxa_diaria(pontos):
    """Rendimento acumulado de uma serie de taxas diarias, em %.

    pontos = [(data_iso, valor_percentual_do_dia)].
    Produtorio de (1 + valor/100), nao soma: 0,05% ao dia por 21 dias nao da
    1,05%, da 1,0552%. Com Selic de dois digitos e series longas a diferenca
    entre somar e compor deixa de ser detalhe -- em 252 pregoes a 0,0505% ao
    dia, somar da 12,73% e compor da 13,57%. Ver a tabela do test_indices.py.
    """
    acumulado = 1.0
    for _, valor in pontos:
        acumulado *= 1 + valor / 100
    return (acumulado - 1) * 100


def anualizar_taxa_diaria(taxa_diaria, pregoes=PREGOES_NO_ANO):
    """% ao dia -> % ao ano, compondo. Nao e multiplicar por 252.

    Mesma aritmetica do acumular_taxa_diaria(), so que projetada para a frente
    em vez de acumulada para tras: 0,050788% ao dia da 13,65% ao ano compondo
    e 12,80% multiplicando. Com a Selic de dois digitos, os 0,85 ponto de
    diferenca decidem sozinhos se uma acao com earnings yield de 13% tem
    premio positivo ou negativo.
    """
    return ((1 + taxa_diaria / 100) ** pregoes - 1) * 100


def variacao_percentual(pontos):
    """Rendimento de uma serie de niveis (IBOV), em %, do primeiro ao ultimo."""
    if len(pontos) < 2:
        return None
    primeiro = pontos[0][1]
    ultimo = pontos[-1][1]
    if not primeiro:
        return None
    return (ultimo - primeiro) / primeiro * 100


# --------------------------------------------------------------------------
# Leitura e comparacao
#
# O relatorio abaixo e um atalho util, nao o lugar definitivo disso: comparar
# rendimento da carteira contra benchmark e trabalho do carteira.py (P1-5) e
# do sinais.py (P1-6), que ainda nao existem. Quando existirem, estas funcoes
# de leitura ficam e o __main__ sai.
# --------------------------------------------------------------------------
def carregar_serie_indice(codigo, inicio=None, fim=None):
    """[(data_iso, valor)] de um indice, em ordem de data."""
    return _consultar(
        "SELECT data, valor FROM indices WHERE codigo = ?", (codigo.upper(),), inicio, fim
    )


def _dias_entre(data_inicial, data_final):
    """Dias corridos entre duas datas ISO. Negativo se a ordem se inverter."""
    inicial = datetime.strptime(data_inicial, "%Y-%m-%d")
    final = datetime.strptime(data_final, "%Y-%m-%d")
    return (final - inicial).days


def selic_anual_vigente(hoje=None):
    """A Selic anualizada mais recente do banco. E a regua do premio (P1-14).

    Devolve um dicionario com a taxa E a procedencia dela, nao so o numero.
    Isso e o ponto: desde que a regua passou a ser viva, a flag
    `premio_negativo` mudou de natureza -- ela pode virar sozinha, sem a
    empresa ter mudado, porque o Copom mexeu. Sem registrar contra o que se
    comparou, um grafico de flags ao longo do tempo mistura as duas coisas e
    nao da para separar depois. Quem grava isso dia a dia e o exportar_bi.py,
    em f_referencia.csv. E o mesmo problema que o VERSAO-SCORE levanta para a
    metodologia, aplicado a regua macro.

    DEFASAGEM NAO E MOTIVO PARA RECUSAR. O BCB publica com dois ou tres dias
    de atraso, e a coleta pode estar parada ha semanas, entao a taxa quase
    nunca e de hoje. A Selic e taxa de politica: fica parada entre reunioes do
    Copom -- os cinco ultimos pontos do banco em 28/10/2026 sao o mesmo
    0,050788. Recusar por estar velha trocaria uma regua de tres dias atras
    por uma constante de semanas atras, que e pior. A defasagem sai junto, em
    dias, para quem le poder julgar.

    Cai para faixas.SELIC_REFERENCIA quando nao ha serie no banco ou quando o
    ponto e implausivel. Nunca devolve None: sem regua a flag nao existe, e
    "nao sei" aqui apagaria a coluna inteira em vez de um valor.
    """
    pontos = carregar_serie_indice(CODIGO_SELIC)

    if pontos:
        data_ponto, taxa_diaria = pontos[-1]
        if taxa_diaria is not None and 0 < taxa_diaria <= SELIC_DIARIA_MAXIMA:
            return {
                "selic_anual": anualizar_taxa_diaria(taxa_diaria),
                "selic_taxa_diaria": taxa_diaria,
                "selic_data": data_ponto,
                "defasagem_dias": _dias_entre(data_ponto, hoje or hoje_b3()),
                "fonte": FONTE_SELIC_BANCO,
            }
        print(f"AVISO: Selic diaria implausivel no banco ({taxa_diaria} % a.d. "
              f"em {data_ponto}). Caindo para faixas.SELIC_REFERENCIA.")

    return {
        "selic_anual": faixas.SELIC_REFERENCIA,
        "selic_taxa_diaria": None,
        "selic_data": None,
        "defasagem_dias": None,
        "fonte": FONTE_SELIC_FIXA,
    }


def carregar_serie_ticker(ticker, inicio=None, fim=None):
    """[(data_iso, fechamento_ajustado)] de uma acao, em ordem de data.

    Usa o ajustado, nao o fechamento cru: o Ibovespa e indice de retorno total
    (reinveste proventos), entao comparar preco cru contra ele subestima a acao
    em todo dividendo pago. Linhas sem ajustado ficam de fora em vez de entrar
    com o fechamento no lugar.
    """
    return _consultar(
        "SELECT data, fechamento_ajustado FROM cotacoes_historicas "
        "WHERE ticker = ? AND fechamento_ajustado IS NOT NULL",
        (ticker.upper(),), inicio, fim,
    )


def _consultar(sql, parametros, inicio, fim):
    """Acrescenta o recorte de datas. Os dois SQLs acima ja trazem um WHERE."""
    if inicio is not None:
        sql += " AND data >= ?"
        parametros = parametros + (inicio,)
    if fim is not None:
        sql += " AND data <= ?"
        parametros = parametros + (fim,)
    sql += " ORDER BY data"

    conexao = sqlite3.connect(CAMINHO_BANCO)
    linhas = conexao.execute(sql, parametros).fetchall()
    conexao.close()
    return linhas


def rendimento(codigo_ou_ticker, tipo, inicio=None, fim=None):
    """Rendimento em % no periodo, escolhendo a conta certa pelo `tipo`."""
    if tipo == TIPO_TAXA_DIARIA:
        return acumular_taxa_diaria(carregar_serie_indice(codigo_ou_ticker, inicio, fim))
    if tipo == TIPO_PRECO:
        return variacao_percentual(carregar_serie_indice(codigo_ou_ticker, inicio, fim))
    raise ValueError(f"tipo invalido: {tipo!r}")


def janela_comparavel():
    """Maior janela em que preco de acao, IBOV e CDI existem ao mesmo tempo.

    Devolve (inicio, fim). As fontes nao terminam no mesmo dia -- o BCB publica
    a taxa com alguns dias de atraso -- e comparar rendimento acumulado sobre
    janelas diferentes nao compara nada.
    """
    conexao = sqlite3.connect(CAMINHO_BANCO)
    faixas = conexao.execute("""
        SELECT MIN(data), MAX(data) FROM cotacoes_historicas
        UNION ALL
        SELECT MIN(data), MAX(data) FROM indices GROUP BY codigo
    """).fetchall()
    conexao.close()

    faixas = [faixa for faixa in faixas if faixa[0] is not None]
    if not faixas:
        return None, None
    return max(faixa[0] for faixa in faixas), min(faixa[1] for faixa in faixas)


def _tickers_no_banco():
    conexao = sqlite3.connect(CAMINHO_BANCO)
    linhas = conexao.execute(
        "SELECT DISTINCT ticker FROM cotacoes_historicas ORDER BY ticker"
    ).fetchall()
    conexao.close()
    return [linha[0] for linha in linhas]


def _imprimir_comparacao():
    inicio, fim = janela_comparavel()
    if inicio is None:
        print("Sem dados. Rode backfill_historico.py e backfill_indices.py antes.")
        return

    cdi = rendimento("CDI", TIPO_TAXA_DIARIA, inicio, fim)
    ibov = rendimento(CODIGO_IBOV, TIPO_PRECO, inicio, fim)
    if cdi is None or ibov is None:
        print("Faltam CDI ou IBOV no banco. Rode backfill_indices.py antes.")
        return

    print(f"Rendimento de {inicio} a {fim} -- janela em que todas as series existem.")
    print("Acoes pelo fechamento ajustado; IBOV por variacao; CDI composto.\n")

    linhas = []
    for ticker in _tickers_no_banco():
        serie = carregar_serie_ticker(ticker, inicio, fim)
        retorno = variacao_percentual(serie)
        if retorno is not None:
            linhas.append((ticker, retorno, len(serie), serie[0][0], serie[-1][0]))

    linhas.sort(key=lambda linha: linha[1], reverse=True)

    print(f"{'ativo':10s} {'rend %':>8s} {'vs CDI p.p.':>12s} {'pregoes':>8s}  periodo coberto")
    for ticker, retorno, pregoes, primeiro, ultimo in linhas:
        print(f"{ticker:10s} {retorno:8.2f} {retorno - cdi:12.2f} {pregoes:8d}  {primeiro} -> {ultimo}")

    print(f"\n{CODIGO_IBOV:10s} {ibov:8.2f} {ibov - cdi:12.2f}   <- indice")
    print(f"{'CDI':10s} {cdi:8.2f} {0.0:12.2f}   <- referencia\n")

    print("Rendimento passado nao e previsao. Um papel acima do CDI aqui so quer")
    print("dizer que rendeu mais no periodo -- nao que vai render, e nem que o")
    print("risco dos dois seja comparavel. O CDI entregou o dele com quase certeza.")
    print("\nFII comparado contra Ibovespa e comparacao torta: o benchmark deles")
    print("seria o IFIX, que o plano free da brapi nao entrega com historico.")


if __name__ == "__main__":
    _imprimir_comparacao()


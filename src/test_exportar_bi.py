"""Testes da camada de BI (exportar_bi.py).

Roda sem pytest, no mesmo estilo dos outros scripts de teste do projeto:

    cd src && python test_exportar_bi.py

Dados sinteticos e banco em memoria. Nao toca no data/acoes.db nem em
exports/bi/, e nao chama API nenhuma.

O que esta sendo testado aqui sao as tres conversoes que erram em SILENCIO --
data em formato brasileiro, fator de taxa diaria e append do snapshot. Um
SELECT errado aparece na tela; uma data ordenada como texto nao.
"""

import sqlite3

import pandas as pd

from exportar_bi import (
    COLUNA_SNAPSHOT,
    fator_diario,
    mesclar_snapshot,
    montar_f_fundamento,
    montar_f_indice,
    montar_f_transacao,
    para_data_iso,
)


# --------------------------------------------------------------------------
# 1. Conversao de data: os tres formatos que convivem no banco
# --------------------------------------------------------------------------
def teste_01_formato_brasileiro_vira_iso():
    assert para_data_iso("31/08/2026") == "2026-08-31"
    assert para_data_iso("01/09/2026") == "2026-09-01"
    assert para_data_iso("14/09/2026") == "2026-09-14"


def teste_02_data_com_hora_perde_a_hora():
    # formato do posicoes.data_atualizacao
    assert para_data_iso("31/08/2026 19:32:14") == "2026-08-31"
    # formato das colunas *_iso
    assert para_data_iso("2026-09-14 17:20:11") == "2026-09-14"


def teste_03_data_ja_em_iso_passa_inteira():
    assert para_data_iso("2026-10-26") == "2026-10-26"


def teste_04_dia_e_mes_na_ordem_brasileira():
    """01/09 e 1 de setembro, nao 9 de janeiro.

    Se a leitura fosse americana, a serie de fundamentos de setembro cairia
    toda em janeiro e o grafico ficaria com um buraco de oito meses.
    """
    assert para_data_iso("01/09/2026") == "2026-09-01"
    assert para_data_iso("09/01/2026") == "2026-01-09"


def teste_05_entrada_ruim_vira_none_e_nao_levanta():
    assert para_data_iso(None) is None
    assert para_data_iso("") is None
    assert para_data_iso("   ") is None
    assert para_data_iso("nan") is None
    assert para_data_iso("None") is None
    assert para_data_iso("32/13/2026") is None
    assert para_data_iso("ontem") is None


def teste_06_ordenacao_iso_corrige_o_bug_01():
    """A razao de tudo isso existir.

    Como texto, '31/08/2026' > '14/09/2026', porque '3' > '1'. Em ISO a ordem
    textual e a ordem cronologica.
    """
    agosto_br, setembro_br = "31/08/2026", "14/09/2026"
    assert agosto_br > setembro_br          # errado, e e assim que o banco ordena

    agosto, setembro = para_data_iso(agosto_br), para_data_iso(setembro_br)
    assert agosto < setembro                # certo


# --------------------------------------------------------------------------
# 2. Fator diario: taxa se compoe, nivel de indice nao tem fator
# --------------------------------------------------------------------------
def teste_07_taxa_diaria_vira_fator():
    assert fator_diario(0.0505, "taxa_diaria") == 1.000505
    assert fator_diario(0.0, "taxa_diaria") == 1.0


def teste_08_nivel_de_indice_nao_tem_fator():
    """IBOV e nivel, nao taxa. Coluna vazia impede a conta errada."""
    assert fator_diario(145000.0, "preco") is None


def teste_09_taxa_ausente_nao_vira_um():
    """Dia sem taxa publicada nao pode virar fator 1,0.

    Fator 1,0 quer dizer "rendeu zero naquele dia", que e uma afirmacao. A
    verdade e que nao se sabe, e isso tem que chegar como vazio no Power BI.
    """
    assert fator_diario(None, "taxa_diaria") is None


def teste_10_produtorio_dos_fatores_bate_com_a_composicao():
    """21 pregoes a 0,0505% ao dia: somar da 1,0605%, compor da 1,0659%."""
    taxas = [0.0505] * 21
    fatores = [fator_diario(t, "taxa_diaria") for t in taxas]

    composto = 1.0
    for fator in fatores:
        composto *= fator
    composto = (composto - 1) * 100
    somado = sum(taxas)

    assert abs(somado - 1.0605) < 0.0001
    assert abs(composto - 1.0659) < 0.0001
    assert composto > somado


# --------------------------------------------------------------------------
# 3. Append do snapshot de score
# --------------------------------------------------------------------------
def _snapshot(data, tickers_e_notas):
    return pd.DataFrame([
        {COLUNA_SNAPSHOT: data, "ticker": ticker, "score_fundamentalista": nota}
        for ticker, nota in tickers_e_notas
    ])


def teste_11_primeiro_snapshot_e_o_arquivo_inteiro():
    novo = _snapshot("2026-10-26", [("PETR4", 70.0)])
    resultado = mesclar_snapshot(None, novo)
    assert len(resultado) == 1

    resultado = mesclar_snapshot(pd.DataFrame(), novo)
    assert len(resultado) == 1


def teste_12_dia_novo_acumula():
    ontem = _snapshot("2026-10-23", [("PETR4", 70.0), ("VALE3", 40.0)])
    hoje = _snapshot("2026-10-26", [("PETR4", 72.0), ("VALE3", 41.0)])

    resultado = mesclar_snapshot(ontem, hoje)
    assert len(resultado) == 4
    assert sorted(resultado[COLUNA_SNAPSHOT].unique()) == ["2026-10-23", "2026-10-26"]


def teste_13_mesmo_dia_substitui_em_vez_de_duplicar():
    """Rodar a exportacao tres vezes na mesma tarde nao pode triplicar o dia."""
    primeira = _snapshot("2026-10-26", [("PETR4", 70.0)])
    segunda = _snapshot("2026-10-26", [("PETR4", 75.0)])

    resultado = mesclar_snapshot(primeira, segunda)
    assert len(resultado) == 1
    assert resultado["score_fundamentalista"].iloc[0] == 75.0


def teste_14_snapshot_vazio_preserva_o_historico():
    """Ranking que falhou nao pode apagar os snapshots ja gravados."""
    historico = _snapshot("2026-10-23", [("PETR4", 70.0)])
    resultado = mesclar_snapshot(historico, pd.DataFrame())
    assert len(resultado) == 1


def teste_15_resultado_sai_ordenado_por_data():
    antigo = _snapshot("2026-10-23", [("VALE3", 40.0)])
    novo = _snapshot("2026-10-26", [("PETR4", 72.0)])

    resultado = mesclar_snapshot(antigo, novo)
    assert list(resultado[COLUNA_SNAPSHOT]) == ["2026-10-23", "2026-10-26"]


# --------------------------------------------------------------------------
# 4. Montagem das tabelas, sobre um banco em memoria
# --------------------------------------------------------------------------
def _banco_sintetico():
    conexao = sqlite3.connect(":memory:")
    conexao.executescript("""
        CREATE TABLE fundamentos (
            ticker TEXT, data TEXT, data_hora_iso TEXT,
            pl REAL, pvp REAL, roe REAL, roa REAL, roic REAL,
            margem_liquida REAL, margem_bruta REAL, margem_ebitda REAL,
            divida_patrimonio REAL, cagr_receita_5a REAL, cagr_lucro_5a REAL
        );
        CREATE TABLE indices (codigo TEXT, data TEXT, valor REAL, tipo TEXT);
        CREATE TABLE transacoes (
            id INTEGER, ticker TEXT, tipo TEXT, quantidade INTEGER,
            preco REAL, data_operacao TEXT, data_operacao_iso TEXT,
            taxas REAL, observacao TEXT
        );
    """)

    # o mesmo ticker em agosto e em setembro: o de setembro e o mais recente
    conexao.executemany(
        "INSERT INTO fundamentos (ticker, data, data_hora_iso, pl, pvp, roe) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("PETR4", "31/08/2026", "2026-08-31 19:00:00", 7.0, 1.1, 25.0),
            ("PETR4", "14/09/2026", "2026-09-14 19:00:00", 8.0, 1.2, 28.26),
            ("VALE3", "14/09/2026", "2026-09-14 19:00:00", 11.0, 1.5, 4.36),
        ],
    )
    conexao.executemany(
        "INSERT INTO indices (codigo, data, valor, tipo) VALUES (?, ?, ?, ?)",
        [
            ("IBOV", "2026-10-23", 145000.0, "preco"),
            ("CDI", "2026-10-23", 0.0505, "taxa_diaria"),
            ("SELIC", "2026-10-23", 0.0505, "taxa_diaria"),
        ],
    )
    conexao.executemany(
        "INSERT INTO transacoes (id, ticker, tipo, quantidade, preco, "
        "data_operacao, data_operacao_iso, taxas) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (1, "PETR4", "compra", 100, 30.0, "31/08/2026", "2026-08-31 19:32:14", 5.0),
            (2, "PETR4", "venda", 50, 35.0, "14/09/2026", "2026-09-14 10:00:00", 4.0),
        ],
    )
    return conexao


def teste_16_fundamento_sai_com_data_iso():
    conexao = _banco_sintetico()
    df = montar_f_fundamento(conexao)
    conexao.close()

    assert set(df["data"]) == {"2026-08-31", "2026-09-14"}


def teste_17_mais_recente_marca_setembro_e_nao_agosto():
    """O caso exato do BUG-01, agora como teste."""
    conexao = _banco_sintetico()
    df = montar_f_fundamento(conexao)
    conexao.close()

    petr = df[df["ticker"] == "PETR4"]
    marcado = petr[petr["mais_recente"]]

    assert len(marcado) == 1
    assert marcado["data"].iloc[0] == "2026-09-14"
    assert marcado["roe"].iloc[0] == 28.26


def teste_18_um_mais_recente_por_ticker():
    conexao = _banco_sintetico()
    df = montar_f_fundamento(conexao)
    conexao.close()

    assert df.groupby("ticker")["mais_recente"].sum().eq(1).all()


def teste_19_indice_recebe_fator_so_nas_taxas():
    conexao = _banco_sintetico()
    df = montar_f_indice(conexao)
    conexao.close()

    por_codigo = df.set_index("codigo")
    assert pd.isna(por_codigo.loc["IBOV", "fator_diario"])
    assert abs(por_codigo.loc["CDI", "fator_diario"] - 1.000505) < 1e-9


def teste_20_transacao_calcula_valores():
    conexao = _banco_sintetico()
    df = montar_f_transacao(conexao)
    conexao.close()

    compra = df[df["tipo"] == "compra"].iloc[0]
    venda = df[df["tipo"] == "venda"].iloc[0]

    assert compra["valor_bruto"] == 3000.0
    assert compra["valor_liquido"] == 3005.0   # taxa encarece a compra
    assert venda["valor_bruto"] == 1750.0
    assert venda["valor_liquido"] == 1746.0    # e diminui o que sobra da venda


def teste_21_taxa_nula_nao_estraga_o_tipo_da_coluna():
    """Coluna de taxas toda NULL tem que sair numerica mesmo assim.

    E o estado real do banco hoje: nenhuma transacao tem taxa preenchida.
    Uma coluna so de NULL volta do SQLite como object, e somar object com
    float propaga object -- o to_csv entao grava o valor_liquido com ponto
    enquanto o resto do arquivo usa virgula, e o Power BI importa essa coluna
    como texto sem reclamar.
    """
    conexao = _banco_sintetico()
    conexao.execute("UPDATE transacoes SET taxas = NULL")
    df = montar_f_transacao(conexao)
    conexao.close()

    assert pd.api.types.is_numeric_dtype(df["valor_liquido"])
    assert pd.api.types.is_numeric_dtype(df["taxas"])
    # sem taxa, liquido e igual ao bruto
    assert (df["valor_liquido"] == df["valor_bruto"]).all()
    # mas a coluna continua ausente: taxa nao registrada nao vira taxa zero
    assert df["taxas"].isna().all()


def teste_22_transacao_sai_em_ordem_cronologica():
    conexao = _banco_sintetico()
    df = montar_f_transacao(conexao)
    conexao.close()

    assert list(df["data"]) == ["2026-08-31", "2026-09-14"]


# --------------------------------------------------------------------------
if __name__ == "__main__":
    testes = [valor for nome, valor in sorted(globals().items())
              if nome.startswith("teste_") and callable(valor)]

    falhas = 0
    for teste in testes:
        try:
            teste()
        except AssertionError as erro:
            falhas += 1
            print(f"FALHOU  {teste.__name__}")
            print(f"        {erro}")
        else:
            print(f"ok      {teste.__name__}")

    print(f"\n{len(testes) - falhas}/{len(testes)} testes passaram")

    print("\nTabela de conferencia 1 -- ordenacao de data como TEXTO:\n")
    datas_br = ["31/08/2026", "01/09/2026", "14/09/2026", "23/10/2026"]
    print(f"{'formato BR':>12s} {'ISO':>12s}")
    for data_br in datas_br:
        print(f"{data_br:>12s} {para_data_iso(data_br):>12s}")

    print(f"\nordem alfabetica do BR : {' < '.join(sorted(datas_br))}")
    print(f"ordem alfabetica do ISO: "
          f"{' < '.join(sorted(para_data_iso(d) for d in datas_br))}")
    print("So a segunda e cronologica. E por isso que a exportacao converte.")

    print("\n\nTabela de conferencia 2 -- CDI somado contra CDI composto:\n")
    print(f"{'pregoes':>8s} {'somado %':>10s} {'composto %':>12s} {'erro p.p.':>10s}")
    for pregoes in (21, 63, 126, 252):
        taxa = 0.0505
        somado = taxa * pregoes
        composto = ((1 + taxa / 100) ** pregoes - 1) * 100
        print(f"{pregoes:8d} {somado:10.4f} {composto:12.4f} {composto - somado:+10.4f}")

    print("\nA coluna fator_diario do f_indice.csv existe para o Power BI usar")
    print("PRODUCTX e cair na terceira coluna, nao SUM e cair na segunda.")

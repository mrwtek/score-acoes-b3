"""Testes do P2-1: timeout, retry, status e a thread que nao morre mais.

    cd src && python test_coletor.py

Nenhuma chamada de rede acontece aqui: `requests.get` e substituido por uma
fila de respostas preparadas, e `time.sleep` por um registrador -- senao o
teste do backoff levaria 6 segundos e o do rate limit, 60.

O QUE ESTE ARQUIVO PROTEGE:

1. QUE A THREAD NAO MORRA. E o bug de 28/10/2026 e o motivo do P2-1 inteiro.
   Um SSLEOFError passageiro derrubou a coleta, e como a thread e daemon e o
   prompt continuava respondendo, o programa ficou parecendo vivo por sete
   semanas sem gravar uma linha.
2. QUE O TOKEN NAO VAZE. A brapi recebe o token na query string, entao ele
   aparece em mensagem de erro de rede e em traceback. Foi assim que o token
   vazou naquele dia.
3. QUE O RETRY NAO SEJA BURRO. 401 e 404 repetidos tres vezes so atrasam o
   ciclo e escondem que o problema e de plano, nao de rede.
"""

import io
import json
from contextlib import redirect_stdout

import requests

import coletor
import main
from coletor import (
    ESPERA_INICIAL_SEGUNDOS,
    ESPERA_RATE_LIMIT_SEGUNDOS,
    TENTATIVAS,
    TIMEOUT_SEGUNDOS,
    buscar_dados_acao,
    buscar_fundamentos,
    buscar_historico,
    coletar_whitelist,
    esconder_tokens,
)

# Token de mentira, com cara de token de verdade. Os testes de vazamento
# trocam o token real por este antes de olhar o que foi impresso.
TOKEN_FALSO = "tok_SEGREDO_abc123"

COTACAO = {"results": [{"symbol": "PETR4", "regularMarketPrice": 53.9}]}
FUNDAMENTO = {"pl": 5.1, "pvp": 1.4, "roe": 28.0}
HISTORICO = {"results": [{"historicalDataPrice": [{"date": 1, "close": 50.0}]}]}


class RespostaFalsa:
    def __init__(self, status=200, corpo=None, texto=None):
        self.status_code = status
        self._corpo = corpo
        if texto is not None:
            self.text = texto
        else:
            self.text = json.dumps(corpo) if corpo is not None else ""

    def json(self):
        if self._corpo is None:
            raise ValueError("resposta nao e JSON")
        return self._corpo


class _api_falsa:
    """Troca requests.get e time.sleep enquanto o bloco roda.

    A ultima resposta da fila se repete: `_api_falsa(erro)` quer dizer "falha
    sempre", sem precisar repetir o item tres vezes.
    """

    def __init__(self, *respostas):
        self.fila = list(respostas)
        self.chamadas = []
        self.esperas = []

    def _get(self, url, params=None, headers=None, timeout=None):
        self.chamadas.append({"url": url, "params": params,
                              "headers": headers, "timeout": timeout})
        item = self.fila.pop(0) if len(self.fila) > 1 else self.fila[0]
        if isinstance(item, Exception):
            raise item
        return item

    def __enter__(self):
        self._get_original = requests.get
        self._sleep_original = coletor.time.sleep
        requests.get = self._get
        coletor.time.sleep = self.esperas.append
        return self

    def __exit__(self, *erro):
        requests.get = self._get_original
        coletor.time.sleep = self._sleep_original

    @property
    def tentativas(self):
        return len(self.chamadas)


def _sem_rede(mensagem="handshake interrompido"):
    """O erro de 28/10: SSLError e subclasse de RequestException."""
    return requests.exceptions.SSLError(mensagem)


# --------------------------------------------------------------------------
# 1. Timeout: a defesa mais importante e a menos visivel
# --------------------------------------------------------------------------
def teste_01_toda_chamada_leva_timeout():
    """Sem timeout, conexao pendurada trava a thread para sempre, sem erro.

    Pior que crash: crash deixa rastro, pendurado nao deixa nada.
    """
    for funcao in (buscar_dados_acao, buscar_historico, buscar_fundamentos):
        with _api_falsa(RespostaFalsa(200, COTACAO if funcao is not buscar_fundamentos
                                      else FUNDAMENTO)) as api:
            funcao("PETR4")
        assert api.chamadas[0]["timeout"] == TIMEOUT_SEGUNDOS, funcao.__name__


# --------------------------------------------------------------------------
# 2. Retry
# --------------------------------------------------------------------------
def teste_02_sucesso_na_primeira_nao_repete():
    with _api_falsa(RespostaFalsa(200, COTACAO)) as api:
        assert buscar_dados_acao("PETR4") == COTACAO["results"][0]
    assert api.tentativas == 1
    assert api.esperas == []


def teste_03_falha_passageira_e_recuperada():
    """O caso exato de 28/10: a rede pisca e volta."""
    with _api_falsa(_sem_rede(), _sem_rede(), RespostaFalsa(200, COTACAO)) as api:
        assert buscar_dados_acao("PETR4") == COTACAO["results"][0]
    assert api.tentativas == 3


def teste_04_desiste_depois_de_n_tentativas():
    with _api_falsa(_sem_rede()) as api:
        assert buscar_dados_acao("PETR4") is None
    assert api.tentativas == TENTATIVAS, (
        f"tentou {api.tentativas} vezes, esperado {TENTATIVAS}"
    )


def teste_05_backoff_dobra():
    with _api_falsa(_sem_rede()) as api:
        buscar_dados_acao("PETR4")
    esperado = [ESPERA_INICIAL_SEGUNDOS * (2 ** i) for i in range(TENTATIVAS - 1)]
    assert api.esperas == esperado, api.esperas


def teste_06_nao_espera_depois_da_ultima_tentativa():
    """Dormir e desistir em seguida e so atraso puro."""
    with _api_falsa(_sem_rede()) as api:
        buscar_dados_acao("PETR4")
    assert len(api.esperas) == TENTATIVAS - 1


# --------------------------------------------------------------------------
# 3. Status: nem todo erro merece retry
# --------------------------------------------------------------------------
def teste_07_erro_de_servidor_repete():
    with _api_falsa(RespostaFalsa(503, texto="indisponivel"),
                    RespostaFalsa(200, COTACAO)) as api:
        assert buscar_dados_acao("PETR4") == COTACAO["results"][0]
    assert api.tentativas == 2


def teste_08_erro_de_cliente_nao_repete():
    """401, 403, 404, 400: a resposta e a mesma na segunda vez.

    Repetir esconde o diagnostico real -- 'token nao fornecido' num ticker
    enquanto outros passam e limite de PLANO, nao falha de rede.
    """
    for status in (400, 401, 403, 404):
        with _api_falsa(RespostaFalsa(status, texto="nope")) as api:
            assert buscar_dados_acao("PETR4") is None
        assert api.tentativas == 1, f"HTTP {status} foi repetido {api.tentativas}x"
        assert api.esperas == []


def teste_09_rate_limit_espera_o_minuto():
    """A janela da brapi e por minuto: tentar em 2s so queima tentativa."""
    with _api_falsa(RespostaFalsa(429, texto="too many"),
                    RespostaFalsa(200, COTACAO)) as api:
        assert buscar_dados_acao("PETR4") == COTACAO["results"][0]
    assert api.esperas == [ESPERA_RATE_LIMIT_SEGUNDOS], api.esperas


def teste_10_corpo_que_nao_e_json_nao_repete():
    """200 com HTML e portal de rede ou pagina de erro. Repetir nao resolve."""
    with _api_falsa(RespostaFalsa(200, None, texto="<html>erro</html>")) as api:
        assert buscar_dados_acao("PETR4") is None
    assert api.tentativas == 1


# --------------------------------------------------------------------------
# 4. O token nao vaza
# --------------------------------------------------------------------------
def teste_11_esconder_tokens_troca_o_segredo():
    original = coletor.BRAPI_TOKEN
    coletor.BRAPI_TOKEN = TOKEN_FALSO
    try:
        texto = f"https://brapi.dev/api/quote/PETR4?token={TOKEN_FALSO}"
        limpo = esconder_tokens(texto)
    finally:
        coletor.BRAPI_TOKEN = original

    assert TOKEN_FALSO not in limpo
    assert "<TOKEN>" in limpo


def teste_12_erro_de_rede_nao_imprime_o_token():
    """Mensagem de excecao do requests costuma trazer a URL inteira.

    Foi exatamente assim que o token vazou no traceback de 28/10/2026.
    """
    original = coletor.BRAPI_TOKEN
    coletor.BRAPI_TOKEN = TOKEN_FALSO
    try:
        erro = _sem_rede(
            f"HTTPSConnectionPool: /api/quote/PETR4?token={TOKEN_FALSO} falhou"
        )
        saida = io.StringIO()
        with _api_falsa(erro), redirect_stdout(saida):
            buscar_dados_acao("PETR4")
    finally:
        coletor.BRAPI_TOKEN = original

    impresso = saida.getvalue()
    assert TOKEN_FALSO not in impresso, "o token foi impresso no log de erro"
    assert "<TOKEN>" in impresso
    assert "cotacao de PETR4" in impresso, "o log nao diz o que falhou"


def teste_13_a_url_nao_entra_no_log():
    """O log identifica a chamada pela descricao, nunca pela URL com token."""
    saida = io.StringIO()
    with _api_falsa(RespostaFalsa(500, texto="boom")), redirect_stdout(saida):
        buscar_dados_acao("PETR4")
    assert "brapi.dev" not in saida.getvalue()


# --------------------------------------------------------------------------
# 5. As tres funcoes continuam validando o corpo
# --------------------------------------------------------------------------
def teste_14_results_vazio_vira_none():
    with _api_falsa(RespostaFalsa(200, {"results": []})):
        assert buscar_dados_acao("PETR4") is None
    with _api_falsa(RespostaFalsa(200, {"erro": "x"})):
        assert buscar_historico("PETR4") is None


def teste_15_fundamento_sem_pl_vira_none():
    with _api_falsa(RespostaFalsa(200, {"erro": "cota diaria esgotada"})):
        assert buscar_fundamentos("PETR4") is None


def teste_16_historico_sem_pontos_vira_lista_vazia():
    """Lista vazia e None nao sao a mesma coisa: uma e 'nao tem pregao no
    periodo', a outra e 'a chamada falhou'. O backfill trata diferente."""
    with _api_falsa(RespostaFalsa(200, {"results": [{}]})):
        assert buscar_historico("PETR4") == []
    with _api_falsa(RespostaFalsa(200, HISTORICO)):
        assert len(buscar_historico("PETR4")) == 1


def teste_17_um_ticker_que_falha_nao_derruba_os_outros():
    whitelist_original = coletor.get_whitelist
    coletor.get_whitelist = lambda: ["PETR4", "QUEBRA3", "VALE3"]
    try:
        respostas = [RespostaFalsa(200, COTACAO),
                     RespostaFalsa(404, texto="nao existe"),
                     RespostaFalsa(200, COTACAO),
                     RespostaFalsa(200, COTACAO)]
        saida = io.StringIO()
        with _api_falsa(*respostas), redirect_stdout(saida):
            coletados = coletar_whitelist()
    finally:
        coletor.get_whitelist = whitelist_original

    assert len(coletados) == 2
    assert "2 de 3" in saida.getvalue(), "o placar da coleta parcial sumiu"
    assert "QUEBRA3" in saida.getvalue(), "nao disse qual ticker falhou"


# --------------------------------------------------------------------------
# 6. A thread nao morre -- o bug que originou o P2-1
# --------------------------------------------------------------------------
def teste_18_ciclo_protegido_sobrevive_a_excecao():
    original = main.ciclo_de_coleta

    def explode():
        raise RuntimeError("qualquer coisa inesperada")

    main.ciclo_de_coleta = explode
    try:
        saida = io.StringIO()
        with redirect_stdout(saida):
            resultado = main.rodar_ciclo_protegido()
    finally:
        main.ciclo_de_coleta = original

    assert resultado is False
    assert "RuntimeError" in saida.getvalue(), "o erro foi engolido em silencio"
    assert "CONTINUA viva" in saida.getvalue()


def teste_19_ciclo_protegido_devolve_true_quando_passa():
    original = main.ciclo_de_coleta
    main.ciclo_de_coleta = lambda: None
    try:
        assert main.rodar_ciclo_protegido() is True
    finally:
        main.ciclo_de_coleta = original


def teste_20_traceback_do_ciclo_nao_vaza_token():
    """O traceback e o caminho mais provavel de vazamento: ele imprime o
    repr dos argumentos que passaram pela pilha, URL com token inclusive."""
    original_ciclo = main.ciclo_de_coleta
    original_token = coletor.BRAPI_TOKEN
    coletor.BRAPI_TOKEN = TOKEN_FALSO

    def explode():
        raise RuntimeError(f"falhou em /quote/PETR4?token={TOKEN_FALSO}")

    main.ciclo_de_coleta = explode
    try:
        saida = io.StringIO()
        with redirect_stdout(saida):
            main.rodar_ciclo_protegido()
    finally:
        main.ciclo_de_coleta = original_ciclo
        coletor.BRAPI_TOKEN = original_token

    assert TOKEN_FALSO not in saida.getvalue(), "o traceback vazou o token"


def teste_21_ctrl_c_ainda_encerra():
    """`except Exception` nao pega KeyboardInterrupt, que herda de
    BaseException. Se um dia virar `except:` pelado, este teste quebra."""
    original = main.ciclo_de_coleta

    def interrompe():
        raise KeyboardInterrupt()

    main.ciclo_de_coleta = interrompe
    try:
        main.rodar_ciclo_protegido()
    except KeyboardInterrupt:
        passou = True
    else:
        passou = False
    finally:
        main.ciclo_de_coleta = original

    assert passou, "Ctrl-C foi engolido pela guarda -- nao da mais para sair"


if __name__ == "__main__":
    testes = [valor for nome, valor in sorted(globals().items())
              if nome.startswith("teste_")]

    falhas = 0
    for teste in testes:
        # o coletor imprime bastante quando repete chamada, e aqui isso seria
        # so ruido entre os 'ok'. Os testes que CONFEREM o que foi impresso
        # capturam a propria saida por dentro, entao nao dependem disto.
        engolido = io.StringIO()
        try:
            with redirect_stdout(engolido):
                teste()
        except AssertionError as erro:
            falhas += 1
            print(f"FALHOU  {teste.__name__}")
            print(f"        {erro}")
        else:
            print(f"ok      {teste.__name__}")

    print()
    print(f"{len(testes) - falhas}/{len(testes)} testes passaram")

    print()
    print("Tabela de conferencia manual -- o que cada resposta provoca:")
    print()
    print(f"{'resposta':>22s} {'tentativas':>11s} {'esperou (s)':>12s} "
          f"{'resultado':>10s}  por que")

    casos = [
        (RespostaFalsa(200, COTACAO), "200 ok", "passa de primeira"),
        (_sem_rede(), "erro de rede", "o caso de 28/10: tenta de novo e desiste"),
        (RespostaFalsa(500, texto="x"), "500", "problema do outro lado, pode passar"),
        (RespostaFalsa(503, texto="x"), "503", "idem"),
        (RespostaFalsa(429, texto="x"), "429", "janela por minuto, espera o minuto"),
        (RespostaFalsa(401, texto="x"), "401", "token ruim nao melhora repetindo"),
        (RespostaFalsa(404, texto="x"), "404", "ticker inexistente idem"),
        (RespostaFalsa(400, texto="x"), "400", "range fora do plano idem"),
        (RespostaFalsa(200, None, texto="<html>"), "200 sem JSON",
         "pagina de erro ou portal de rede"),
    ]
    for resposta, rotulo, comentario in casos:
        saida = io.StringIO()
        with _api_falsa(resposta) as api, redirect_stdout(saida):
            devolvido = buscar_dados_acao("PETR4")
        total = sum(api.esperas)
        print(f"{rotulo:>22s} {api.tentativas:>11d} {total:>12.0f} "
              f"{('dados' if devolvido else 'None'):>10s}  {comentario}")

    print()
    print("Em NENHUMA linha acima a excecao escapa: a thread de coleta segue viva")
    print("e o proximo ciclo tenta de novo. Era so isso que faltava em 28/10.")

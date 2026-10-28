"""
Chamadas as duas APIs: brapi (cotacoes e historico) e BolsAI (fundamentos).

P2-1, 28/10/2026. Antes desta mudanca as chamadas nao tinham timeout, retry
nem checagem de status, e a excecao subia sem ninguem capturar. Em 28/10 um
SSLEOFError -- handshake TLS interrompido, falha passageira, a brapi
respondeu normal minutos depois -- derrubou a thread de coleta inteira. Como
a thread e daemon e o prompt do main.py continua respondendo, o programa
ficou PARECENDO vivo por sete semanas sem gravar uma linha.

Tres defesas, nesta ordem de importancia:

1. TIMEOUT em toda chamada. E a mais importante e a menos visivel: sem ele,
   uma conexao pendurada trava a thread para sempre, sem erro nenhum e sem
   crash para investigar depois. Crash pelo menos deixa rastro.
2. RETRY com backoff, para falha passageira nao custar o ciclo.
3. STATUS conferido antes de ler o corpo, para 401 e 429 aparecerem como o
   que sao, em vez de virarem KeyError la na frente.

E um cuidado que nao e sobre rede: o token da brapi vai na QUERY STRING, e
mensagem de erro de rede costuma incluir a URL inteira. Foi assim que o
traceback de 28/10 expos o token. Nada sai daqui sem passar por
esconder_tokens().
"""
import time

import requests

from config import BRAPI_TOKEN, BOLSAI_TOKEN
from whitelist import get_whitelist

# A brapi no plano free so aceita os ranges 1d, 5d, 1mo e 3mo - 6mo para cima
# exige o plano Pro. 3mo rende 63 pregoes por ticker. Como a janela desliza, o
# backfill rodado periodicamente vai estendendo a serie no banco; e por isso que
# ele nao e script de uso unico.
INTERVALO_HISTORICO_PADRAO = "3mo"

# Teto de espera por resposta. Vale para conexao e leitura (requests aplica aos
# dois quando recebe um numero so). 30s e folgado para as duas APIs, que
# respondem em menos de 1s quando estao bem -- o numero nao esta calibrado para
# performance, esta para garantir que a thread SEMPRE volta.
TIMEOUT_SEGUNDOS = 30

# Tentativas por chamada, contando a primeira. Tres cobre o caso que motivou o
# P2-1 (uma piscada de rede) sem transformar instabilidade longa em travamento:
# com 13 tickers e duas APIs, o pior caso e ~2,5 min de ciclo, e o ciclo roda
# de hora em hora.
TENTATIVAS = 3

# Backoff: 2s antes da segunda tentativa, 4s antes da terceira. Dobrar e o
# padrao porque espalha as tentativas em vez de concentra-las no instante em
# que o servico ainda esta caindo.
ESPERA_INICIAL_SEGUNDOS = 2

# 429 e caso a parte. A brapi limita 20 requisicoes POR MINUTO, entao tentar de
# novo em 2s so queima tentativa -- a janela ainda nao virou. Esperar o minuto
# inteiro e o unico retry que pode dar certo.
ESPERA_RATE_LIMIT_SEGUNDOS = 60
HTTP_RATE_LIMIT = 429

# Status que NAO adianta repetir: a resposta nao vai mudar na segunda vez.
# 400 range fora do plano, 401 token invalido, 403 sem permissao, 404 ticker
# inexistente. Repetir aqui so atrasa o ciclo e esconde o problema real --
# "token nao fornecido" num ticker enquanto outros funcionam e limite de
# plano, nao falha de rede (ver as Restricoes no ESTADO.md).
STATUS_SEM_RETRY = (400, 401, 403, 404)


def esconder_tokens(texto):
    """Troca qualquer token por <TOKEN> no texto. Use em TUDO que for impresso.

    A brapi recebe o token na query string, entao ele aparece inteiro em
    mensagem de excecao do requests, que costuma trazer a URL completa. O
    traceback de 28/10/2026 vazou o token exatamente assim, e o token teve de
    ser rotacionado.

    Nao e paranoia de log bonito: o terminal vira print de tela, o print vira
    anexo, e o anexo vira token publico.
    """
    texto = str(texto)
    for token in (BRAPI_TOKEN, BOLSAI_TOKEN):
        if token:
            texto = texto.replace(token, "<TOKEN>")
    return texto


def _buscar(url, descricao, params=None, headers=None, tentativas=TENTATIVAS):
    """GET com timeout, retry e checagem de status. Devolve o JSON, ou None.

    `descricao` e o que aparece no log ("cotacao de PETR4"). A URL NAO entra
    no log, de proposito -- e ela que carrega o token da brapi.

    Devolver None em vez de levantar e deliberado, e segue o que as funcoes
    deste modulo ja faziam: quem chama trata ticker ausente pulando o ticker,
    e um papel que falhou nao pode derrubar a coleta dos outros doze.
    """
    espera = ESPERA_INICIAL_SEGUNDOS

    for tentativa in range(1, tentativas + 1):
        ultima = tentativa == tentativas

        try:
            resposta = requests.get(url, params=params, headers=headers,
                                    timeout=TIMEOUT_SEGUNDOS)
        except requests.RequestException as erro:
            # Timeout, ConnectionError, SSLError (o caso de 28/10) -- todos
            # passageiros em principio, todos valem retry.
            motivo = f"{erro.__class__.__name__}: {esconder_tokens(erro)}"
            if ultima:
                print(f"ERRO de rede em {descricao}, desisti apos {tentativas} "
                      f"tentativas. {motivo}")
                return None
            print(f"AVISO: falha de rede em {descricao} "
                  f"(tentativa {tentativa}/{tentativas}). {motivo}")
            time.sleep(espera)
            espera *= 2
            continue

        if resposta.status_code == HTTP_RATE_LIMIT:
            if ultima:
                print(f"ERRO: limite de requisicoes da API em {descricao}, "
                      f"desisti apos {tentativas} tentativas.")
                return None
            print(f"AVISO: limite de requisicoes em {descricao}. Esperando "
                  f"{ESPERA_RATE_LIMIT_SEGUNDOS}s (a janela da brapi e por minuto).")
            time.sleep(ESPERA_RATE_LIMIT_SEGUNDOS)
            continue

        if resposta.status_code in STATUS_SEM_RETRY:
            # Nao repete: a resposta e a mesma na proxima vez. O corpo entra no
            # log porque e onde a API diz o que faltou -- o 400 de range fora
            # do plano, por exemplo, nomeia o plano necessario.
            print(f"ERRO HTTP {resposta.status_code} em {descricao}: "
                  f"{esconder_tokens(resposta.text[:200])}")
            return None

        if resposta.status_code != 200:
            # sobra 5xx e companhia: problema do lado de la, pode passar
            if ultima:
                print(f"ERRO HTTP {resposta.status_code} em {descricao}, "
                      f"desisti apos {tentativas} tentativas: "
                      f"{esconder_tokens(resposta.text[:200])}")
                return None
            print(f"AVISO: HTTP {resposta.status_code} em {descricao} "
                  f"(tentativa {tentativa}/{tentativas}).")
            time.sleep(espera)
            espera *= 2
            continue

        try:
            return resposta.json()
        except ValueError:
            # 200 que nao e JSON e quase sempre pagina de erro ou portal de
            # rede capturado. Repetir nao resolve nenhum dos dois.
            print(f"ERRO em {descricao}: resposta 200 que nao e JSON. "
                  f"{esconder_tokens(resposta.text[:200])}")
            return None

    return None


def buscar_dados_acao(ticker):
    """Cotacao do momento na brapi, ou None.

    Devolve `results[0]`: regularMarketPrice, regularMarketVolume, marketCap,
    priceEarnings, earningsPerShare.
    """
    dados = _buscar(
        f"https://brapi.dev/api/quote/{ticker}",
        descricao=f"cotacao de {ticker}",
        params={"token": BRAPI_TOKEN},
    )
    if dados is None:
        return None

    if "results" not in dados or not dados["results"]:
        print(f"ERRO ao buscar {ticker}: {esconder_tokens(dados)}")
        return None

    return dados["results"][0]


def coletar_whitelist():
    """Cotacao de todos os tickers da whitelist. Ticker que falha e pulado.

    Imprime o placar no fim. Antes do P2-1 uma coleta parcial passava
    despercebida -- e uma coleta ZERADA tambem, porque a lista vazia nao
    reclamava de nada.
    """
    tickers = get_whitelist()
    dados_coletados = []
    falharam = []

    for ticker in tickers:
        dados = buscar_dados_acao(ticker)
        if dados is None:
            falharam.append(ticker)
            continue
        dados_coletados.append(dados)
        print(f"Coletado: {ticker}")

    print(f"Cotacoes: {len(dados_coletados)} de {len(tickers)}.")
    if falharam:
        print(f"Falharam: {', '.join(falharam)}. Se o mesmo ticker falha sempre "
              f"enquanto os outros passam, suspeite do plano da API antes do codigo.")

    return dados_coletados


def buscar_historico(ticker, intervalo=INTERVALO_HISTORICO_PADRAO):
    """Devolve a lista de pregoes diarios da brapi, ou None se a chamada falhar.

    Cada item vem no formato {date, open, high, low, close, volume,
    adjustedClose}, com `date` em epoch de segundos.
    """
    dados = _buscar(
        f"https://brapi.dev/api/quote/{ticker}",
        descricao=f"historico de {ticker}",
        params={"token": BRAPI_TOKEN, "range": intervalo, "interval": "1d"},
    )
    if dados is None:
        return None

    if "results" not in dados or not dados["results"]:
        print(f"ERRO ao buscar historico de {ticker}: {esconder_tokens(dados)}")
        return None

    return dados["results"][0].get("historicalDataPrice") or []


def buscar_fundamentos(ticker):
    """Fundamentos da BolsAI, ou None. O token vai no header, nao na URL."""
    dados = _buscar(
        f"https://api.usebolsai.com/api/v1/fundamentals/{ticker}",
        descricao=f"fundamentos de {ticker}",
        headers={"X-API-Key": BOLSAI_TOKEN},
    )
    if dados is None:
        return None

    if "pl" not in dados:
        print(f"ERRO ao buscar fundamentos de {ticker}: {esconder_tokens(dados)}")
        return None

    return dados


if __name__ == "__main__":
    resultado = coletar_whitelist()
    print(f"\nTotal de ações coletadas: {len(resultado)}")

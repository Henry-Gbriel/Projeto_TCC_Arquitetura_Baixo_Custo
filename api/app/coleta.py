"""Descoberta e coleta dos arquivos anuais de ITBI-SP (adaptado de SearchDataSetSP.py).

- O ano vem do rótulo do parágrafo na página ("2026 ( Excel/xlsx ) ( ODS )"), não da URL.
- Seleciona o link cujo texto é Excel/xlsx; o ODS é ignorado. Links de 2019-2021 terminam
  em .xls, por isso o filtro por extensão do código original não serve.
- Redirecionamentos são seguidos manualmente e registrados no catálogo.
- Coletar não inicia processamento.
"""
import re
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from . import bronze, config, db

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) TCC-ITBI-coletor/1.0"
MAX_REDIRECIONAMENTOS = 5
_RE_ANO = re.compile(r"^\s*((?:19|20)\d{2})\b")
_cache: dict = {"quando": 0.0, "anos": None}
CACHE_S = 600


def _get(url: str, **kw) -> tuple[requests.Response, str, list[dict]]:
    """GET com redirecionamentos explícitos. Retorna (resposta final, url final, cadeia)."""
    cadeia = []
    atual = url
    for _ in range(MAX_REDIRECIONAMENTOS + 1):
        r = requests.get(atual, headers={"User-Agent": USER_AGENT}, timeout=config.HTTP_TIMEOUT_S,
                         allow_redirects=False, **kw)
        if r.is_redirect or r.status_code in (301, 302, 303, 307, 308):
            destino = urljoin(atual, r.headers.get("Location", ""))
            cadeia.append({"de": atual, "para": destino, "status": r.status_code,
                           "troca_dominio": urlparse(atual).netloc != urlparse(destino).netloc})
            r.close()
            atual = destino
            continue
        return r, atual, cadeia
    raise RuntimeError(f"Mais de {MAX_REDIRECIONAMENTOS} redirecionamentos a partir de {url}")


def extrair_links_anuais(html: str, base: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    encontrados: dict[int, dict] = {}
    for a in soup.find_all("a"):
        href = a.get("href")
        rotulo = a.get_text(" ", strip=True).lower()
        if not href or ("excel" not in rotulo and "xlsx" not in rotulo):
            continue
        pai = a.find_parent(["p", "li", "td", "div"])
        texto_pai = pai.get_text(" ", strip=True) if pai else ""
        m = _RE_ANO.match(texto_pai)
        if not m:
            continue
        ano = int(m.group(1))
        encontrados.setdefault(ano, {"ano": ano, "url": urljoin(base, href.strip()),
                                     "rotulo": texto_pai[:80]})
    return sorted(encontrados.values(), key=lambda x: x["ano"], reverse=True)


def descobrir_anos(forcar: bool = False) -> list[dict]:
    if not forcar and _cache["anos"] is not None and time.time() - _cache["quando"] < CACHE_S:
        return _cache["anos"]
    r, url_final, _ = _get(config.FONTE_ITBI_SP_URL)
    r.raise_for_status()
    anos = extrair_links_anuais(r.text, url_final)
    _cache.update(quando=time.time(), anos=anos)
    return anos


def coletar_ano(item: dict) -> dict:
    """Baixa o Excel de um ano e registra em Bronze. Pula se o servidor indica o mesmo conteúdo."""
    with db.conexao() as conn:
        anterior = conn.execute(
            "SELECT * FROM arquivos_bronze WHERE url_origem = %s ORDER BY coletado_em DESC LIMIT 1",
            (item["url"],)).fetchone()

    r, url_final, cadeia = _get(item["url"], stream=True)
    try:
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code} ao baixar {url_final}")
        etag, last_mod = r.headers.get("ETag"), r.headers.get("Last-Modified")
        if anterior and (etag or last_mod) and anterior["etag"] == etag and anterior["last_modified"] == last_mod:
            return {"status": "inalterado", "arquivo_id": anterior["id"], "criterio": "etag/last-modified"}
        destino, temp = bronze.arquivo_temporario()
        with destino:
            for bloco in r.iter_content(bronze.BLOCO):
                destino.write(bloco)
    finally:
        r.close()

    nome = urlparse(url_final).path.rsplit("/", 1)[-1] or f"itbi_{item['ano']}"
    nome = requests.utils.unquote(nome)
    linha, novo = bronze.registrar(temp, nome, ano_fonte=item["ano"], url_origem=item["url"],
                                   url_final=url_final, redirecionamentos=cadeia, etag=etag,
                                   last_modified=last_mod)
    return {"status": "novo" if novo else "inalterado", "arquivo_id": linha["id"],
            "criterio": "sha256", "formato": linha["formato"], "redirecionamentos": len(cadeia)}


def iniciar_coleta(anos: list[int] | None) -> int:
    """Cria a coleta e processa em thread. anos=None significa todos os anos da página."""
    disponiveis = descobrir_anos(forcar=True)
    por_ano = {d["ano"]: d for d in disponiveis}
    alvo = sorted(por_ano) if anos is None else anos
    faltando = [a for a in alvo if a not in por_ano]
    if faltando:
        raise ValueError(f"Ano(s) não encontrados na página oficial: {faltando}")
    progresso = {str(a): {"status": "pendente"} for a in alvo}
    with db.conexao() as conn:
        coleta_id = conn.execute(
            "INSERT INTO coletas (parametros, status, progresso) VALUES (%s, 'em_andamento', %s) RETURNING id",
            (db.Jsonb({"anos": alvo, "todos": anos is None}), db.Jsonb(progresso))).fetchone()["id"]
    threading.Thread(target=_executar_coleta, args=(coleta_id, [por_ano[a] for a in alvo]),
                     daemon=True, name=f"coleta-{coleta_id}").start()
    return coleta_id


def _executar_coleta(coleta_id: int, itens: list[dict]) -> None:
    falhas = 0
    for item in itens:
        _atualizar(coleta_id, item["ano"], {"status": "baixando", "url": item["url"]})
        try:
            resultado = coletar_ano(item)
        except Exception as e:
            falhas += 1
            resultado = {"status": "falhou", "mensagem": str(e)}
        resultado["finalizado_em"] = datetime.now(timezone.utc).isoformat()
        _atualizar(coleta_id, item["ano"], resultado)
    with db.conexao() as conn:
        conn.execute("UPDATE coletas SET status = %s, concluido_em = now() WHERE id = %s",
                     ("concluida" if falhas == 0 else "concluida_com_falhas", coleta_id))


def _atualizar(coleta_id: int, ano: int, estado: dict) -> None:
    with db.conexao() as conn:
        conn.execute("UPDATE coletas SET progresso = jsonb_set(progresso, %s, %s) WHERE id = %s",
                     ([str(ano)], db.Jsonb(estado), coleta_id))

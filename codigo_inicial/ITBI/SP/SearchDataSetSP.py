import requests
from bs4 import BeautifulSoup
import os
import random
from pyspark.sql import SparkSession

# faz a busca no site da prefeitura
URL = "https://prefeitura.sp.gov.br/web/fazenda/w/acesso_a_informacao/31501"
CATALOG = "cdp_dev"
SCHEMA = "itbi"
VOLUME = "volume_itbi_sp"
PATH = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}"

request_delay = 10

# Mascara para não levarmos bloqueio
AGENTS_MASCARA = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0)",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
    "Mozilla/5.0 (Linux; Android 13; SM-G991B)"
]


def get_spark():
    return SparkSession.builder.appName("ITBI São Paulo").enableHiveSupport().getOrCreate()


def _headers():
    return {
        "User-Agent": random.choice(AGENTS_MASCARA)
    }  # Utilizar a mascara aleatoria


def _e_link_xlsx(href: str) -> bool:
    """
    Identifica links de planilha ITBI cobrindo os dois padrões observados no site:

    - Padrão antigo (2006-2025): termina literalmente em '.xlsx'
      Ex.: .../GUIAS-DE-ITBI-PAGAS-2024.xlsx

    - Padrão novo (a partir de 2026): link do repositório de documentos
      (Liferay), sem o ponto antes de 'xlsx'
      Ex.: .../documents/d/fazenda/guias-de-itbi-pagas-4-xlsx
    """
    href_lower = href.lower()

    if href_lower.endswith(".xlsx"):
        return True

    if href_lower.endswith("-xlsx") and "itbi" in href_lower:
        return True

    return False


# Buscamos todas informações de link
def buscar_links():

    response = requests.get(URL, headers=_headers(), timeout=request_delay)

    if response.status_code != 200:
        raise Exception(f"Erro ao buscar dados: {response.status_code}")

    soup = BeautifulSoup(response.text, "html.parser")  # Fazendo requisição para as tags do site

    # Ao percorrer todos os links, filtramos somente os que apontam para planilhas ITBI
    links = []

    for a in soup.find_all("a"):
        href = a.get("href")

        if not href:
            continue

        if _e_link_xlsx(href):
            # garantir link completo ---- Links relativos ficam completos
            if href.startswith("/"):
                href = "https://prefeitura.sp.gov.br" + href

            links.append(href)

    print(f"Total de arquivos encontrados: {len(links)}")
    return links


def _nome_arquivo(link: str) -> str:
    """
    Extrai o nome do arquivo a partir do link e garante extensão .xlsx.

    Necessário porque o link do padrão novo (2026) não termina com
    extensão de arquivo (ex.: 'guias-de-itbi-pagas-4-xlsx'), e o
    pipeline de extração depende de glob.glob('*.xlsx') para localizar
    os arquivos no Volume.
    """
    filename = link.split("/")[-1]

    if not filename.lower().endswith(".xlsx"):
        filename = filename.rstrip("-") + ".xlsx"

    return filename


def download(links):

    os.makedirs(PATH, exist_ok=True)

    for link in links:
        filename = _nome_arquivo(link)
        path = os.path.join(PATH, filename)

        print(f"Baixando: {filename}")

        response = requests.get(link, headers=_headers(), timeout=request_delay)

        if response.status_code == 200:
            with open(path, "wb") as f:
                f.write(response.content)
        else:
            print(f"Erro ao baixar {filename}: {response.status_code}")

    print("Download concluído")


if __name__ == "__main__":
    links = buscar_links()
    download(links)
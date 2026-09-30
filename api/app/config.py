"""Configuração lida de variáveis de ambiente (e do arquivo .env na raiz, se existir)."""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def _carregar_env(caminho: Path) -> None:
    """Parser mínimo de .env: não sobrescreve variáveis já definidas no ambiente."""
    if not caminho.is_file():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


_carregar_env(RAIZ / ".env")


def _lista(nome: str, padrao: str) -> list[str]:
    return [x.strip() for x in os.environ.get(nome, padrao).split(",") if x.strip()]


PG_DSN = os.environ.get("PG_DSN") or (
    f"host={os.environ.get('PG_HOST', 'localhost')} "
    f"port={os.environ.get('PG_PORTA', '5434')} "
    f"dbname={os.environ.get('PG_DB', 'tcc_itbi')} "
    f"user={os.environ.get('PG_USER', 'tcc')} "
    f"password={os.environ.get('PG_PASSWORD', '')}"
)

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORTA = int(os.environ.get("MQTT_PORTA", "1884"))
MQTT_USUARIO = os.environ.get("MQTT_USUARIO") or None
MQTT_SENHA = os.environ.get("MQTT_SENHA") or None
# Prefixo dos tópicos (tcc/nos/{no_id}/tarefa, tcc/resultados...). Testes usam outro prefixo.
MQTT_PREFIXO = os.environ.get("MQTT_PREFIXO", "tcc")
MQTT_CLIENT_ID = os.environ.get("MQTT_CLIENT_ID", "tcc-orquestrador")

BRONZE_DIR = Path(os.environ.get("BRONZE_DIR", str(RAIZ / "data" / "bronze")))

# Nós físicos padrão; uma execução pode escolher um subconjunto (experimentos 1, 2 e 3 nós).
NOS_PADRAO = _lista("NOS_PADRAO", "esp32-01,esp32-02,esp32-03")
TAMANHO_LOTE = int(os.environ.get("TAMANHO_LOTE", "10"))
# Segundos sem resposta para um registro enviado antes de reenviar.
TIMEOUT_REGISTRO_S = float(os.environ.get("TIMEOUT_REGISTRO_S", "15"))
# Reenvios do mesmo registro ao mesmo nó antes de expirar a tentativa do lote.
MAX_REENVIOS = int(os.environ.get("MAX_REENVIOS", "2"))
# Tentativas de lote (atribuições) antes de marcá-lo como falhou.
MAX_TENTATIVAS_LOTE = int(os.environ.get("MAX_TENTATIVAS_LOTE", "3"))
# Nó sem mensagem de estado por esse tempo é considerado offline.
NO_OFFLINE_S = float(os.environ.get("NO_OFFLINE_S", "45"))

FONTE_ITBI_SP_URL = os.environ.get(
    "FONTE_ITBI_SP_URL",
    "https://prefeitura.sp.gov.br/web/fazenda/w/acesso_a_informacao/31501",
)
HTTP_TIMEOUT_S = float(os.environ.get("HTTP_TIMEOUT_S", "60"))

# Desliga o orquestrador MQTT (útil em testes que só usam leitura/API).
ORQUESTRADOR_ATIVO = os.environ.get("ORQUESTRADOR_ATIVO", "1") == "1"

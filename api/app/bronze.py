"""Camada Bronze: preserva o arquivo original sem alteração e o cataloga no PostgreSQL."""
import hashlib
import os
import re
import shutil
import tempfile
from collections import Counter
from pathlib import Path
from typing import BinaryIO

from . import config, db
from .leitor import listar_abas

BLOCO = 1024 * 1024


def detectar_formato(caminho: Path) -> str:
    with open(caminho, "rb") as f:
        cabeca = f.read(8)
    if cabeca.startswith(b"PK\x03\x04"):
        return "xlsx"
    if cabeca.startswith(b"\xd0\xcf\x11\xe0"):
        return "xls"
    return "desconhecido"


def _nome_seguro(nome: str) -> str:
    nome = os.path.basename(nome) or "arquivo"
    return re.sub(r"[^\w.\-() ]+", "_", nome).strip() or "arquivo"


def arquivo_temporario() -> tuple[BinaryIO, Path]:
    tmp_dir = config.BRONZE_DIR / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fd, nome = tempfile.mkstemp(dir=tmp_dir, suffix=".part")
    return os.fdopen(fd, "wb"), Path(nome)


def salvar_stream(origem: BinaryIO) -> Path:
    destino, caminho = arquivo_temporario()
    with destino:
        shutil.copyfileobj(origem, destino, BLOCO)
    return caminho


def sha256_arquivo(caminho: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    tamanho = 0
    with open(caminho, "rb") as f:
        while bloco := f.read(BLOCO):
            h.update(bloco)
            tamanho += len(bloco)
    return h.hexdigest(), tamanho


def registrar(temp: Path, nome_original: str, ano_fonte: int | None = None, url_origem=None,
              url_final=None, redirecionamentos=None, etag=None, last_modified=None) -> tuple[dict, bool]:
    """Move o arquivo temporário para Bronze e cataloga. Retorna (registro, novo).

    Se o mesmo conteúdo (SHA-256) já existe, o temporário é descartado e o registro
    existente é devolvido: não há importação duplicada. Conteúdo diferente do mesmo ano
    gera uma nova versão; versões anteriores nunca são sobrescritas nem apagadas.
    """
    sha, tamanho = sha256_arquivo(temp)
    with db.conexao() as conn:
        existente = conn.execute("SELECT * FROM arquivos_bronze WHERE sha256 = %s", (sha,)).fetchone()
        if existente:
            temp.unlink(missing_ok=True)
            return existente, False

    formato = detectar_formato(temp)
    abas, erro_abas = [], None
    if formato == "xlsx":
        try:
            abas = listar_abas(temp)
        except Exception as e:  # arquivo corrompido continua preservado
            erro_abas = str(e)
    if ano_fonte is None and abas:
        ano_fonte = Counter(a["ano"] for a in abas).most_common(1)[0][0]

    pasta = config.BRONZE_DIR / "itbi_sp" / (str(ano_fonte) if ano_fonte else "sem_ano")
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{sha[:12]}_{_nome_seguro(nome_original)}"
    shutil.move(str(temp), destino)
    os.chmod(destino, 0o444)  # preservação: somente leitura

    with db.conexao() as conn:
        linha = conn.execute(
            """INSERT INTO arquivos_bronze (nome_original, caminho, sha256, tamanho, formato, ano_fonte,
                   url_origem, url_final, redirecionamentos, etag, last_modified, abas)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (sha256) DO NOTHING RETURNING *""",
            (nome_original, str(destino), sha, tamanho, formato, ano_fonte, url_origem, url_final,
             db.Jsonb(redirecionamentos or []), etag, last_modified, db.Jsonb(abas)),
        ).fetchone()
        if linha is None:  # corrida com outra importação do mesmo conteúdo
            linha = conn.execute("SELECT * FROM arquivos_bronze WHERE sha256 = %s", (sha,)).fetchone()
            return linha, False
        if erro_abas or formato != "xlsx":
            db.evento(conn, "erro_leitura_arquivo", arquivo_id=linha["id"], formato=formato,
                      mensagem=erro_abas or "formato não suportado pelo leitor XLSX")
    return linha, True


def reanalisar_abas_pendentes() -> int:
    """Relê a lista de abas de arquivos XLSX catalogados sem abas (ex.: falha anterior)."""
    with db.conexao() as conn:
        linhas = conn.execute("SELECT id, caminho FROM arquivos_bronze "
                              "WHERE formato='xlsx' AND abas = '[]'::jsonb").fetchall()
        for l in linhas:
            try:
                abas = listar_abas(l["caminho"])
            except Exception as e:
                db.evento(conn, "erro_leitura_arquivo", arquivo_id=l["id"], mensagem=str(e))
                continue
            conn.execute("UPDATE arquivos_bronze SET abas=%s WHERE id=%s", (db.Jsonb(abas), l["id"]))
    return len(linhas)


def resumo(linha: dict) -> dict:
    return {
        "id": linha["id"], "nome_original": linha["nome_original"], "ano_fonte": linha["ano_fonte"],
        "sha256": linha["sha256"], "tamanho": linha["tamanho"], "formato": linha["formato"],
        "url_origem": linha["url_origem"], "url_final": linha["url_final"],
        "coletado_em": linha["coletado_em"],
        "meses_disponiveis": [a["aba"] for a in linha["abas"]],
    }

"""Acesso ao PostgreSQL (psycopg 3 + pool)."""
from contextlib import contextmanager
from pathlib import Path

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from . import config

MIGRACOES = Path(__file__).parent / "migrations"
_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(config.PG_DSN, min_size=1, max_size=10,
                               kwargs={"row_factory": dict_row}, open=True)
    return _pool


def fechar() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def conexao():
    """Conexão transacional: commit ao sair sem erro, rollback em exceção."""
    with pool().connection() as conn:
        yield conn


def migrar() -> list[str]:
    aplicadas = []
    with conexao() as conn:
        conn.execute("SELECT pg_advisory_lock(424242)")
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS migracoes (nome TEXT PRIMARY KEY, "
                         "aplicada_em TIMESTAMPTZ NOT NULL DEFAULT now())")
            feitas = {r["nome"] for r in conn.execute("SELECT nome FROM migracoes")}
            for arq in sorted(MIGRACOES.glob("*.sql")):
                if arq.name in feitas:
                    continue
                conn.execute(arq.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO migracoes (nome) VALUES (%s)", (arq.name,))
                aplicadas.append(arq.name)
            conn.commit()
        finally:
            conn.execute("SELECT pg_advisory_unlock(424242)")
    return aplicadas


def evento(conn, tipo: str, execucao_id=None, lote_id=None, no_id=None, **detalhe) -> None:
    conn.execute(
        "INSERT INTO eventos_execucao (execucao_id, lote_id, no_id, tipo, detalhe) "
        "VALUES (%s, %s, %s, %s, %s)",
        (execucao_id, lote_id, no_id, tipo, Jsonb(detalhe)),
    )


__all__ = ["Jsonb", "conexao", "evento", "fechar", "migrar", "pool"]

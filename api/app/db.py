"""Acesso ao PostgreSQL (psycopg 3 + pool)."""
from contextlib import contextmanager

from alembic import command
from alembic.config import Config as AlembicConfig
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from . import config

ALEMBIC_INI = config.RAIZ / "alembic.ini"
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


def migrar() -> None:
    """Aplica as revisões pendentes do Alembic (api/migracoes), como `alembic upgrade head`."""
    cfg = AlembicConfig(str(ALEMBIC_INI))
    cfg.attributes["configurar_logging"] = False  # não sobrescreve o logging da API
    command.upgrade(cfg, "head")


def evento(conn, tipo: str, execucao_id=None, lote_id=None, no_id=None, **detalhe) -> None:
    conn.execute(
        "INSERT INTO eventos_execucao (execucao_id, lote_id, no_id, tipo, detalhe) "
        "VALUES (%s, %s, %s, %s, %s)",
        (execucao_id, lote_id, no_id, tipo, Jsonb(detalhe)),
    )


__all__ = ["Jsonb", "conexao", "evento", "fechar", "migrar", "pool"]

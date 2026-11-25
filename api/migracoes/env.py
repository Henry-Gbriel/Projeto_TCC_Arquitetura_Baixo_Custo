"""Ambiente do Alembic: conecta com o mesmo DSN da API (app/config.py) via psycopg 3.

Sem ORM: as revisões usam SQL puro (op.execute). Usado pela CLI (`alembic upgrade head`) e por
`db.migrar()` na inicialização da API, que passa a configuração sem mexer no logging do uvicorn.
"""
from logging.config import fileConfig

import psycopg
from alembic import context
from sqlalchemy import create_engine, pool, text

from app import config as app_config

TRAVA = 424242  # pg_advisory_lock: duas instâncias nunca migram ao mesmo tempo

cfg = context.config
if cfg.config_file_name and cfg.attributes.get("configurar_logging", True):
    fileConfig(cfg.config_file_name)


def rodar() -> None:
    if context.is_offline_mode():
        raise SystemExit("Modo offline (--sql) não suportado: rode contra o banco.")
    motor = create_engine("postgresql+psycopg://", creator=lambda: psycopg.connect(app_config.PG_DSN),
                          poolclass=pool.NullPool)
    with motor.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(:t)"), {"t": TRAVA})
        conn.commit()  # a trava é da sessão; o Alembic abre as próprias transações
        try:
            context.configure(connection=conn, transaction_per_migration=True)
            with context.begin_transaction():
                context.run_migrations()
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:t)"), {"t": TRAVA})
            conn.commit()


rodar()

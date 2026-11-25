"""Esquema inicial (seção 8 da especificação).

O SQL fica em 0001_inicial.sql e é idempotente (IF NOT EXISTS): em um banco criado antes do Alembic,
esta revisão não altera nada e só registra a versão em alembic_version.

Revisão: 0001
Anterior:
"""
from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SQL = Path(__file__).with_suffix(".sql")


def upgrade() -> None:
    op.execute(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS silver_tipado")
    for tabela in ("registros_silver", "registros_origem", "eventos_execucao", "lotes", "nos",
                   "execucoes", "coletas", "arquivos_bronze"):
        op.execute(f"DROP TABLE IF EXISTS {tabela} CASCADE")
    op.execute("DROP SEQUENCE IF EXISTS execucoes_seq")

"""Remove a tabela migracoes (controle anterior ao Alembic, substituído por alembic_version).

Revisão: 0002
Anterior: 0001
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS migracoes")


def downgrade() -> None:
    op.execute("CREATE TABLE IF NOT EXISTS migracoes (nome TEXT PRIMARY KEY, "
               "aplicada_em TIMESTAMPTZ NOT NULL DEFAULT now())")

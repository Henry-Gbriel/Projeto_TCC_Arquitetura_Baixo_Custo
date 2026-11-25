"""Usuários do painel de controle e a camada Gold materializada usada pela consulta pública.

gold_transacoes: uma linha por transação de compra e venda, deduplicada entre execuções
(mesmo SQL, data e valor), com o tipo de imóvel agrupado e o preço do m² já calculado.
Atualizada pela API quando uma execução termina (gold.atualizar_transacoes).

Revisão: 0003
Anterior: 0002
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

TIPO = """CASE
    WHEN descricao_uso LIKE 'APARTAMENTO%' OR descricao_uso LIKE 'FLAT RESIDENCIAL%'
         OR descricao_uso LIKE 'PRÉDIO DE APARTAMENTO%' THEN 'apartamento'
    WHEN descricao_uso LIKE 'RESIDÊNCIA%' THEN 'casa'
    WHEN descricao_uso LIKE 'TERRENO%' THEN 'terreno'
    WHEN descricao_uso LIKE 'LOJA%' OR descricao_uso LIKE 'ESCRITÓRIO%' OR descricao_uso LIKE 'PRÉDIO DE ESCRITÓRIO%'
         OR descricao_uso LIKE 'FLAT DE USO COMERCIAL%' OR descricao_uso LIKE 'HOTEL%'
         OR descricao_uso LIKE 'INDÚSTRIA%' OR descricao_uso LIKE 'ARMAZÉNS%' OR descricao_uso LIKE 'OFICINA%'
         THEN 'comercial'
END"""


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id            SERIAL PRIMARY KEY,
            usuario       TEXT NOT NULL UNIQUE,
            nome          TEXT,
            senha_hash    TEXT NOT NULL,             -- scrypt$sal$hash
            ativo         BOOLEAN NOT NULL DEFAULT true,
            criado_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
            ultimo_login  TIMESTAMPTZ
        )""")
    # Critério de outlier: só compra e venda, área >= 10 m² e preço entre R$ 500 e R$ 60.000 por m².
    op.execute(f"""
        CREATE MATERIALIZED VIEW gold_transacoes AS
        WITH t AS (
            SELECT DISTINCT ON (sql_id, data_transacao, valor_transacao)
                   registro_origem_id, execucao_id,
                   NULLIF(regexp_replace(upper(trim(bairro)), '\\s+', ' ', 'g'), '') AS bairro,
                   NULLIF(regexp_replace(upper(trim(s.dados_tratados->>'logradouro')), '\\s+', ' ', 'g'), '')
                       AS logradouro,
                   data_transacao, valor_transacao, area_construida, area_terreno, {TIPO} AS tipo
            FROM silver_tipado
            JOIN registros_silver s USING (registro_origem_id, execucao_id)
            WHERE transacao LIKE '1.%' AND valor_transacao > 0 AND data_transacao IS NOT NULL
            ORDER BY sql_id, data_transacao, valor_transacao, registro_origem_id DESC
        ), m AS (
            SELECT *, CASE WHEN tipo = 'terreno' THEN area_terreno ELSE area_construida END AS area FROM t
            WHERE tipo IS NOT NULL
        )
        SELECT registro_origem_id, execucao_id, bairro, logradouro, tipo, data_transacao,
               date_trunc('quarter', data_transacao)::date AS trimestre,
               valor_transacao, area, round(valor_transacao / area, 2) AS preco_m2
        FROM m
        WHERE area >= 10 AND valor_transacao / area BETWEEN 500 AND 60000
        WITH DATA""")
    op.execute("CREATE UNIQUE INDEX gold_transacoes_pk ON gold_transacoes (registro_origem_id)")
    op.execute("CREATE INDEX gold_transacoes_bairro ON gold_transacoes (bairro, tipo, data_transacao)")
    op.execute("CREATE INDEX gold_transacoes_data ON gold_transacoes (tipo, data_transacao)")


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS gold_transacoes")
    op.execute("DROP TABLE IF EXISTS usuarios")

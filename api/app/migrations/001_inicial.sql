-- Modelo lógico mínimo (seção 8 da especificação).

CREATE TABLE IF NOT EXISTS arquivos_bronze (
    id              SERIAL PRIMARY KEY,
    nome_original   TEXT NOT NULL,
    caminho         TEXT NOT NULL,
    sha256          CHAR(64) NOT NULL UNIQUE,
    tamanho         BIGINT NOT NULL,
    formato         TEXT NOT NULL,                 -- xlsx | xls | desconhecido
    ano_fonte       INT,                           -- ano do rótulo na página oficial (ou informado no upload)
    url_origem      TEXT,
    url_final       TEXT,                          -- após redirecionamentos
    redirecionamentos JSONB NOT NULL DEFAULT '[]',
    etag            TEXT,
    last_modified   TEXT,
    abas            JSONB NOT NULL DEFAULT '[]',   -- abas mensais detectadas
    coletado_em     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS arquivos_bronze_ano ON arquivos_bronze (ano_fonte);

CREATE TABLE IF NOT EXISTS coletas (
    id              SERIAL PRIMARY KEY,
    parametros      JSONB NOT NULL,
    status          TEXT NOT NULL,                 -- em_andamento | concluida | falhou
    progresso       JSONB NOT NULL DEFAULT '{}',   -- por ano: status, arquivo_id, mensagem
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT now(),
    concluido_em    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS execucoes (
    id                  TEXT PRIMARY KEY,          -- exec-000001
    arquivo_id          INT NOT NULL REFERENCES arquivos_bronze(id),
    ano                 INT NOT NULL,
    mes                 TEXT,
    limite_registros    INT,
    abas_selecionadas   TEXT[] NOT NULL,
    nos                 TEXT[] NOT NULL,           -- nós que podem receber lotes
    tamanho_lote        INT NOT NULL,
    status              TEXT NOT NULL,             -- preparando | em_andamento | concluida | falhou
    total_esperado      INT,
    mensagem            TEXT,
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT now(),
    iniciado_em         TIMESTAMPTZ,
    concluido_em        TIMESTAMPTZ
);
CREATE SEQUENCE IF NOT EXISTS execucoes_seq;

CREATE TABLE IF NOT EXISTS lotes (
    id              TEXT PRIMARY KEY,              -- exec-000001-lote-0014
    execucao_id     TEXT NOT NULL REFERENCES execucoes(id) ON DELETE CASCADE,
    numero          INT NOT NULL,
    no_id           TEXT,
    estado          TEXT NOT NULL,                 -- pendente | atribuido | processando | concluido | falhou
    total           INT NOT NULL,
    tentativas      INT NOT NULL DEFAULT 0,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT now(),
    atribuido_em    TIMESTAMPTZ,
    primeiro_resultado_em TIMESTAMPTZ,
    concluido_em    TIMESTAMPTZ,
    UNIQUE (execucao_id, numero)
);
CREATE INDEX IF NOT EXISTS lotes_estado ON lotes (execucao_id, estado, numero);

CREATE TABLE IF NOT EXISTS registros_origem (
    id              BIGSERIAL PRIMARY KEY,
    execucao_id     TEXT NOT NULL REFERENCES execucoes(id) ON DELETE CASCADE,
    arquivo_id      INT NOT NULL REFERENCES arquivos_bronze(id),
    aba             TEXT NOT NULL,
    linha           INT NOT NULL,
    registro_id     TEXT NOT NULL,                 -- arquivo-01:JAN-2026:2
    lote_id         TEXT NOT NULL REFERENCES lotes(id) ON DELETE CASCADE,
    posicao         INT NOT NULL,                  -- 1..total do lote
    dados           JSONB NOT NULL,                -- 28 colunas, representação transportável (sem limpeza)
    tipos           JSONB NOT NULL,                -- tipo da célula de origem por campo
    extras          JSONB NOT NULL DEFAULT '{}',   -- colunas fora do esquema com valor
    envios          INT NOT NULL DEFAULT 0,
    primeiro_envio_em TIMESTAMPTZ,
    ultimo_envio_em TIMESTAMPTZ,
    UNIQUE (execucao_id, arquivo_id, aba, linha),
    UNIQUE (execucao_id, registro_id),
    UNIQUE (lote_id, posicao)
);

CREATE TABLE IF NOT EXISTS registros_silver (
    id                  BIGSERIAL PRIMARY KEY,
    execucao_id         TEXT NOT NULL REFERENCES execucoes(id) ON DELETE CASCADE,
    registro_origem_id  BIGINT NOT NULL REFERENCES registros_origem(id) ON DELETE CASCADE,
    lote_id             TEXT NOT NULL,
    no_id               TEXT NOT NULL,
    status              TEXT NOT NULL,             -- processado | erro
    dados_tratados      JSONB,
    erros               JSONB NOT NULL DEFAULT '[]',
    versao_regras       TEXT,
    duracao_no_us       BIGINT,                    -- tempo relatado pelo nó
    mem_livre_no        INT,                       -- gc.mem_free() após o processamento
    simulado            BOOLEAN NOT NULL DEFAULT false,
    enviado_em          TIMESTAMPTZ,
    recebido_em         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (execucao_id, registro_origem_id)
);

CREATE TABLE IF NOT EXISTS eventos_execucao (
    id              BIGSERIAL PRIMARY KEY,
    execucao_id     TEXT REFERENCES execucoes(id) ON DELETE CASCADE,
    lote_id         TEXT,
    no_id           TEXT,
    tipo            TEXT NOT NULL,
    detalhe         JSONB NOT NULL DEFAULT '{}',
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS eventos_execucao_exec ON eventos_execucao (execucao_id, id);

CREATE TABLE IF NOT EXISTS nos (
    no_id           TEXT PRIMARY KEY,
    estado          TEXT NOT NULL,                 -- estado relatado pelo nó
    lote_atual      TEXT,                          -- lote atribuído pelo orquestrador
    simulado        BOOLEAN NOT NULL DEFAULT false,
    mem_livre       INT,
    detalhe         JSONB NOT NULL DEFAULT '{}',
    ultimo_contato  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Projeção tipada do Silver para consultas e Gold. Uma linha por registro de origem.
CREATE OR REPLACE VIEW silver_tipado AS
SELECT
    s.execucao_id, s.registro_origem_id, o.registro_id, o.aba, o.linha, s.no_id, s.simulado,
    s.dados_tratados->>'id'                                AS sql_id,
    s.dados_tratados->>'bairro'                            AS bairro,
    s.dados_tratados->>'cep'                               AS cep,
    s.dados_tratados->>'transacao'                         AS transacao,
    (s.dados_tratados->>'valor_transacao')::numeric        AS valor_transacao,
    (s.dados_tratados->>'data_transacao')::date            AS data_transacao,
    (s.dados_tratados->>'valor_venal_referencia')::numeric AS valor_venal_referencia,
    (s.dados_tratados->>'base_calculo')::numeric           AS base_calculo,
    (s.dados_tratados->>'valor_financiado')::numeric       AS valor_financiado,
    s.dados_tratados->>'tipo_financiamento'                AS tipo_financiamento,
    (s.dados_tratados->>'area_construida')::numeric        AS area_construida,
    (s.dados_tratados->>'area_terreno')::numeric           AS area_terreno,
    s.dados_tratados->>'descricao_uso'                     AS descricao_uso,
    s.dados_tratados->>'descricao_padrao'                  AS descricao_padrao,
    (s.dados_tratados->>'acc_iptu')::int                   AS acc_iptu,
    jsonb_array_length(s.erros)                            AS qtd_erros
FROM registros_silver s
JOIN registros_origem o ON o.id = s.registro_origem_id;

CREATE TABLE IF NOT EXISTS migracoes (nome TEXT PRIMARY KEY, aplicada_em TIMESTAMPTZ NOT NULL DEFAULT now());

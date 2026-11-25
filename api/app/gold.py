"""Gold: indicadores agregados calculados SOMENTE a partir do Silver (respostas dos nós).

A unicidade (execucao_id, registro_origem_id) em registros_silver garante que uma resposta
MQTT repetida nunca é contada duas vezes. Conjunto inicial; a definição fina vem após o
primeiro ciclo completo (seção 2 da especificação).
"""
import logging
import re
import threading
import time
import unicodedata

from . import config, db


def indicadores(exec_id: str) -> dict:
    with db.conexao() as conn:
        geral = conn.execute(
            """SELECT count(*) AS registros,
                      count(*) FILTER (WHERE qtd_erros > 0) AS registros_com_erro,
                      count(valor_transacao) AS com_valor,
                      sum(valor_transacao) AS valor_total,
                      round(avg(valor_transacao), 2) AS valor_medio,
                      percentile_cont(0.5) WITHIN GROUP (ORDER BY valor_transacao) AS valor_mediano,
                      min(valor_transacao) AS valor_min, max(valor_transacao) AS valor_max,
                      round(avg(valor_transacao / NULLIF(area_construida, 0)), 2) AS valor_m2_construido_medio,
                      min(data_transacao) AS data_transacao_min, max(data_transacao) AS data_transacao_max
               FROM silver_tipado WHERE execucao_id = %s""", (exec_id,)).fetchone()
        por_natureza = conn.execute(
            """SELECT transacao, count(*) AS registros, round(avg(valor_transacao), 2) AS valor_medio
               FROM silver_tipado WHERE execucao_id = %s GROUP BY transacao
               ORDER BY registros DESC LIMIT 15""", (exec_id,)).fetchall()
        por_bairro = conn.execute(
            """SELECT bairro, count(*) AS registros,
                      percentile_cont(0.5) WITHIN GROUP (ORDER BY valor_transacao) AS valor_mediano
               FROM silver_tipado WHERE execucao_id = %s AND bairro IS NOT NULL GROUP BY bairro
               ORDER BY registros DESC LIMIT 15""", (exec_id,)).fetchall()
        por_aba = conn.execute(
            """SELECT aba, count(*) AS registros, sum(valor_transacao) AS valor_total
               FROM silver_tipado WHERE execucao_id = %s GROUP BY aba ORDER BY aba""",
            (exec_id,)).fetchall()
        por_financiamento = conn.execute(
            """SELECT tipo_financiamento, count(*) AS registros, sum(valor_financiado) AS valor_financiado
               FROM silver_tipado WHERE execucao_id = %s GROUP BY tipo_financiamento
               ORDER BY registros DESC""", (exec_id,)).fetchall()
        erros_por_motivo = conn.execute(
            """SELECT e->>'campo' AS campo, e->>'motivo' AS motivo, count(*) AS ocorrencias
               FROM registros_silver s, jsonb_array_elements(s.erros) e
               WHERE s.execucao_id = %s GROUP BY 1, 2 ORDER BY ocorrencias DESC""", (exec_id,)).fetchall()
        por_no = conn.execute(
            """SELECT no_id, simulado, count(*) AS registros FROM registros_silver
               WHERE execucao_id = %s GROUP BY no_id, simulado ORDER BY no_id""", (exec_id,)).fetchall()
    return {"geral": geral, "por_natureza": por_natureza, "por_bairro": por_bairro, "por_aba": por_aba,
            "por_financiamento": por_financiamento, "erros_por_motivo": erros_por_motivo, "por_no": por_no}


def metricas(exec_id: str) -> dict:
    """Medições do experimento (seção 7): fila, trânsito, tempo no nó, total, tentativas, memória."""
    with db.conexao() as conn:
        execucao = conn.execute(
            """SELECT id, status, total_esperado, nos, iniciado_em, concluido_em,
                      extract(epoch FROM (coalesce(concluido_em, now()) - iniciado_em)) AS duracao_total_s
               FROM execucoes WHERE id = %s""", (exec_id,)).fetchone()
        por_no = conn.execute(
            """SELECT s.no_id, s.simulado, count(*) AS registros,
                      round(avg(s.duracao_no_us) / 1000.0, 3) AS processamento_no_ms_medio,
                      round(max(s.duracao_no_us) / 1000.0, 3) AS processamento_no_ms_max,
                      round(avg(extract(epoch FROM (s.recebido_em - s.enviado_em)) * 1000
                                - coalesce(s.duracao_no_us, 0) / 1000.0)::numeric, 3)
                          AS rede_mqtt_ms_medio,  -- ida e volta pelo broker menos o tempo relatado pelo nó
                      round(avg(extract(epoch FROM (s.recebido_em - s.enviado_em)) * 1000)::numeric, 3)
                          AS ida_e_volta_ms_medio,
                      min(s.mem_livre_no) AS mem_livre_min, max(s.mem_livre_no) AS mem_livre_max,
                      sum(jsonb_array_length(s.erros)) AS erros_campo
               FROM registros_silver s WHERE s.execucao_id = %s GROUP BY s.no_id, s.simulado ORDER BY s.no_id""",
            (exec_id,)).fetchall()
        lotes = conn.execute(
            """SELECT count(*) AS lotes, sum(tentativas) AS tentativas,
                      count(*) FILTER (WHERE tentativas > 1) AS lotes_reatribuidos,
                      count(*) FILTER (WHERE estado = 'falhou') AS lotes_falhos,
                      round(avg(extract(epoch FROM (atribuido_em - criado_em)))::numeric, 3) AS fila_s_medio,
                      round(avg(extract(epoch FROM (concluido_em - atribuido_em)))::numeric, 3) AS lote_s_medio
               FROM lotes WHERE execucao_id = %s""", (exec_id,)).fetchone()
        eventos = conn.execute(
            """SELECT tipo, count(*) AS ocorrencias FROM eventos_execucao WHERE execucao_id = %s
               GROUP BY tipo ORDER BY tipo""", (exec_id,)).fetchall()
        envios = conn.execute(
            "SELECT sum(envios) AS envios, count(*) AS registros FROM registros_origem WHERE execucao_id = %s",
            (exec_id,)).fetchone()
    return {"execucao": execucao, "lotes": lotes, "envios": envios, "por_no": por_no,
            "eventos": {e["tipo"]: e["ocorrencias"] for e in eventos}}


# ---------------------------------------------------------------- consulta pública (gold_transacoes)
TIPOS = ("apartamento", "casa", "comercial", "terreno")
PERIODOS = {"12m": "1 year", "3a": "3 years", "5a": "5 years", "tudo": None}
CRITERIO = ("Preço do m² = valor declarado da transação ÷ área construída (área do terreno, para terrenos). "
            "Entram só compras e vendas com área de pelo menos 10 m² e preço entre R$ 500 e R$ 60.000 por m²; "
            "registros repetidos entre execuções contam uma vez.")
_ABREVIACOES = {"RUA": "R", "AVENIDA": "AV", "ALAMEDA": "AL", "TRAVESSA": "TV", "PRACA": "PC", "ESTRADA": "EST",
                "RODOVIA": "ROD", "LARGO": "LGO", "VIELA": "VL", "DOUTOR": "DR", "PROFESSOR": "PROF"}
MINIMO_VARIACAO = 10  # transações em cada janela de 12 meses para calcular a variação
_atualizando = threading.Lock()
log = logging.getLogger("gold")


def normalizar(texto: str | None) -> str | None:
    """'Pinheiros ' -> 'PINHEIROS'; tira acentos e espaços repetidos, como os campos do ITBI."""
    if not texto or not texto.strip():
        return None
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento).strip().upper()


def normalizar_rua(texto: str | None) -> str | None:
    """'Rua Doutor José Elias' -> 'R DR JOSE ELIAS' (abreviações usadas no cadastro do IPTU)."""
    t = normalizar(texto)
    if not t:
        return None
    return " ".join(_ABREVIACOES.get(p, p) for p in t.replace(".", "").split())


def atualizar_transacoes() -> None:
    """Recalcula gold_transacoes a partir do Silver. Uma atualização por vez; leituras não bloqueiam."""
    if not _atualizando.acquire(blocking=False):
        return
    try:
        inicio = time.monotonic()
        with db.conexao() as conn:
            conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY gold_transacoes")
        log.info("gold_transacoes atualizada em %.1f s", time.monotonic() - inicio)
    except Exception:
        log.exception("Falha ao atualizar gold_transacoes")
    finally:
        _atualizando.release()


def atualizar_transacoes_em_segundo_plano() -> None:
    threading.Thread(target=atualizar_transacoes, daemon=True, name="gold").start()


def bairros(busca: str | None, limite: int = 8) -> list[dict]:
    termo = normalizar(busca) or ""
    with db.conexao() as conn:
        return conn.execute(
            """SELECT bairro, count(*) AS transacoes FROM gold_transacoes
               WHERE bairro LIKE %(contem)s GROUP BY bairro
               ORDER BY (bairro LIKE %(prefixo)s) DESC, count(*) DESC LIMIT %(limite)s""",
            {"contem": f"%{termo}%", "prefixo": f"{termo}%", "limite": limite}).fetchall()


def ruas(bairro: str | None, busca: str | None, limite: int = 8) -> list[dict]:
    with db.conexao() as conn:
        return conn.execute(
            """SELECT logradouro, count(*) AS transacoes FROM gold_transacoes
               WHERE logradouro LIKE %(contem)s AND (%(bairro)s::text IS NULL OR bairro = %(bairro)s)
               GROUP BY logradouro ORDER BY count(*) DESC LIMIT %(limite)s""",
            {"contem": f"%{normalizar_rua(busca) or ''}%", "bairro": normalizar(bairro), "limite": limite}).fetchall()


def consulta_preco(bairro: str | None, rua: str | None, tipo: str, area_min: float | None,
                   area_max: float | None, periodo: str) -> dict:
    """Preço do m² de um recorte (bairro/rua, tipo, área, período), comparado com a cidade toda.

    O período conta para trás a partir da transação mais recente do recorte, não da data de hoje:
    a base tem anos inteiros sem carga, e "últimos 12 meses" contados de hoje viria vazio.
    """
    p = {"bairro": normalizar(bairro), "rua": f"%{normalizar_rua(rua)}%" if normalizar_rua(rua) else None,
         "tipo": tipo, "area_min": area_min, "area_max": area_max, "intervalo": PERIODOS[periodo]}
    # Recorte da cidade (tipo e área) e, dentro dele, o recorte local (bairro e rua).
    cidade = """tipo = %(tipo)s AND (%(area_min)s::numeric IS NULL OR area >= %(area_min)s)
                AND (%(area_max)s::numeric IS NULL OR area <= %(area_max)s)"""
    local = """(%(bairro)s::text IS NULL OR bairro = %(bairro)s)
               AND (%(rua)s::text IS NULL OR logradouro LIKE %(rua)s)"""
    no_periodo = "(%(intervalo)s::interval IS NULL OR data_transacao > %(ref)s::date - %(intervalo)s::interval)"
    ano = "data_transacao > %(ref)s::date - interval '1 year'"
    ano_anterior = ("data_transacao > %(ref)s::date - interval '2 years' "
                    "AND data_transacao <= %(ref)s::date - interval '1 year'")
    with db.conexao() as conn:
        p["ref"] = conn.execute(f"SELECT max(data_transacao) AS ref FROM gold_transacoes WHERE {cidade} AND {local}",
                                p).fetchone()["ref"]
        ultima_carga = conn.execute(
            "SELECT max(concluido_em) AS em FROM execucoes WHERE status='concluida'").fetchone()["em"]
        base = {"criterio": CRITERIO, "amostra_minima": config.AMOSTRA_MINIMA, "ultima_carga": ultima_carga,
                "referencia": p["ref"]}
        if p["ref"] is None:
            return {**base, "resumo": None, "serie": [], "por_tipo": [], "ruas": []}
        resumo = conn.execute(
            f"""SELECT count(*) FILTER (WHERE {local} AND {no_periodo}) AS transacoes,
                       round(avg(preco_m2) FILTER (WHERE {local} AND {no_periodo}), 2) AS preco_m2_medio,
                       percentile_cont(0.25) WITHIN GROUP (ORDER BY preco_m2) FILTER (WHERE {local} AND {no_periodo})
                           AS p25,
                       percentile_cont(0.75) WITHIN GROUP (ORDER BY preco_m2) FILTER (WHERE {local} AND {no_periodo})
                           AS p75,
                       min(data_transacao) FILTER (WHERE {local} AND {no_periodo}) AS inicio,
                       round(avg(preco_m2) FILTER (WHERE {no_periodo}), 2) AS cidade_preco_m2_medio,
                       avg(preco_m2) FILTER (WHERE {local} AND {ano}) AS ano,
                       avg(preco_m2) FILTER (WHERE {local} AND {ano_anterior}) AS ano_anterior,
                       count(*) FILTER (WHERE {local} AND {ano}) AS n_ano,
                       count(*) FILTER (WHERE {local} AND {ano_anterior}) AS n_ano_anterior,
                       avg(preco_m2) FILTER (WHERE {ano}) AS cidade_ano,
                       avg(preco_m2) FILTER (WHERE {ano_anterior}) AS cidade_ano_anterior,
                       count(*) FILTER (WHERE {ano}) AS cidade_n_ano,
                       count(*) FILTER (WHERE {ano_anterior}) AS cidade_n_ano_anterior
                FROM gold_transacoes WHERE {cidade}""", p).fetchone()
        serie = conn.execute(
            f"""SELECT trimestre, round(avg(preco_m2) FILTER (WHERE {local}), 2) AS local,
                       count(*) FILTER (WHERE {local}) AS transacoes, round(avg(preco_m2), 2) AS cidade
                FROM gold_transacoes WHERE {cidade} AND {no_periodo}
                GROUP BY trimestre HAVING count(*) FILTER (WHERE {local}) > 0 ORDER BY trimestre""", p).fetchall()
        por_tipo = conn.execute(
            f"""SELECT tipo, count(*) AS transacoes, round(avg(preco_m2), 2) AS preco_m2_medio FROM gold_transacoes
                WHERE {local} AND {no_periodo} AND (%(area_min)s::numeric IS NULL OR area >= %(area_min)s)
                  AND (%(area_max)s::numeric IS NULL OR area <= %(area_max)s)
                GROUP BY tipo ORDER BY preco_m2_medio DESC""", p).fetchall()
        # Ruas do bairro (ou as que casam com a busca, sem bairro), sem o filtro de rua.
        ruas_top = conn.execute(
            f"""SELECT logradouro, count(*) FILTER (WHERE {no_periodo}) AS transacoes,
                       round(avg(preco_m2) FILTER (WHERE {no_periodo}), 2) AS preco_m2_medio,
                       avg(preco_m2) FILTER (WHERE {ano}) AS ano, avg(preco_m2) FILTER (WHERE {ano_anterior})
                           AS ano_anterior,
                       count(*) FILTER (WHERE {ano}) AS n_ano, count(*) FILTER (WHERE {ano_anterior}) AS n_ano_anterior
                FROM gold_transacoes
                WHERE {cidade} AND logradouro IS NOT NULL AND (%(bairro)s::text IS NULL OR bairro = %(bairro)s)
                  AND (%(bairro)s::text IS NOT NULL OR %(rua)s::text IS NULL OR logradouro LIKE %(rua)s)
                GROUP BY logradouro HAVING count(*) FILTER (WHERE {no_periodo}) > 0
                ORDER BY transacoes DESC LIMIT 5""", p).fetchall()

    def variacao(linha, prefixo=""):
        """Média dos últimos 12 meses contra os 12 anteriores; None se algum lado tem poucas transações."""
        atual, anterior = linha[prefixo + "ano"], linha[prefixo + "ano_anterior"]
        if min(linha[prefixo + "n_ano"], linha[prefixo + "n_ano_anterior"]) < MINIMO_VARIACAO:
            return None
        return round(float(atual / anterior - 1) * 100, 1)

    return {**base,
            "resumo": {"transacoes": resumo["transacoes"], "preco_m2_medio": resumo["preco_m2_medio"],
                       "p25": resumo["p25"], "p75": resumo["p75"], "inicio": resumo["inicio"],
                       "cidade_preco_m2_medio": resumo["cidade_preco_m2_medio"],
                       "variacao_12m": variacao(resumo), "variacao_12m_cidade": variacao(resumo, "cidade_")},
            "serie": serie, "por_tipo": por_tipo,
            "ruas": [{"logradouro": r["logradouro"], "transacoes": r["transacoes"],
                      "preco_m2_medio": r["preco_m2_medio"], "variacao_12m": variacao(r)}
                     for r in ruas_top]}


# ---------------------------------------------------------------- cluster ao vivo
def cluster(broker_conectado: bool, disponiveis: set[str]) -> dict:
    """Tela "sala das máquinas": totais do Silver, situação de cada nó, fila de lotes e log recente."""
    with db.conexao() as conn:
        totais = conn.execute(
            """SELECT count(*) AS registros, count(*) FILTER (WHERE jsonb_array_length(erros) > 0) AS com_erro,
                      count(*) FILTER (WHERE recebido_em > now() - interval '60 seconds') AS ultimo_minuto
               FROM registros_silver""").fetchone()
        nos = conn.execute(
            """SELECT n.no_id, n.estado, n.lote_atual, n.simulado, n.mem_livre,
                      extract(epoch FROM now() - n.ultimo_contato) AS segundos_sem_contato,
                      (SELECT count(*) FROM lotes l WHERE l.no_id = n.no_id AND l.estado = 'concluido')
                          AS lotes_processados,
                      (SELECT round(avg(extract(epoch FROM l.concluido_em - l.atribuido_em))::numeric, 2) FROM lotes l
                       WHERE l.no_id = n.no_id AND l.estado = 'concluido') AS tempo_medio_lote_s,
                      (SELECT count(*) FROM registros_silver s WHERE s.no_id = n.no_id) AS registros
               FROM nos n ORDER BY n.no_id""").fetchall()
        execucao = conn.execute(
            """SELECT e.id, e.status, e.total_esperado, e.ano, e.mes, e.criado_em, e.concluido_em,
                      (SELECT count(*) FROM lotes l WHERE l.execucao_id = e.id) AS lotes,
                      (SELECT count(*) FROM lotes l WHERE l.execucao_id = e.id AND l.estado = 'concluido')
                          AS lotes_concluidos,
                      (SELECT count(*) FROM lotes l WHERE l.execucao_id = e.id AND l.estado = 'pendente')
                          AS lotes_na_fila,
                      (SELECT count(*) FROM lotes l WHERE l.execucao_id = e.id
                         AND l.estado IN ('atribuido', 'processando')) AS lotes_em_voo,
                      (SELECT count(*) FROM registros_silver s WHERE s.execucao_id = e.id) AS processados
               FROM execucoes e
               ORDER BY (e.status IN ('em_andamento', 'preparando')) DESC, e.criado_em DESC LIMIT 1""").fetchone()
        log_eventos = conn.execute(
            """SELECT id, criado_em, tipo, execucao_id, lote_id, no_id, detalhe FROM eventos_execucao
               WHERE tipo <> 'resposta_duplicada' ORDER BY id DESC LIMIT 40""").fetchall()
    conhecidos = {n["no_id"] for n in nos}
    nos += [{"no_id": no_id, "estado": "nunca_conectado", "lotes_processados": 0, "registros": 0}
            for no_id in config.NOS_PADRAO if no_id not in conhecidos]
    for n in nos:
        n["disponivel"] = n["no_id"] in disponiveis
    return {"broker_conectado": broker_conectado, "tamanho_lote": config.TAMANHO_LOTE,
            "registros_validados": totais["registros"], "registros_com_erro": totais["com_erro"],
            "taxa_erro": round(totais["com_erro"] / totais["registros"], 4) if totais["registros"] else 0.0,
            "vazao_reg_s": round(totais["ultimo_minuto"] / 60, 2),
            "nos_ativos": sum(n["disponivel"] for n in nos), "nos": nos,
            "execucao": execucao, "log": log_eventos}

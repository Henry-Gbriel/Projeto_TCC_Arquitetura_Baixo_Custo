"""Gold: indicadores agregados calculados SOMENTE a partir do Silver (respostas dos nós).

A unicidade (execucao_id, registro_origem_id) em registros_silver garante que uma resposta
MQTT repetida nunca é contada duas vezes. Conjunto inicial; a definição fina vem após o
primeiro ciclo completo (seção 2 da especificação).
"""
from . import db


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

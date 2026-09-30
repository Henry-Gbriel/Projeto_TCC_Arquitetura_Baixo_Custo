"""Orquestrador: distribui lotes aos ESP32 via MQTT e persiste as respostas (seções 6 e 7).

Modelo de concorrência: callbacks do paho só enfileiram mensagens; uma única thread
consome a fila e executa toda a lógica com o banco. Assim não há corrida entre
resultados, timeouts e atribuições.

Fonte de verdade: PostgreSQL. Um lote está concluído quando a contagem de respostas
únicas persistidas é igual ao seu total; uma execução, quando todos os registros
esperados têm resultado. Estado em memória (registro pendente por lote) serve apenas
para timeouts e é reconstruível: no reinício, lotes ativos voltam a pendente.
"""
import json
import logging
import queue
import threading
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from . import config, db
from .canonico import COLUNAS

log = logging.getLogger("orquestrador")

ATIVOS = ("atribuido", "processando")
INTERVALO_TICK_S = 0.5


class Orquestrador:
    def __init__(self):
        self.fila: queue.Queue = queue.Queue()
        self.nos: dict[str, dict] = {}          # no_id -> {estado, visto, simulado, bloqueado_ate}
        self.pendentes: dict[str, dict] = {}    # lote_id -> registro em voo
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None
        self.conectado = False
        p = config.MQTT_PREFIXO
        self.topico_tarefa = p + "/nos/{}/tarefa"
        self.topico_resultados = p + "/resultados"
        self.topico_estado = p + "/nos/+/estado"
        self.cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=config.MQTT_CLIENT_ID,
                                   clean_session=True)
        if config.MQTT_USUARIO:
            self.cliente.username_pw_set(config.MQTT_USUARIO, config.MQTT_SENHA)
        self.cliente.on_connect = self._on_connect
        self.cliente.on_disconnect = self._on_disconnect
        self.cliente.on_message = lambda c, u, m: self.fila.put(
            ("mqtt", m.topic, m.payload, datetime.now(timezone.utc)))
        self.cliente.reconnect_delay_set(1, 10)

    # ------------------------------------------------------------------ ciclo de vida
    def iniciar(self) -> None:
        self.recuperar()
        self.cliente.connect_async(config.MQTT_HOST, config.MQTT_PORTA, keepalive=30)
        self.cliente.loop_start()
        self._thread = threading.Thread(target=self._laco, daemon=True, name="orquestrador")
        self._thread.start()

    def parar(self) -> None:
        self._parar.set()
        self.fila.put(("parar",))
        if self._thread:
            self._thread.join(timeout=5)
        self.cliente.loop_stop()
        self.cliente.disconnect()

    def acordar(self) -> None:
        self.fila.put(("acordar",))

    def _on_connect(self, cliente, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            log.error("Falha ao conectar ao broker: %s", reason_code)
            return
        self.conectado = True
        cliente.subscribe([(self.topico_resultados, 1), (self.topico_estado, 1)])
        log.info("Conectado ao broker %s:%s", config.MQTT_HOST, config.MQTT_PORTA)

    def _on_disconnect(self, cliente, userdata, flags, reason_code, properties):
        self.conectado = False
        log.warning("Desconectado do broker: %s", reason_code)

    def _laco(self) -> None:
        proximo_tick = 0.0
        while not self._parar.is_set():
            try:
                item = self.fila.get(timeout=INTERVALO_TICK_S)
                self._tratar_item(item)
                while True:  # drena o que já chegou antes do próximo tick
                    self._tratar_item(self.fila.get_nowait())
            except queue.Empty:
                pass
            except Exception:
                log.exception("Erro no laço do orquestrador")
            if time.monotonic() >= proximo_tick:
                proximo_tick = time.monotonic() + INTERVALO_TICK_S
                try:
                    self.tick()
                except Exception:
                    log.exception("Erro no tick do orquestrador")

    def _tratar_item(self, item) -> None:
        if item[0] != "mqtt":
            return
        _, topico, payload, recebido_em = item
        try:
            msg = json.loads(payload)
        except (ValueError, UnicodeDecodeError):
            with db.conexao() as conn:
                db.evento(conn, "mensagem_invalida", topico=topico, payload=payload[:500].decode("latin-1"))
            return
        partes = topico.split("/")
        if topico == self.topico_resultados:
            self.tratar_resultado(msg, recebido_em)
        elif len(partes) == 4 and partes[1] == "nos" and partes[3] == "estado":
            self.tratar_estado(partes[2], msg)

    # ------------------------------------------------------------------ nós
    def no_disponivel(self, no_id: str) -> bool:
        n = self.nos.get(no_id)
        if not n or n["estado"] in ("offline", "erro"):
            return False
        agora = time.monotonic()
        return agora - n["visto"] <= config.NO_OFFLINE_S and agora >= n.get("bloqueado_ate", 0)

    def tratar_estado(self, no_id: str, msg: dict) -> None:
        estado = str(msg.get("estado", "desconhecido"))
        anterior = self.nos.get(no_id, {})
        self.nos[no_id] = {"estado": estado, "visto": time.monotonic(),
                           "simulado": bool(msg.get("simulado", False)),
                           "bloqueado_ate": anterior.get("bloqueado_ate", 0)}
        with db.conexao() as conn:
            conn.execute(
                """INSERT INTO nos (no_id, estado, simulado, mem_livre, detalhe, ultimo_contato)
                   VALUES (%s,%s,%s,%s,%s,now())
                   ON CONFLICT (no_id) DO UPDATE SET estado=EXCLUDED.estado, simulado=EXCLUDED.simulado,
                       mem_livre=COALESCE(EXCLUDED.mem_livre, nos.mem_livre), detalhe=EXCLUDED.detalhe,
                       ultimo_contato=now()""",
                (no_id, estado, bool(msg.get("simulado", False)), msg.get("mem_livre"), db.Jsonb(msg)))
            if estado != anterior.get("estado"):
                db.evento(conn, "estado_no", no_id=no_id, estado=estado, anterior=anterior.get("estado"))
            if estado == "offline":
                self._liberar_lotes_do_no(conn, no_id, "desconexao")

    def _liberar_lotes_do_no(self, conn, no_id: str, motivo: str) -> None:
        lotes = conn.execute("SELECT id FROM lotes WHERE no_id = %s AND estado = ANY(%s)",
                             (no_id, list(ATIVOS))).fetchall()
        for l in lotes:
            self._expirar_lote(conn, l["id"], motivo)

    # ------------------------------------------------------------------ distribuição
    def tick(self) -> None:
        with db.conexao() as conn:
            self._verificar_timeouts(conn)
            self._verificar_nos_silenciosos(conn)
            if self.conectado:
                self._distribuir(conn)

    def _distribuir(self, conn) -> None:
        execucoes = conn.execute(
            "SELECT id, nos FROM execucoes WHERE status = 'em_andamento' ORDER BY criado_em").fetchall()
        if not execucoes:
            return
        ocupados = {r["no_id"] for r in conn.execute(
            "SELECT no_id FROM lotes WHERE estado = ANY(%s) AND no_id IS NOT NULL", (list(ATIVOS),))}
        for ex in execucoes:
            for no_id in sorted(ex["nos"]):
                if no_id in ocupados or not self.no_disponivel(no_id):
                    continue
                lote = conn.execute(
                    """UPDATE lotes SET estado='atribuido', no_id=%s, tentativas=tentativas+1, atribuido_em=now()
                       WHERE id = (SELECT id FROM lotes WHERE execucao_id=%s AND estado='pendente'
                                   ORDER BY numero LIMIT 1 FOR UPDATE SKIP LOCKED)
                       RETURNING *""", (no_id, ex["id"])).fetchone()
                if not lote:
                    break
                ocupados.add(no_id)
                conn.execute("UPDATE nos SET lote_atual=%s WHERE no_id=%s", (lote["id"], no_id))
                db.evento(conn, "lote_atribuido", ex["id"], lote["id"], no_id, tentativa=lote["tentativas"])
                conn.commit()
                self._enviar_proximo(conn, lote["id"])

    def _enviar_proximo(self, conn, lote_id: str) -> None:
        lote = conn.execute("SELECT * FROM lotes WHERE id=%s", (lote_id,)).fetchone()
        if not lote or lote["estado"] not in ATIVOS:
            self.pendentes.pop(lote_id, None)
            return
        reg = conn.execute(
            """SELECT o.* FROM registros_origem o
               LEFT JOIN registros_silver s ON s.registro_origem_id = o.id
               WHERE o.lote_id = %s AND s.id IS NULL ORDER BY o.posicao LIMIT 1""", (lote_id,)).fetchone()
        if reg is None:
            self._concluir_lote(conn, lote_id)
            return
        self._publicar_tarefa(conn, lote, reg)
        self.pendentes[lote_id] = {"registro_origem_id": reg["id"], "registro": reg, "no_id": lote["no_id"],
                                   "enviado": time.monotonic(), "reenvios": 0}

    def _publicar_tarefa(self, conn, lote: dict, reg: dict) -> None:
        tarefa = {
            "versao": 1, "execucao_id": lote["execucao_id"], "lote_id": lote["id"],
            "registro_id": reg["registro_id"], "no_id": lote["no_id"], "posicao": reg["posicao"],
            "total_lote": lote["total"], "dados": reg["dados"], "tipos": reg["tipos"],
        }
        conn.execute("UPDATE registros_origem SET envios=envios+1, ultimo_envio_em=clock_timestamp(), "
                     "primeiro_envio_em=COALESCE(primeiro_envio_em, clock_timestamp()) WHERE id=%s", (reg["id"],))
        conn.commit()
        self.cliente.publish(self.topico_tarefa.format(lote["no_id"]),
                             json.dumps(tarefa, ensure_ascii=False, separators=(",", ":")),
                             qos=1, retain=False)

    # ------------------------------------------------------------------ resultados
    def tratar_resultado(self, msg: dict, recebido_em=None) -> None:
        obrigatorios = ("versao", "execucao_id", "lote_id", "registro_id", "no_id", "status")
        recebido_em = recebido_em or datetime.now(timezone.utc)
        with db.conexao() as conn:
            if any(k not in msg for k in obrigatorios) or msg.get("versao") != 1 \
                    or msg.get("status") not in ("processado", "erro"):
                db.evento(conn, "resultado_invalido", msg.get("execucao_id"), msg.get("lote_id"),
                          msg.get("no_id"), mensagem={k: msg.get(k) for k in obrigatorios})
                return
            reg = conn.execute(
                """SELECT o.id, o.lote_id, o.ultimo_envio_em, l.estado AS lote_estado
                   FROM registros_origem o JOIN lotes l ON l.id = o.lote_id
                   WHERE o.execucao_id=%s AND o.registro_id=%s""",
                (msg["execucao_id"], msg["registro_id"])).fetchone()
            if not reg:
                db.evento(conn, "resultado_desconhecido", None, msg["lote_id"], msg["no_id"],
                          registro_id=msg["registro_id"], execucao=msg["execucao_id"])
                return
            dados = msg.get("dados_tratados")
            if msg["status"] == "processado" and (not isinstance(dados, dict) or set(dados) != set(COLUNAS)):
                db.evento(conn, "resultado_campos_divergentes", msg["execucao_id"], reg["lote_id"], msg["no_id"],
                          registro_id=msg["registro_id"],
                          campos=sorted(dados) if isinstance(dados, dict) else None)
            inserido = conn.execute(
                """INSERT INTO registros_silver (execucao_id, registro_origem_id, lote_id, no_id, status,
                       dados_tratados, erros, versao_regras, duracao_no_us, mem_livre_no, simulado, enviado_em,
                       recebido_em)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (execucao_id, registro_origem_id) DO NOTHING RETURNING id""",
                (msg["execucao_id"], reg["id"], reg["lote_id"], msg["no_id"], msg["status"],
                 db.Jsonb(dados) if dados is not None else None, db.Jsonb(msg.get("erros") or []),
                 msg.get("versao_regras"), msg.get("duracao_us"), msg.get("mem_livre"),
                 bool(msg.get("simulado", False)), reg["ultimo_envio_em"], recebido_em)).fetchone()
            if not inserido:
                db.evento(conn, "resposta_duplicada", msg["execucao_id"], reg["lote_id"], msg["no_id"],
                          registro_id=msg["registro_id"])
            elif reg["lote_estado"] == "atribuido":
                conn.execute("UPDATE lotes SET estado='processando', primeiro_resultado_em=now() "
                             "WHERE id=%s AND estado='atribuido'", (reg["lote_id"],))
            conn.commit()

            pend = self.pendentes.get(reg["lote_id"])
            if pend and pend["registro_origem_id"] == reg["id"]:
                self._enviar_proximo(conn, reg["lote_id"])
            elif reg["lote_estado"] in ATIVOS:
                self._concluir_lote(conn, reg["lote_id"], somente_se_completo=True)

    def _concluir_lote(self, conn, lote_id: str, somente_se_completo: bool = False) -> None:
        r = conn.execute(
            """SELECT l.total, l.execucao_id, l.no_id, l.estado,
                      (SELECT count(*) FROM registros_silver s JOIN registros_origem o ON o.id = s.registro_origem_id
                       WHERE o.lote_id = l.id) AS feitos
               FROM lotes l WHERE l.id = %s""", (lote_id,)).fetchone()
        if r["feitos"] < r["total"]:
            if not somente_se_completo:
                log.warning("Lote %s sem registros pendentes mas incompleto (%s/%s)", lote_id, r["feitos"], r["total"])
            return
        self.pendentes.pop(lote_id, None)
        if r["estado"] != "concluido":
            conn.execute("UPDATE lotes SET estado='concluido', concluido_em=now() WHERE id=%s", (lote_id,))
            conn.execute("UPDATE nos SET lote_atual=NULL WHERE lote_atual=%s", (lote_id,))
            db.evento(conn, "lote_concluido", r["execucao_id"], lote_id, r["no_id"], registros=r["feitos"])
        self._verificar_execucao(conn, r["execucao_id"])
        conn.commit()

    def _verificar_execucao(self, conn, exec_id: str) -> None:
        r = conn.execute(
            """SELECT e.status, e.total_esperado,
                      (SELECT count(*) FROM registros_silver WHERE execucao_id = e.id) AS feitos,
                      (SELECT count(*) FROM lotes WHERE execucao_id = e.id
                         AND estado IN ('pendente','atribuido','processando')) AS abertos,
                      (SELECT count(*) FROM lotes WHERE execucao_id = e.id AND estado = 'falhou') AS falhos
               FROM execucoes e WHERE e.id = %s""", (exec_id,)).fetchone()
        if r["status"] != "em_andamento":
            return
        if r["feitos"] == r["total_esperado"]:
            conn.execute("UPDATE execucoes SET status='concluida', concluido_em=now() WHERE id=%s", (exec_id,))
            db.evento(conn, "execucao_concluida", exec_id, registros=r["feitos"])
        elif r["abertos"] == 0 and r["falhos"] > 0:
            conn.execute("UPDATE execucoes SET status='falhou', mensagem=%s WHERE id=%s",
                         (f"{r['falhos']} lote(s) falharam após {config.MAX_TENTATIVAS_LOTE} tentativas; "
                          f"{r['feitos']}/{r['total_esperado']} registros persistidos", exec_id))
            db.evento(conn, "execucao_falhou", exec_id, lotes_falhos=r["falhos"], registros=r["feitos"])

    # ------------------------------------------------------------------ falhas
    def _verificar_timeouts(self, conn) -> None:
        agora = time.monotonic()
        for lote_id, p in list(self.pendentes.items()):
            if agora - p["enviado"] < config.TIMEOUT_REGISTRO_S:
                continue
            if p["reenvios"] < config.MAX_REENVIOS and self.no_disponivel(p["no_id"]):
                lote = conn.execute("SELECT * FROM lotes WHERE id=%s", (lote_id,)).fetchone()
                if not lote or lote["estado"] not in ATIVOS:
                    self.pendentes.pop(lote_id, None)
                    continue
                p["reenvios"] += 1
                p["enviado"] = agora
                db.evento(conn, "reenvio", lote["execucao_id"], lote_id, p["no_id"],
                          registro_id=p["registro"]["registro_id"], reenvio=p["reenvios"])
                self._publicar_tarefa(conn, lote, p["registro"])
            else:
                self._expirar_lote(conn, lote_id, "timeout")

    def _verificar_nos_silenciosos(self, conn) -> None:
        agora = time.monotonic()
        for no_id, n in self.nos.items():
            if n["estado"] != "offline" and agora - n["visto"] > config.NO_OFFLINE_S:
                n["estado"] = "offline"
                conn.execute("UPDATE nos SET estado='offline' WHERE no_id=%s", (no_id,))
                db.evento(conn, "no_silencioso", no_id=no_id, segundos=round(agora - n["visto"], 1))
                self._liberar_lotes_do_no(conn, no_id, "no_silencioso")

    def _expirar_lote(self, conn, lote_id: str, motivo: str) -> None:
        """Encerra a tentativa atual: o lote volta a pendente (ou falha) para outro nó continuar."""
        self.pendentes.pop(lote_id, None)
        lote = conn.execute(
            """UPDATE lotes l SET estado = CASE WHEN l.tentativas >= %s THEN 'falhou' ELSE 'pendente' END,
                   no_id = NULL
               FROM (SELECT id, no_id AS no_anterior FROM lotes WHERE id = %s FOR UPDATE) antes
               WHERE l.id = antes.id AND l.estado = ANY(%s)
               RETURNING l.execucao_id, l.estado, l.tentativas, antes.no_anterior""",
            (config.MAX_TENTATIVAS_LOTE, lote_id, list(ATIVOS))).fetchone()
        if not lote:
            return
        conn.execute("UPDATE nos SET lote_atual=NULL WHERE lote_atual=%s", (lote_id,))
        if motivo == "timeout" and lote["no_anterior"] in self.nos:
            # Evita devolver lotes de imediato ao nó que não respondeu (pausa de um timeout).
            self.nos[lote["no_anterior"]]["bloqueado_ate"] = time.monotonic() + config.TIMEOUT_REGISTRO_S
        db.evento(conn, "tentativa_expirada", lote["execucao_id"], lote_id, lote["no_anterior"], motivo=motivo,
                  novo_estado=lote["estado"], tentativas=lote["tentativas"])
        if lote["estado"] == "falhou":
            self._verificar_execucao(conn, lote["execucao_id"])
        conn.commit()

    # ------------------------------------------------------------------ reinício
    def recuperar(self) -> None:
        """Restaura o estado a partir do PostgreSQL após reinício da API."""
        from . import execucoes
        with db.conexao() as conn:
            ativos = conn.execute("SELECT id FROM lotes WHERE estado = ANY(%s)", (list(ATIVOS),)).fetchall()
            for l in ativos:
                r = conn.execute(
                    """SELECT l.total, l.execucao_id, (SELECT count(*) FROM registros_silver s
                           JOIN registros_origem o ON o.id=s.registro_origem_id WHERE o.lote_id=l.id) AS feitos
                       FROM lotes l WHERE l.id=%s""", (l["id"],)).fetchone()
                novo = "concluido" if r["feitos"] >= r["total"] else "pendente"
                conn.execute("UPDATE lotes SET estado=%s, no_id=CASE WHEN %s='pendente' THEN NULL ELSE no_id END, "
                             "concluido_em=CASE WHEN %s='concluido' THEN now() ELSE NULL END WHERE id=%s",
                             (novo, novo, novo, l["id"]))
                db.evento(conn, "recuperacao_lote", r["execucao_id"], l["id"], novo_estado=novo, feitos=r["feitos"])
            conn.execute("UPDATE nos SET lote_atual=NULL, estado='desconhecido'")
            for ex in conn.execute("SELECT id FROM execucoes WHERE status='em_andamento'").fetchall():
                self._verificar_execucao(conn, ex["id"])
            preparando = [r["id"] for r in conn.execute("SELECT id FROM execucoes WHERE status='preparando'")]
        for exec_id in preparando:
            execucoes.iniciar_preparacao(exec_id)

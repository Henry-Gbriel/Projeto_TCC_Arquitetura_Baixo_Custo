"""Simulador de nó para TESTES de integração sem hardware — não é a solução final.

Executa o mesmo firmware/regras.py do ESP32 em CPython, fala o mesmo contrato MQTT v1 e
marca estado e resultados com "simulado": true, que ficam registrados no Silver. Use IDs
distintos dos nós físicos (ex.: sim-01) para não confundir as medições.

    python scripts/simulador_no.py --id sim-01
    python scripts/simulador_no.py --id sim-02 --cair-apos 3      # testa desconexão
    python scripts/simulador_no.py --id sim-03 --duplicar         # testa idempotência
"""
import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path

import paho.mqtt.client as mqtt

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "firmware"))
sys.path.insert(0, str(RAIZ / "api"))
import regras  # noqa: E402
from app import config  # noqa: E402  (lê .env)


class NoSimulado:
    def __init__(self, no_id, host, porta, atraso_s=0.0, cair_apos=None, duplicar=False, silenciar_apos=None,
                 prefixo="tcc"):
        self.no_id = no_id
        self.atraso_s = atraso_s
        self.cair_apos = cair_apos
        self.silenciar_apos = silenciar_apos
        self.duplicar = duplicar
        self.processados = 0
        self.caiu = False
        self.lote_atual = None
        self.encerrado = threading.Event()
        self.prefixo = prefixo
        self.topico_estado = f"{prefixo}/nos/{no_id}/estado"
        self.c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"no-{no_id}", clean_session=True)
        self.c.will_set(self.topico_estado, self._estado("offline"), qos=1, retain=True)
        self.c.on_connect = self._on_connect
        self.c.on_message = self._on_message
        self.host, self.porta = host, porta

    def _estado(self, estado):
        return json.dumps({"versao": 1, "no_id": self.no_id, "estado": estado, "lote_id": self.lote_atual,
                           "simulado": True, "processados": self.processados})

    def _on_connect(self, c, u, f, rc, p):
        c.subscribe(f"{self.prefixo}/nos/{self.no_id}/tarefa", qos=1)
        c.publish(self.topico_estado, self._estado("disponivel"), qos=1, retain=True)

    def _on_message(self, c, u, m):
        if self.silenciar_apos is not None and self.processados >= self.silenciar_apos:
            return  # recebe mas não responde: testa timeout/reenvio
        t = json.loads(m.payload)
        self.lote_atual = t["lote_id"]
        inicio = time.perf_counter_ns()
        tratados, erros = regras.tratar_registro(t["dados"], t.get("tipos") or {})
        if self.atraso_s:
            time.sleep(self.atraso_s)
        duracao_us = (time.perf_counter_ns() - inicio) // 1000
        resposta = json.dumps({
            "versao": 1, "execucao_id": t["execucao_id"], "lote_id": t["lote_id"],
            "registro_id": t["registro_id"], "no_id": self.no_id, "posicao": t["posicao"],
            "status": "processado", "dados_tratados": tratados, "erros": erros,
            "versao_regras": regras.VERSAO_REGRAS, "duracao_us": duracao_us, "mem_livre": None,
            "simulado": True,
        }, ensure_ascii=False)
        c.publish(f"{self.prefixo}/resultados", resposta, qos=1)
        if self.duplicar:
            c.publish(f"{self.prefixo}/resultados", resposta, qos=1)
        self.processados += 1
        if self.cair_apos is not None and self.processados >= self.cair_apos:
            threading.Thread(target=self._derrubar, daemon=True).start()

    def _derrubar(self):
        """Queda abrupta (sem DISCONNECT): o broker publica o LWT "offline"."""
        time.sleep(0.3)
        self.caiu = True
        self.c.loop_stop()
        sock = self.c.socket()
        if sock:
            sock.close()
        self.encerrado.set()

    def rodar(self, bloquear=True):
        self.c.connect(self.host, self.porta, keepalive=5)
        self.c.loop_start()

        def batimento():
            while not self.encerrado.wait(5):
                self.c.publish(self.topico_estado, self._estado("disponivel"), qos=1, retain=True)
        threading.Thread(target=batimento, daemon=True).start()
        if bloquear:
            try:
                self.encerrado.wait()
            except KeyboardInterrupt:
                pass
            self.parar()

    def parar(self):
        self.encerrado.set()
        if self.caiu:
            return
        try:
            self.c.publish(self.topico_estado, self._estado("offline"), qos=1, retain=True).wait_for_publish(2)
        except Exception:
            pass
        self.c.loop_stop()
        self.c.disconnect()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--id", required=True)
    p.add_argument("--host", default=config.MQTT_HOST)
    p.add_argument("--porta", type=int, default=config.MQTT_PORTA)
    p.add_argument("--atraso", type=float, default=0.0, help="segundos extras por registro")
    p.add_argument("--cair-apos", type=int, help="derruba a conexão após N registros")
    p.add_argument("--silenciar-apos", type=int, help="para de responder após N registros")
    p.add_argument("--prefixo", default=config.MQTT_PREFIXO)
    p.add_argument("--duplicar", action="store_true", help="publica cada resposta duas vezes")
    a = p.parse_args()
    if a.id.startswith("esp32-") and not os.environ.get("PERMITIR_ID_FISICO"):
        p.error("Use um ID de simulação (ex.: sim-01) para não se passar por um nó físico")
    NoSimulado(a.id, a.host, a.porta, a.atraso, a.cair_apos, a.duplicar, a.silenciar_apos, a.prefixo).rodar()


if __name__ == "__main__":
    main()

# Nó de processamento ESP32 (MicroPython): recebe um registro por mensagem MQTT, aplica
# regras.py, publica o resultado e mostra o progresso no OLED.
#
# Módulos: rede (Wi-Fi), umqtt.simple (MQTT), regras (tratamento), tela (OLED),
# telemetria (tempo de processamento e memória livre no próprio resultado/estado).
# O firmware nunca acessa o PostgreSQL nem lê XLSX.
import gc
import json
import time

import network
from umqtt.simple import MQTTClient

import config
import regras
from tela import Tela

# umqtt.simple usa len() para o tamanho do pacote: tópicos e mensagens vão como bytes
# UTF-8 (acentos em "Cartório", "RESIDÊNCIA" etc. teriam tamanho errado como str).
TOPICO_TAREFA = "{}/nos/{}/tarefa".format(config.PREFIXO, config.NO_ID).encode()
TOPICO_ESTADO = "{}/nos/{}/estado".format(config.PREFIXO, config.NO_ID).encode()
TOPICO_RESULTADOS = "{}/resultados".format(config.PREFIXO).encode()
MAX_FILA = 3

tela = Tela(config)
fila = []          # tarefas recebidas; o callback só enfileira (evita recursão no publish QoS 1)
lote_atual = None
processados = 0
wlan = network.WLAN(network.STA_IF)


def conectar_wifi():
    wlan.active(True)
    if wlan.isconnected():
        return
    tela.mqtt_ok = False
    tela.mostrar("wifi...")
    wlan.connect(config.WIFI_SSID, config.WIFI_SENHA)
    inicio = time.ticks_ms()
    while not wlan.isconnected():
        if time.ticks_diff(time.ticks_ms(), inicio) > 20000:
            raise OSError("timeout wifi")
        time.sleep_ms(250)
    print("Wi-Fi:", wlan.ifconfig()[0])


def estado_json(estado):
    return json.dumps({
        "versao": 1, "no_id": config.NO_ID, "estado": estado, "lote_id": lote_atual,
        "processados": processados, "mem_livre": gc.mem_free(), "simulado": False,
        "ip": wlan.ifconfig()[0] if wlan.isconnected() else None,
        "versao_regras": regras.VERSAO_REGRAS,
    }).encode()


def ao_receber(topico, mensagem):
    if len(fila) >= MAX_FILA:
        fila.pop(0)  # o orquestrador reenviará o que não for respondido
    fila.append(mensagem)


def conectar_mqtt():
    cliente = MQTTClient(config.NO_ID, config.MQTT_HOST, port=config.MQTT_PORTA,
                         user=config.MQTT_USUARIO, password=config.MQTT_SENHA, keepalive=30)
    cliente.set_callback(ao_receber)
    cliente.set_last_will(TOPICO_ESTADO, estado_json("offline"), retain=True, qos=1)
    tela.mostrar("conectando")
    cliente.connect(clean_session=True)
    cliente.subscribe(TOPICO_TAREFA, qos=1)
    cliente.publish(TOPICO_ESTADO, estado_json("disponivel"), retain=True, qos=1)
    tela.mqtt_ok = True
    tela.mostrar("disponivel")
    return cliente


def processar(cliente, mensagem):
    global lote_atual, processados
    tela.mostrar("recebendo")
    try:
        tarefa = json.loads(mensagem.decode())
    except (ValueError, UnicodeError):
        print("Tarefa invalida")
        return
    del mensagem
    if tarefa.get("lote_id") != lote_atual:
        lote_atual = tarefa.get("lote_id")
        tela.novo_lote(lote_atual, tarefa.get("total_lote", 0))
    tela.mostrar("processando")

    inicio = time.ticks_us()
    try:
        tratados, erros = regras.tratar_registro(tarefa["dados"], tarefa.get("tipos") or {})
        status = "processado"
    except Exception as e:  # erro inesperado: devolve como erro de processamento
        tratados, erros, status = None, [{"campo": None, "motivo": "excecao_no", "valor_original": str(e)}], "erro"
    duracao = time.ticks_diff(time.ticks_us(), inicio)
    gc.collect()

    resposta = json.dumps({
        "versao": 1, "execucao_id": tarefa["execucao_id"], "lote_id": tarefa["lote_id"],
        "registro_id": tarefa["registro_id"], "no_id": config.NO_ID, "posicao": tarefa.get("posicao"),
        "status": status, "dados_tratados": tratados, "erros": erros,
        "versao_regras": regras.VERSAO_REGRAS, "duracao_us": duracao, "mem_livre": gc.mem_free(),
        "simulado": False,
    }).encode()
    posicao = tarefa.get("posicao") or 0
    del tarefa, tratados
    tela.mostrar("publicando")
    cliente.publish(TOPICO_RESULTADOS, resposta, qos=1)
    del resposta
    gc.collect()

    processados += 1
    tela.pos = posicao  # posição informada pelo orquestrador (correta mesmo em reenvios)
    tela.erros += len(erros)
    tela.mostrar("disponivel")


def laco():
    cliente = None
    espera = 1
    ultimo_batimento = time.ticks_ms()
    while True:
        try:
            if cliente is None:
                conectar_wifi()
                cliente = conectar_mqtt()
                espera = 1
            cliente.check_msg()
            while fila:
                processar(cliente, fila.pop(0))
            if time.ticks_diff(time.ticks_ms(), ultimo_batimento) > config.BATIMENTO_S * 1000:
                cliente.publish(TOPICO_ESTADO, estado_json("disponivel"), retain=True, qos=1)
                ultimo_batimento = time.ticks_ms()
            time.sleep_ms(5)
        except OSError as e:
            print("Conexao perdida:", e)
            tela.mqtt_ok = False
            tela.mostrar("reconectando")
            try:
                if cliente:
                    cliente.sock.close()
            except Exception:
                pass
            cliente = None
            time.sleep(espera)
            espera = min(espera * 2, 30)
        except MemoryError:
            gc.collect()
            tela.mostrar("erro memoria")
            del fila[:]


tela.mostrar("iniciando")
laco()

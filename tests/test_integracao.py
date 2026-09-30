"""Integração orquestrador + PostgreSQL + Mosquitto com nós SIMULADOS (sem hardware).

Requer `docker compose up -d`. Usa um banco próprio (tcc_itbi_teste) e um prefixo MQTT
aleatório, sem interferir numa API em execução. Pulado se os serviços não responderem.
"""
import datetime as dt
import socket
import time
import uuid

import openpyxl
import psycopg
import pytest

from app import config

BANCO_TESTE = "tcc_itbi_teste"


def _servicos_disponiveis() -> bool:
    try:
        socket.create_connection((config.MQTT_HOST, config.MQTT_PORTA), timeout=1).close()
        psycopg.connect(config.PG_DSN, connect_timeout=2).close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _servicos_disponiveis(), reason="PostgreSQL/Mosquitto indisponíveis")

CABECALHO = ["N° do Cadastro (SQL)", "Nome do Logradouro", "Número", "Complemento", "Bairro", "Referência",
             "CEP", "Natureza de Transação", "Valor de Transação (declarado pelo contribuinte)",
             "Data de Transação", "Valor Venal de Referência", "Proporção Transmitida (%)",
             "Valor Venal de Referência (proporcional)", "Base de Cálculo adotada", "Tipo de Financiamento",
             "Valor Financiado", "Cartório de Registro", "Matrícula do Imóvel", "Situação do SQL",
             "Área do Terreno (m2)", "Testada (m)", "Fração Ideal", "Área Construída (m2)", "Uso (IPTU)",
             "Descrição do uso (IPTU)", "Padrão (IPTU)", "Descrição do padrão (IPTU)", "ACC (IPTU)"]


def _linha(i: int) -> list:
    return [12318300101 + i, "R TESTE", 71 + i, None, " JD MORUMBI ", None, 5662000 + i, "1.Compra e venda",
            400000 + i + 0.39, dt.datetime(2025, 8, 29), 0, 100, 0, 428832, None, 0, "18º Cartório",
            1000 + i, "Ativo Predial", 828, 0, 1, 329, 10, "RESIDÊNCIA", 13, "RESIDENCIAL HORIZONTAL ", 1977]


@pytest.fixture(scope="module")
def ambiente(tmp_path_factory):
    import simulador_no  # noqa: F401  (valida import antes de mexer no config)
    from app import bronze, db

    dsn_admin = config.PG_DSN
    with psycopg.connect(dsn_admin, autocommit=True) as c:
        c.execute(f"DROP DATABASE IF EXISTS {BANCO_TESTE} WITH (FORCE)")
        c.execute(f"CREATE DATABASE {BANCO_TESTE}")
    config.PG_DSN = dsn_admin.replace(f"dbname={config.PG_DSN.split('dbname=')[1].split()[0]}",
                                      f"dbname={BANCO_TESTE}")
    config.BRONZE_DIR = tmp_path_factory.mktemp("bronze")
    config.MQTT_PREFIXO = f"teste-{uuid.uuid4().hex[:8]}"
    config.MQTT_CLIENT_ID = f"orq-{config.MQTT_PREFIXO}"
    config.TIMEOUT_REGISTRO_S = 1.5
    config.MAX_REENVIOS = 1
    config.NO_OFFLINE_S = 20
    db.fechar()
    db.migrar()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "JAN-2026"
    ws.append(CABECALHO)
    for i in range(25):
        ws.append(_linha(i))
    caminho = tmp_path_factory.mktemp("xlsx") / "amostra.xlsx"
    wb.save(caminho)
    temp = bronze.salvar_stream(open(caminho, "rb"))
    arquivo, _ = bronze.registrar(temp, "amostra.xlsx", ano_fonte=2026)
    yield {"arquivo_id": arquivo["id"]}
    db.fechar()


@pytest.fixture
def orquestrador(ambiente):
    from app import execucoes
    from app.orquestrador import Orquestrador
    o = Orquestrador()
    execucoes.definir_notificacao(o.acordar)
    o.iniciar()
    yield o
    o.parar()


def _no(no_id, **kw):
    from simulador_no import NoSimulado
    n = NoSimulado(no_id, config.MQTT_HOST, config.MQTT_PORTA, prefixo=config.MQTT_PREFIXO, **kw)
    n.rodar(bloquear=False)
    return n


def _aguardar(exec_id, status=("concluida", "falhou"), timeout=40):
    from app import db
    fim = time.time() + timeout
    while time.time() < fim:
        with db.conexao() as conn:
            ex = conn.execute("SELECT * FROM execucoes WHERE id=%s", (exec_id,)).fetchone()
        if ex["status"] in status:
            return ex
        time.sleep(0.3)
    raise AssertionError(f"{exec_id} não terminou: {ex['status']}")


def _consulta(sql, *args):
    from app import db
    with db.conexao() as conn:
        return conn.execute(sql, args).fetchall()


def _nova(ambiente, limite, nos):
    from app import execucoes
    return execucoes.criar(ambiente["arquivo_id"], 2026, "JAN", limite, nos)["id"]


def test_tres_nos_distribuem_lotes(ambiente, orquestrador):
    nos = [_no(f"sim-{i}") for i in "abc"]
    try:
        exec_id = _nova(ambiente, None, ["sim-a", "sim-b", "sim-c"])
        ex = _aguardar(exec_id)
        assert ex["status"] == "concluida" and ex["total_esperado"] == 25
        silver = _consulta("SELECT no_id, dados_tratados FROM registros_silver WHERE execucao_id=%s", exec_id)
        assert len(silver) == 25
        assert len({s["no_id"] for s in silver}) >= 2
        assert all(s["dados_tratados"]["cep"].startswith("0566") for s in silver)
        assert all(s["dados_tratados"]["bairro"] == "JD MORUMBI" for s in silver)
        lotes = _consulta("SELECT total FROM lotes WHERE execucao_id=%s ORDER BY numero", exec_id)
        assert [l["total"] for l in lotes] == [10, 10, 5]
    finally:
        for n in nos:
            n.parar()


def test_resposta_duplicada_nao_duplica_silver(ambiente, orquestrador):
    n = _no("sim-dup", duplicar=True)
    try:
        exec_id = _nova(ambiente, 10, ["sim-dup"])
        assert _aguardar(exec_id)["status"] == "concluida"
        time.sleep(1)  # deixa chegar a última duplicata
        assert len(_consulta("SELECT 1 FROM registros_silver WHERE execucao_id=%s", exec_id)) == 10
        dup = _consulta("SELECT 1 FROM eventos_execucao WHERE execucao_id=%s AND tipo='resposta_duplicada'", exec_id)
        assert len(dup) >= 9
    finally:
        n.parar()


def test_queda_de_no_reatribui_lote(ambiente, orquestrador):
    a = _no("sim-cai", cair_apos=3)
    try:
        exec_id = _nova(ambiente, 10, ["sim-cai", "sim-ok"])
        time.sleep(0.5)
        b = _no("sim-ok")  # entra depois, para o primeiro lote ir ao nó que cai
        ex = _aguardar(exec_id)
        assert ex["status"] == "concluida"
        silver = _consulta("SELECT no_id FROM registros_silver WHERE execucao_id=%s", exec_id)
        assert len(silver) == 10
        por_no = {n: sum(1 for s in silver if s["no_id"] == n) for n in ("sim-cai", "sim-ok")}
        assert por_no["sim-cai"] >= 3 and por_no["sim-ok"] >= 1
        lote = _consulta("SELECT tentativas FROM lotes WHERE execucao_id=%s", exec_id)[0]
        assert lote["tentativas"] == 2
        assert _consulta("SELECT 1 FROM eventos_execucao WHERE execucao_id=%s AND tipo='tentativa_expirada' "
                         "AND detalhe->>'motivo'='desconexao'", exec_id)
    finally:
        a.parar()
        b.parar()


def test_timeout_reenvia_e_reatribui(ambiente, orquestrador):
    mudo = _no("sim-mudo", silenciar_apos=2)
    try:
        exec_id = _nova(ambiente, 10, ["sim-mudo", "sim-vivo"])
        time.sleep(0.5)
        vivo = _no("sim-vivo")
        ex = _aguardar(exec_id)
        assert ex["status"] == "concluida"
        tipos = {e["tipo"] for e in _consulta("SELECT tipo FROM eventos_execucao WHERE execucao_id=%s", exec_id)}
        assert {"reenvio", "tentativa_expirada"} <= tipos
        assert len(_consulta("SELECT 1 FROM registros_silver WHERE execucao_id=%s", exec_id)) == 10
    finally:
        mudo.parar()
        vivo.parar()


def test_reinicio_do_orquestrador_recupera(ambiente, orquestrador):
    from app import execucoes
    from app.orquestrador import Orquestrador
    lento = _no("sim-lento", atraso_s=0.3)
    try:
        exec_id = _nova(ambiente, 10, ["sim-lento"])
        time.sleep(2)
        orquestrador.parar()  # "queda" da API no meio do lote
        feitos = len(_consulta("SELECT 1 FROM registros_silver WHERE execucao_id=%s", exec_id))
        assert 0 < feitos < 10
        novo = Orquestrador()
        execucoes.definir_notificacao(novo.acordar)
        novo.iniciar()
        try:
            lento.c.publish(lento.topico_estado, lento._estado("disponivel"), qos=1, retain=True)
            assert _aguardar(exec_id)["status"] == "concluida"
            assert len(_consulta("SELECT 1 FROM registros_silver WHERE execucao_id=%s", exec_id)) == 10
            assert _consulta("SELECT 1 FROM eventos_execucao WHERE execucao_id=%s AND tipo='recuperacao_lote'",
                             exec_id)
        finally:
            novo.parar()
    finally:
        lento.parar()


def test_indicadores_e_metricas(ambiente, orquestrador):
    from app import gold
    n = _no("sim-gold")
    try:
        exec_id = _nova(ambiente, 10, ["sim-gold"])
        _aguardar(exec_id)
        ind = gold.indicadores(exec_id)
        assert ind["geral"]["registros"] == 10
        assert str(ind["geral"]["valor_min"]) == "400000.39"  # decimal exato, sem arredondamento binário
        met = gold.metricas(exec_id)
        assert met["por_no"][0]["registros"] == 10 and met["por_no"][0]["simulado"] is True
    finally:
        n.parar()

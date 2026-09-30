"""API v1 (seção 9). Executar com um único worker: o orquestrador vive neste processo.

    uvicorn app.main:app --app-dir api --port 8010
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator

from . import bronze, coleta, config, db, execucoes, gold
from .orquestrador import Orquestrador

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
orquestrador: Orquestrador | None = None
ESTATICO = Path(__file__).parent / "static"


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    global orquestrador
    db.migrar()
    bronze.reanalisar_abas_pendentes()
    if config.ORQUESTRADOR_ATIVO:
        orquestrador = Orquestrador()
        execucoes.definir_notificacao(orquestrador.acordar)
        orquestrador.iniciar()
    yield
    if orquestrador:
        orquestrador.parar()
    db.fechar()


app = FastAPI(title="TCC — Framework distribuído de baixo custo (ITBI-SP)", version="1.0",
              lifespan=ciclo_de_vida)


@app.get("/", include_in_schema=False)
def interface():
    return FileResponse(ESTATICO / "index.html")


# ---------------------------------------------------------------- Bronze e coleta
@app.post("/arquivos", status_code=201)
def enviar_arquivo(arquivo: UploadFile = File(...), ano_fonte: int | None = Form(None)):
    """Registra um XLSX enviado e o preserva sem alteração em data/bronze/."""
    temp = bronze.salvar_stream(arquivo.file)
    linha, novo = bronze.registrar(temp, arquivo.filename or "upload.xlsx", ano_fonte=ano_fonte)
    return {"novo": novo, "arquivo": bronze.resumo(linha)}


@app.get("/arquivos")
def listar_arquivos():
    with db.conexao() as conn:
        linhas = conn.execute("SELECT * FROM arquivos_bronze ORDER BY ano_fonte DESC NULLS LAST, coletado_em DESC")
        return [bronze.resumo(l) for l in linhas]


@app.get("/fontes/itbi-sp/anos")
def anos_disponiveis(atualizar: bool = False):
    """Anos descobertos na página oficial e versões já preservadas em Bronze."""
    try:
        anos = coleta.descobrir_anos(forcar=atualizar)
        erro_fonte = None
    except Exception as e:
        anos, erro_fonte = [], str(e)
    with db.conexao() as conn:
        arquivos = conn.execute("SELECT * FROM arquivos_bronze ORDER BY coletado_em DESC").fetchall()
    por_ano: dict[int, list] = {}
    for a in arquivos:
        por_ano.setdefault(a["ano_fonte"], []).append(bronze.resumo(a))
    todos = sorted({d["ano"] for d in anos} | {k for k in por_ano if k}, reverse=True)
    origem = {d["ano"]: d for d in anos}
    return {
        "fonte": config.FONTE_ITBI_SP_URL, "erro_fonte": erro_fonte,
        "anos": [{"ano": a, "url_excel": origem.get(a, {}).get("url"), "na_pagina": a in origem,
                  "versoes_bronze": por_ano.get(a, [])} for a in todos],
    }


class PedidoColeta(BaseModel):
    ano: int | None = None
    todos: bool = False

    @model_validator(mode="after")
    def _um_dos_dois(self):
        if (self.ano is None) == (not self.todos):
            raise ValueError("Informe 'ano' ou 'todos=true' (não ambos)")
        return self


@app.post("/coletas/itbi-sp", status_code=202)
def coletar(pedido: PedidoColeta):
    """Baixa o Excel de um ano (ou de todos) para Bronze. Não inicia processamento."""
    try:
        coleta_id = coleta.iniciar_coleta(None if pedido.todos else [pedido.ano])
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"coleta_id": coleta_id, "acompanhar": f"/coletas/{coleta_id}"}


@app.get("/coletas/{coleta_id}")
def estado_coleta(coleta_id: int):
    with db.conexao() as conn:
        c = conn.execute("SELECT * FROM coletas WHERE id=%s", (coleta_id,)).fetchone()
    if not c:
        raise HTTPException(404, "Coleta não encontrada")
    return c


# ---------------------------------------------------------------- execuções
class PedidoExecucao(BaseModel):
    arquivo_id: int
    ano: int
    mes: str | None = Field(None, description="JAN..DEZ; omitido = todos os meses do ano")
    limite_registros: int | None = Field(None, ge=1, description="Para testes; não altera o Bronze")
    nos: list[str] | None = Field(None, description="Subconjunto de nós (padrão: NOS_PADRAO)")


@app.post("/execucoes", status_code=202)
def criar_execucao(pedido: PedidoExecucao):
    """Cria a execução e retorna imediatamente; acompanhe em GET /execucoes/{id}."""
    try:
        ex = execucoes.criar(pedido.arquivo_id, pedido.ano, pedido.mes, pedido.limite_registros, pedido.nos)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"execucao_id": ex["id"], "status": ex["status"], "abas": ex["abas_selecionadas"],
            "acompanhar": f"/execucoes/{ex['id']}"}


@app.get("/execucoes")
def listar_execucoes(limite: int = Query(20, le=200)):
    with db.conexao() as conn:
        return conn.execute(
            """SELECT e.*, (SELECT count(*) FROM registros_silver s WHERE s.execucao_id=e.id) AS processados
               FROM execucoes e ORDER BY criado_em DESC LIMIT %s""", (limite,)).fetchall()


@app.get("/execucoes/{exec_id}")
def estado_execucao(exec_id: str, eventos: int = Query(30, le=500)):
    with db.conexao() as conn:
        ex = conn.execute("SELECT * FROM execucoes WHERE id=%s", (exec_id,)).fetchone()
        if not ex:
            raise HTTPException(404, "Execução não encontrada")
        contagem = conn.execute(
            """SELECT count(*) AS processados,
                      count(*) FILTER (WHERE jsonb_array_length(erros) > 0) AS com_erro,
                      count(*) FILTER (WHERE status='erro') AS erro_no_no
               FROM registros_silver WHERE execucao_id=%s""", (exec_id,)).fetchone()
        lotes = conn.execute(
            """SELECT l.id, l.numero, l.no_id, l.estado, l.total, l.tentativas, l.atribuido_em, l.concluido_em,
                      (SELECT count(*) FROM registros_silver s JOIN registros_origem o ON o.id=s.registro_origem_id
                       WHERE o.lote_id=l.id) AS feitos
               FROM lotes l WHERE l.execucao_id=%s ORDER BY l.numero LIMIT 500""", (exec_id,)).fetchall()
        resumo_lotes = conn.execute("SELECT estado, count(*) AS n FROM lotes WHERE execucao_id=%s GROUP BY estado",
                                    (exec_id,)).fetchall()
        ultimos = conn.execute(
            "SELECT tipo, lote_id, no_id, detalhe, criado_em FROM eventos_execucao WHERE execucao_id=%s "
            "ORDER BY id DESC LIMIT %s", (exec_id, eventos)).fetchall()
        erros_leitura = conn.execute(
            "SELECT count(*) AS n FROM eventos_execucao WHERE execucao_id=%s AND tipo='erro_leitura'",
            (exec_id,)).fetchone()["n"]
    total = ex["total_esperado"] or 0
    return {**ex, **contagem, "erros_leitura": erros_leitura,
            "progresso": round(contagem["processados"] / total, 4) if total else 0.0,
            "lotes_por_estado": {r["estado"]: r["n"] for r in resumo_lotes},
            "lotes": lotes, "eventos_recentes": ultimos}


@app.post("/execucoes/{exec_id}/retomar")
def retomar_execucao(exec_id: str):
    """Devolve lotes que falharam para pendente (novas tentativas) e reabre a execução."""
    with db.conexao() as conn:
        n = conn.execute("UPDATE lotes SET estado='pendente', tentativas=0 WHERE execucao_id=%s AND estado='falhou'",
                         (exec_id,)).rowcount
        conn.execute("UPDATE execucoes SET status='em_andamento', mensagem=NULL WHERE id=%s AND status='falhou' "
                     "AND total_esperado > 0", (exec_id,))
        db.evento(conn, "execucao_retomada", exec_id, lotes=n)
    if orquestrador:
        orquestrador.acordar()
    return {"lotes_reabertos": n}


@app.get("/execucoes/{exec_id}/registros")
def registros_silver(exec_id: str, pagina: int = Query(1, ge=1), por_pagina: int = Query(50, ge=1, le=500),
                     somente_erros: bool = False):
    """Resultados Silver paginados, lado a lado com o registro bruto de origem."""
    filtro = "AND jsonb_array_length(s.erros) > 0" if somente_erros else ""
    with db.conexao() as conn:
        total = conn.execute(f"SELECT count(*) AS n FROM registros_silver s WHERE s.execucao_id=%s {filtro}",
                             (exec_id,)).fetchone()["n"]
        itens = conn.execute(
            f"""SELECT o.registro_id, o.aba, o.linha, o.lote_id, o.posicao, s.no_id, s.simulado, s.status,
                       o.dados AS dados_origem, o.tipos, s.dados_tratados, s.erros, s.duracao_no_us,
                       s.mem_livre_no, s.recebido_em
                FROM registros_silver s JOIN registros_origem o ON o.id=s.registro_origem_id
                WHERE s.execucao_id=%s {filtro} ORDER BY o.lote_id, o.posicao LIMIT %s OFFSET %s""",
            (exec_id, por_pagina, (pagina - 1) * por_pagina)).fetchall()
    return {"total": total, "pagina": pagina, "por_pagina": por_pagina, "itens": itens}


@app.get("/execucoes/{exec_id}/indicadores")
def indicadores(exec_id: str):
    return gold.indicadores(exec_id)


@app.get("/execucoes/{exec_id}/metricas")
def metricas(exec_id: str):
    return gold.metricas(exec_id)


# ---------------------------------------------------------------- nós
@app.get("/nos")
def listar_nos():
    with db.conexao() as conn:
        linhas = conn.execute(
            "SELECT *, extract(epoch FROM now()-ultimo_contato) AS segundos_sem_contato FROM nos ORDER BY no_id"
        ).fetchall()
    conhecidos = {l["no_id"] for l in linhas}
    for no_id in config.NOS_PADRAO:
        if no_id not in conhecidos:
            linhas.append({"no_id": no_id, "estado": "nunca_conectado"})
    for l in linhas:
        l["disponivel"] = bool(orquestrador and orquestrador.no_disponivel(l["no_id"]))
    return {"broker_conectado": bool(orquestrador and orquestrador.conectado), "nos": linhas}

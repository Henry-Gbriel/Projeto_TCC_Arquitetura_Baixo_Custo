"""Criação e preparação de execuções: seleciona abas, lê registros e monta lotes.

A preparação grava os registros brutos (representação transportável, sem limpeza) em
registros_origem; o orquestrador lê do banco, o que permite recuperação após reinício.
"""
import threading
from pathlib import Path

from . import config, db
from .canonico import MESES
from .leitor import ErroLeitura, ler_registros

COMMIT_A_CADA_LOTES = 200
_notificar = None  # callback do orquestrador (definido em main)


def definir_notificacao(fn) -> None:
    global _notificar
    _notificar = fn


def selecionar_abas(arquivo: dict, ano: int, mes: str | None) -> list[str]:
    mensais = [a for a in arquivo["abas"] if a["ano"] == ano]
    if mes:
        mensais = [a for a in mensais if a["mes"] == mes]
    mensais.sort(key=lambda a: MESES.index(a["mes"]))
    return [a["aba"] for a in mensais]


def criar(arquivo_id: int, ano: int, mes: str | None, limite: int | None, nos: list[str] | None) -> dict:
    mes = mes.upper() if mes else None
    if mes and mes not in MESES:
        raise ValueError(f"Mês inválido: {mes}. Use {', '.join(MESES)}")
    if limite is not None and limite < 1:
        raise ValueError("limite_registros deve ser >= 1")
    nos = nos or config.NOS_PADRAO
    if not nos or len(set(nos)) != len(nos):
        raise ValueError("Lista de nós vazia ou com repetição")

    with db.conexao() as conn:
        arquivo = conn.execute("SELECT * FROM arquivos_bronze WHERE id = %s", (arquivo_id,)).fetchone()
        if not arquivo:
            raise LookupError(f"Arquivo {arquivo_id} não encontrado")
        if arquivo["formato"] != "xlsx":
            raise ValueError(f"Arquivo {arquivo_id} tem formato {arquivo['formato']}; o leitor aceita xlsx")
        abas = selecionar_abas(arquivo, ano, mes)
        if not abas:
            disponiveis = [a["aba"] for a in arquivo["abas"]]
            raise ValueError(f"Nenhuma aba mensal de {ano}{'/' + mes if mes else ''} no arquivo. "
                             f"Disponíveis: {disponiveis}")
        n = conn.execute("SELECT nextval('execucoes_seq') AS n").fetchone()["n"]
        exec_id = f"exec-{n:06d}"
        linha = conn.execute(
            """INSERT INTO execucoes (id, arquivo_id, ano, mes, limite_registros, abas_selecionadas, nos,
                   tamanho_lote, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'preparando') RETURNING *""",
            (exec_id, arquivo_id, ano, mes, limite, abas, nos, config.TAMANHO_LOTE)).fetchone()
        db.evento(conn, "execucao_criada", exec_id, abas=abas, nos=nos, limite=limite)
    iniciar_preparacao(exec_id)
    return linha


def iniciar_preparacao(exec_id: str) -> None:
    threading.Thread(target=preparar, args=(exec_id,), daemon=True, name=f"prep-{exec_id}").start()


def preparar(exec_id: str) -> None:
    try:
        with db.conexao() as conn:
            ex = conn.execute(
                "SELECT e.*, a.caminho FROM execucoes e JOIN arquivos_bronze a ON a.id = e.arquivo_id "
                "WHERE e.id = %s", (exec_id,)).fetchone()
            # Reinício no meio da preparação: nada foi distribuído ainda, então recomeçar é seguro.
            conn.execute("DELETE FROM lotes WHERE execucao_id = %s", (exec_id,))
            conn.commit()

            erros: list[ErroLeitura] = []
            total = 0
            numero_lote = 0
            buffer = []

            def gravar_lote():
                nonlocal numero_lote
                numero_lote += 1
                lote_id = f"{exec_id}-lote-{numero_lote:04d}"
                conn.execute("INSERT INTO lotes (id, execucao_id, numero, estado, total) "
                             "VALUES (%s,%s,%s,'pendente',%s)", (lote_id, exec_id, numero_lote, len(buffer)))
                with conn.cursor() as cur:
                    cur.executemany(
                        """INSERT INTO registros_origem (execucao_id, arquivo_id, aba, linha, registro_id,
                               lote_id, posicao, dados, tipos, extras) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        [(exec_id, ex["arquivo_id"], r.aba, r.linha,
                          f"arquivo-{ex['arquivo_id']:02d}:{r.aba}:{r.linha}", lote_id, pos,
                          db.Jsonb(r.dados), db.Jsonb(r.tipos), db.Jsonb(r.extras))
                         for pos, r in enumerate(buffer, start=1)])
                buffer.clear()
                if numero_lote % COMMIT_A_CADA_LOTES == 0:
                    conn.commit()

            for r in ler_registros(Path(ex["caminho"]), ex["abas_selecionadas"],
                                   limite=ex["limite_registros"], ao_erro=erros.append):
                buffer.append(r)
                total += 1
                if len(buffer) == ex["tamanho_lote"]:
                    gravar_lote()
            if buffer:
                gravar_lote()

            for e in erros:
                db.evento(conn, "erro_leitura", exec_id, aba=e.aba, linha=e.linha, erro=e.tipo, **e.detalhe)
            if total == 0:
                conn.execute("UPDATE execucoes SET status='falhou', total_esperado=0, "
                             "mensagem='Nenhum registro de dados nas abas selecionadas' WHERE id=%s", (exec_id,))
            else:
                conn.execute("UPDATE execucoes SET status='em_andamento', total_esperado=%s, iniciado_em=now() "
                             "WHERE id=%s", (total, exec_id))
            db.evento(conn, "preparacao_concluida", exec_id, registros=total, lotes=numero_lote,
                      erros_leitura=len(erros))
    except Exception as e:
        with db.conexao() as conn:
            conn.execute("UPDATE execucoes SET status='falhou', mensagem=%s WHERE id=%s",
                         (f"Falha na preparação: {e}", exec_id))
            db.evento(conn, "falha_preparacao", exec_id, mensagem=str(e))
        return
    if _notificar:
        _notificar()

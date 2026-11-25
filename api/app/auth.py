"""Login do painel de controle.

Usuários na tabela `usuarios`, senha com scrypt (hashlib, sem dependência nova) e sessão em cookie
HttpOnly assinado com HMAC-SHA256. As rotas que alteram dados ou expõem a operação exigem login;
a consulta pública e o status do cluster continuam abertos.
"""
import base64
import hashlib
import hmac
import json
import logging
import secrets
import threading
import time

from fastapi import HTTPException, Request

from . import config, db

log = logging.getLogger("auth")
COOKIE = "sessao"
_SEGREDO = (config.SESSAO_SEGREDO or secrets.token_hex(32)).encode()
_SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1}

# Proteção simples contra força bruta: até 5 falhas por usuário a cada 5 minutos.
MAX_FALHAS, JANELA_FALHAS_S = 5, 300
_falhas: dict[str, list[float]] = {}
_trava = threading.Lock()


def hash_senha(senha: str) -> str:
    sal = secrets.token_bytes(16)
    h = hashlib.scrypt(senha.encode(), salt=sal, **_SCRYPT)
    return f"scrypt${sal.hex()}${h.hex()}"


def conferir_senha(senha: str, armazenado: str) -> bool:
    try:
        _, sal, h = armazenado.split("$")
    except ValueError:
        return False
    calculado = hashlib.scrypt(senha.encode(), salt=bytes.fromhex(sal), **_SCRYPT)
    return hmac.compare_digest(calculado.hex(), h)


def _b64(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode()


def criar_token(usuario: str) -> str:
    corpo = _b64(json.dumps({"u": usuario, "exp": int(time.time() + config.SESSAO_HORAS * 3600)}).encode())
    assinatura = _b64(hmac.new(_SEGREDO, corpo.encode(), hashlib.sha256).digest())
    return f"{corpo}.{assinatura}"


def ler_token(token: str | None) -> str | None:
    """Usuário do token, ou None se a assinatura não confere ou a sessão expirou."""
    if not token or "." not in token:
        return None
    corpo, assinatura = token.rsplit(".", 1)
    esperado = _b64(hmac.new(_SEGREDO, corpo.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(esperado, assinatura):
        return None
    try:
        dados = json.loads(base64.urlsafe_b64decode(corpo + "=" * (-len(corpo) % 4)))
    except ValueError:
        return None
    return dados["u"] if dados.get("exp", 0) > time.time() else None


def bloqueado(usuario: str) -> bool:
    with _trava:
        recentes = [t for t in _falhas.get(usuario, []) if time.time() - t < JANELA_FALHAS_S]
        _falhas[usuario] = recentes
        return len(recentes) >= MAX_FALHAS


def autenticar(usuario: str, senha: str) -> dict | None:
    with db.conexao() as conn:
        u = conn.execute("SELECT * FROM usuarios WHERE usuario=%s AND ativo", (usuario,)).fetchone()
        if u and conferir_senha(senha, u["senha_hash"]):
            conn.execute("UPDATE usuarios SET ultimo_login=now() WHERE id=%s", (u["id"],))
            with _trava:
                _falhas.pop(usuario, None)
            return {"usuario": u["usuario"], "nome": u["nome"]}
    with _trava:
        _falhas.setdefault(usuario, []).append(time.time())
    return None


def exigir_login(request: Request) -> dict:
    """Dependência das rotas do painel: 401 sem sessão válida ou com usuário desativado."""
    usuario = ler_token(request.cookies.get(COOKIE))
    if usuario:
        with db.conexao() as conn:
            u = conn.execute("SELECT usuario, nome FROM usuarios WHERE usuario=%s AND ativo", (usuario,)).fetchone()
        if u:
            return u
    raise HTTPException(401, "Faça login para acessar o painel de controle")


def criar_usuario(usuario: str, senha: str, nome: str | None = None) -> None:
    """Cria o usuário ou troca a senha de um existente (e o reativa)."""
    with db.conexao() as conn:
        conn.execute(
            """INSERT INTO usuarios (usuario, nome, senha_hash) VALUES (%s, %s, %s)
               ON CONFLICT (usuario) DO UPDATE SET senha_hash=EXCLUDED.senha_hash,
                   nome=COALESCE(EXCLUDED.nome, usuarios.nome), ativo=true""",
            (usuario, nome, hash_senha(senha)))


def preparar() -> None:
    """Na inicialização: cria o primeiro usuário a partir do .env e avisa sobre o segredo."""
    if not config.SESSAO_SEGREDO:
        log.warning("SESSAO_SEGREDO não definido: sessões do painel caem quando a API reinicia")
    with db.conexao() as conn:
        existe = conn.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone()
    if existe:
        return
    if config.ADMIN_USUARIO and config.ADMIN_SENHA:
        criar_usuario(config.ADMIN_USUARIO, config.ADMIN_SENHA, "Administrador")
        log.info("Usuário inicial '%s' criado a partir do .env", config.ADMIN_USUARIO)
    else:
        log.warning("Nenhum usuário do painel: defina ADMIN_USUARIO/ADMIN_SENHA ou rode scripts/criar_usuario.py")

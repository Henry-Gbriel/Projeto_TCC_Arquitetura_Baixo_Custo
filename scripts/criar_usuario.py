"""Cria um usuário do painel de controle (ou troca a senha de um existente).

    .venv/bin/python scripts/criar_usuario.py admin --nome "Henry Gabriel"
"""
import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from app import auth, db  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("usuario")
    p.add_argument("--nome")
    args = p.parse_args()
    senha = getpass.getpass("Senha: ")
    if len(senha) < 8:
        sys.exit("A senha precisa de pelo menos 8 caracteres.")
    if senha != getpass.getpass("Repita a senha: "):
        sys.exit("As senhas não conferem.")
    db.migrar()
    auth.criar_usuario(args.usuario, senha, args.nome)
    db.fechar()
    print(f"Usuário '{args.usuario}' pronto.")


if __name__ == "__main__":
    main()

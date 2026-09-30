"""Executa as fixtures das regras no MicroPython real (port Unix via Docker), se disponível."""
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
IMAGEM = "micropython/unix:latest"


def _imagem_disponivel() -> bool:
    if not shutil.which("docker"):
        return False
    r = subprocess.run(["docker", "image", "inspect", IMAGEM], capture_output=True)
    return r.returncode == 0


@pytest.mark.skipif(not _imagem_disponivel(), reason=f"docker/{IMAGEM} indisponível")
def test_regras_no_micropython():
    r = subprocess.run(["docker", "run", "--rm", "-v", f"{RAIZ}:/w", "-w", "/w", IMAGEM,
                        "tests/micropython_regras.py"], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "falhas: 0" in r.stdout

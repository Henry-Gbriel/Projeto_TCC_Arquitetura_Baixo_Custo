import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "api"))
sys.path.insert(0, str(RAIZ / "firmware"))
sys.path.insert(0, str(RAIZ / "scripts"))

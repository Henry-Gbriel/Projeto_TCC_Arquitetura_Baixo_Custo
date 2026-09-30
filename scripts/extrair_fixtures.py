"""Extrai amostras pequenas das planilhas reais para tests/fixtures (etapa 1 da especificação).

Uso:
    python scripts/extrair_fixtures.py --dir ~/Downloads

Gera, para cada amostra, os valores brutos serializados (como irão no MQTT), os tipos de
célula, erros de leitura e a saída das regras do ESP32. A saída esperada deve ser revisada
manualmente antes de ser congelada; a revisão é o que dá valor ao fixture.
"""
import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "api"))
sys.path.insert(0, str(RAIZ / "firmware"))

from app.leitor import ler_registros  # noqa: E402
import regras  # noqa: E402

AMOSTRAS = [
    ("jan2026_10", "GUIAS DE ITBI PAGAS (27082026) XLS.xlsx", "JAN-2026", 10),
    ("fev2026_cabecalho_pardao", "GUIAS DE ITBI PAGAS (27082026) XLS.xlsx", "FEV-2026", 3),
    ("jan2025_3", "GUIAS DE ITBI PAGAS (28012026) XLS.xlsx", "JAN-2025", 3),
    ("jan2019_acc_duplicado", "GUIAS_DE_ITBI_PAGAS_(2019) (1).xlsx", "JAN-2019", 3),
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dir", default=str(Path.home() / "Downloads"))
    p.add_argument("--saida", default=str(RAIZ / "tests" / "fixtures"))
    args = p.parse_args()
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)

    for nome, arquivo, aba, limite in AMOSTRAS:
        caminho = Path(args.dir) / arquivo
        if not caminho.exists():
            print(f"[pular] {caminho} não encontrado")
            continue
        erros_leitura = []
        registros = []
        for r in ler_registros(caminho, [aba], limite=limite,
                               ao_erro=lambda e: erros_leitura.append(e.__dict__)):
            tratados, erros = regras.tratar_registro(r.dados, r.tipos)
            registros.append({
                "aba": r.aba, "linha": r.linha, "dados": r.dados, "tipos": r.tipos,
                "extras": r.extras, "esperado": {"dados_tratados": tratados, "erros": erros},
            })
        doc = {"arquivo": arquivo, "aba": aba, "erros_leitura": erros_leitura, "registros": registros}
        destino = saida / f"{nome}.json"
        destino.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[ok] {destino.name}: {len(registros)} registros, {len(erros_leitura)} erros de leitura")


if __name__ == "__main__":
    main()

# Roda no MicroPython (port Unix) para provar que regras.py funciona fora do CPython:
#   docker run --rm -v "$PWD":/w -w /w micropython/unix tests/micropython_regras.py
import sys
sys.path.insert(0, "firmware")
import json
import regras

FIXTURES = ("jan2026_10", "fev2026_cabecalho_pardao", "jan2025_3", "jan2019_acc_duplicado")
ok = falhas = 0
for nome in FIXTURES:
    with open("tests/fixtures/" + nome + ".json") as f:
        doc = json.loads(f.read())
    for r in doc["registros"]:
        tratados, erros = regras.tratar_registro(r["dados"], r["tipos"])
        if tratados == r["esperado"]["dados_tratados"] and erros == r["esperado"]["erros"]:
            ok += 1
        else:
            falhas += 1
            print("DIVERGENTE", nome, r["linha"])
casos = [
    (regras.numero_decimal("R$ 605.994,39"), "605994.39"),
    (regras.cep("5662000", "n"), "05662000"),
    (regras.data("29/08/2025", "s"), "2025-08-29"),
    (regras.inteiro("1977.0"), 1977),
]
for obtido, esperado in casos:
    if obtido == esperado:
        ok += 1
    else:
        falhas += 1
        print("DIVERGENTE", obtido, esperado)
try:
    regras.cep("5662000", "s")
    falhas += 1
except regras.ErroCampo as e:
    ok += 1 if e.motivo == "cep_texto_incompleto" else 0
print(sys.implementation.name, "ok:", ok, "falhas:", falhas)
sys.exit(1 if falhas else 0)

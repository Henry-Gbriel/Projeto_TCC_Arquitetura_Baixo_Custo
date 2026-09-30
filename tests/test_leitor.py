import datetime as dt
import json
from pathlib import Path

import openpyxl
import pytest

import regras
from app.canonico import COLUNAS
from app.leitor import listar_abas, ler_registros, serializar_celula

FIXTURES = Path(__file__).parent / "fixtures"
CABECALHO_2026 = [
    "N° do Cadastro (SQL)", "Nome do Logradouro", "Número", "Complemento", "Bairro", "Referência",
    "CEP", "Natureza de Transação", "Valor de Transação (declarado pelo contribuinte)",
    "Data de Transação", "Valor Venal de Referência", "Proporção Transmitida (%)",
    "Valor Venal de Referência (proporcional)", "Base de Cálculo adotada", "Tipo de Financiamento",
    "Valor Financiado", "Cartório de Registro", "Matrícula do Imóvel", "Situação do SQL",
    "Área do Terreno (m2)", "Testada (m)", "Fração Ideal", "Área Construída (m2)", "Uso (IPTU)",
    "Descrição do uso (IPTU)", "Padrão (IPTU)", "Descrição do padrão (IPTU)", "ACC (IPTU)",
]
LINHA = [12318300101, "R SEN OTAVIO MANGABEIRA", 71, None, " JD MORUMBI ", None, 5662000,
         "4.Arrematação", 605994.39, dt.datetime(2025, 8, 29), 0, 100, 0, 428832, None, 0,
         "18º Cartório", 1000, "Ativo Predial", 828, 0, 1, 329, 10, "RESIDÊNCIA", 13,
         "RESIDENCIAL HORIZONTAL ", 1977]


def _xlsx(tmp_path, abas: dict[str, list[list]]) -> Path:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for nome, linhas in abas.items():
        ws = wb.create_sheet(nome)
        for linha in linhas:
            ws.append(linha)
    caminho = tmp_path / "teste.xlsx"
    wb.save(caminho)
    return caminho


def test_serializacao_nao_altera_significado():
    assert serializar_celula(5662000) == ("5662000", "n")
    assert serializar_celula(605994.39) == ("605994.39", "n")
    assert serializar_celula(1e-05) == ("0.00001", "n")
    assert serializar_celula(12318300101) == ("12318300101", "n")
    assert serializar_celula(dt.datetime(2025, 8, 29)) == ("2025-08-29", "d")
    assert serializar_celula(" JD ") == (" JD ", "s")  # sem strip: limpeza é do ESP32
    assert serializar_celula(None) == (None, None)


def test_leitura_basica_e_abas(tmp_path):
    caminho = _xlsx(tmp_path, {
        "JAN-2026": [CABECALHO_2026, LINHA, [None] * 28, LINHA],
        "LEGENDA": [["x"]],
        "FEV-2026": [CABECALHO_2026, LINHA],
    })
    assert [a["aba"] for a in listar_abas(caminho)] == ["JAN-2026", "FEV-2026"]
    erros = []
    regs = list(ler_registros(caminho, ["JAN-2026"], ao_erro=erros.append))
    assert [r.linha for r in regs] == [2, 4]  # linha vazia ignorada, numeração real mantida
    assert erros == []
    r = regs[0]
    assert list(r.dados) == COLUNAS
    assert r.dados["bairro"] == " JD MORUMBI "
    assert r.dados["cep"] == "5662000" and r.tipos["cep"] == "n"
    assert r.dados["valor_transacao"] == "605994.39"


def test_limite_registros(tmp_path):
    caminho = _xlsx(tmp_path, {"JAN-2026": [CABECALHO_2026] + [LINHA] * 5,
                               "FEV-2026": [CABECALHO_2026] + [LINHA] * 5})
    regs = list(ler_registros(caminho, ["JAN-2026", "FEV-2026"], limite=7))
    assert len(regs) == 7
    assert regs[-1].aba == "FEV-2026" and regs[-1].linha == 3


def test_acc_duplicado_2019(tmp_path):
    cab = CABECALHO_2026[:26] + ["ACC (IPTU)", "ACC (IPTU)"]
    caminho = _xlsx(tmp_path, {"JAN-2019": [cab, LINHA]})
    erros = []
    r = next(ler_registros(caminho, ["JAN-2019"], ao_erro=erros.append))
    assert r.dados["descricao_padrao"] == "RESIDENCIAL HORIZONTAL "
    assert r.dados["acc_iptu"] == "1977"
    assert erros == []


def test_grafia_pardao_e_coluna_29(tmp_path):
    cab = CABECALHO_2026[:26] + ["Descrição do pardão (IPTU)", "ACC (IPTU)", None]
    caminho = _xlsx(tmp_path, {"FEV-2026": [cab, LINHA + [None], LINHA + ["sobra"]]})
    erros = []
    regs = list(ler_registros(caminho, ["FEV-2026"], ao_erro=erros.append))
    assert regs[0].dados["descricao_padrao"] == "RESIDENCIAL HORIZONTAL "
    assert regs[0].extras == {}
    assert regs[1].extras == {"coluna_29": "sobra"}
    assert [e.tipo for e in erros] == ["valor_em_coluna_fora_do_esquema"]
    assert erros[0].linha == 3


def test_coluna_desconhecida_e_conflito(tmp_path):
    cab = CABECALHO_2026 + ["Coluna Nova", "CEP"]
    caminho = _xlsx(tmp_path, {"JAN-2026": [cab, LINHA + ["v", "99999999"]]})
    erros = []
    r = next(ler_registros(caminho, ["JAN-2026"], ao_erro=erros.append))
    tipos = [e.tipo for e in erros]
    assert "coluna_desconhecida" in tipos and "conflito_cabecalho" in tipos
    assert r.dados["cep"] == "5662000"  # primeira ocorrência mantida
    assert r.extras == {"Coluna Nova": "v", "CEP": "99999999"}


@pytest.mark.parametrize("nome", ["jan2026_10", "fev2026_cabecalho_pardao", "jan2025_3",
                                  "jan2019_acc_duplicado"])
def test_fixtures_reais_regras(nome):
    """Saídas esperadas revisadas manualmente a partir das planilhas reais."""
    caminho = FIXTURES / f"{nome}.json"
    if not caminho.exists():
        pytest.skip("fixture ausente; rode scripts/extrair_fixtures.py")
    doc = json.loads(caminho.read_text(encoding="utf-8"))
    for r in doc["registros"]:
        assert len(r["dados"]) == 28
        tratados, erros = regras.tratar_registro(r["dados"], r["tipos"])
        assert {"dados_tratados": tratados, "erros": erros} == r["esperado"], r["linha"]

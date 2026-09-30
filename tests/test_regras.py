"""Casos de teste que fixam a política das regras do ESP32 (firmware/regras.py)."""
import pytest

import regras


@pytest.mark.parametrize("entrada,esperado", [
    ("605994.39", "605994.39"),
    ("R$ 605.994,39", "605994.39"),
    ("R$605994,39", "605994.39"),
    ("428832", "428832"),
    ("0", "0"),
    ("0.0227", "0.0227"),
    ("100.50", "100.5"),
    ("  1.234,00 ", "1234"),
    ("-0", "0"),
    ("28383.1616", "28383.1616"),
    (None, None),
    ("", None),
    ("-", None),
    ("nan", None),
])
def test_numero_decimal(entrada, esperado):
    assert regras.numero_decimal(entrada) == esperado


@pytest.mark.parametrize("entrada", ["abc", "1.234.567", "1e5", "12,3,4", "R$"])
def test_numero_decimal_invalido(entrada):
    if entrada == "R$":
        assert regras.numero_decimal(entrada) is None  # só símbolo = ausente
        return
    with pytest.raises(regras.ErroCampo):
        regras.numero_decimal(entrada)


def test_cep_numerico_recupera_zero():
    assert regras.cep("5662000", "n") == "05662000"
    assert regras.cep("5662000.0", "n") == "05662000"
    assert regras.cep("13185010", "n") == "13185010"


def test_cep_texto():
    assert regras.cep("05662-000", "s") == "05662000"
    assert regras.cep(" 05662000 ", "s") == "05662000"
    assert regras.cep("   ", "s") is None


@pytest.mark.parametrize("valor,tipo,motivo", [
    ("5662000", "s", "cep_texto_incompleto"),
    ("123456789", "n", "cep_mais_de_8_digitos"),
    ("123456789", "s", "cep_mais_de_8_digitos"),
    ("0566A000", "s", "cep_caractere_inesperado"),
    ("0", "n", "cep_zero"),
])
def test_cep_invalido(valor, tipo, motivo):
    with pytest.raises(regras.ErroCampo) as e:
        regras.cep(valor, tipo)
    assert e.value.motivo == motivo


def test_numero_logradouro():
    assert regras.numero_logradouro("71") == "71"
    assert regras.numero_logradouro("71.0") == "71"
    assert regras.numero_logradouro("10.05") == "10.05"
    assert regras.numero_logradouro(" S/N ") == "S/N"


@pytest.mark.parametrize("valor,tipo,esperado", [
    ("2025-08-29", "d", "2025-08-29"),
    ("2025-08-29T10:30:00", "d", "2025-08-29"),
    ("29/08/2025", "s", "2025-08-29"),
    ("2024-02-29", "s", "2024-02-29"),
    (None, None, None),
])
def test_data(valor, tipo, esperado):
    assert regras.data(valor, tipo) == esperado


@pytest.mark.parametrize("valor,tipo,motivo", [
    ("2025-02-30", "s", "data_inexistente"),
    ("2023-02-29", "s", "data_inexistente"),
    ("45000", "n", "data_numerica_nao_suportada"),
    ("ago/2025", "s", "formato_data_invalido"),
])
def test_data_invalida(valor, tipo, motivo):
    with pytest.raises(regras.ErroCampo) as e:
        regras.data(valor, tipo)
    assert e.value.motivo == motivo


def test_inteiro():
    assert regras.inteiro("1977") == 1977
    assert regras.inteiro("1977.0") == 1977
    assert regras.inteiro(None) is None
    with pytest.raises(regras.ErroCampo):
        regras.inteiro("19.5")
    with pytest.raises(regras.ErroCampo):
        regras.inteiro("abc")


def test_tratar_registro_mantem_campos_e_sinaliza_erros():
    dados = {
        "id": "12318300101", "cep": "5662000", "bairro": "JD MORUMBI ",
        "complemento": None, "valor_transacao": "abc", "data_transacao": "2025-08-29",
        "acc_iptu": "1977", "campo_extra": " x ",
    }
    tipos = {"id": "n", "cep": "n", "bairro": "s", "valor_transacao": "s",
             "data_transacao": "d", "acc_iptu": "n"}
    tratados, erros = regras.tratar_registro(dados, tipos)
    assert tratados == {
        "id": "12318300101", "cep": "05662000", "bairro": "JD MORUMBI",
        "complemento": None, "valor_transacao": None, "data_transacao": "2025-08-29",
        "acc_iptu": 1977, "campo_extra": " x ",
    }
    assert erros == [{"campo": "valor_transacao", "motivo": "formato_numerico_invalido",
                      "valor_original": "abc"}]

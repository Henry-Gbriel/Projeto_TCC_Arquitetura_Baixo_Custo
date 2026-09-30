"""Nomes canônicos das colunas de ITBI-SP (derivados de schema_sp em ExtractionRawSP.py).

Este módulo trata apenas de ESTRUTURA (nomes de colunas). Nenhuma regra de limpeza de
valores fica aqui: essas regras executam nos ESP32 (firmware/regras.py).
"""
import re

COLUNAS = [
    "id", "logradouro", "numero", "complemento", "bairro", "referencia", "cep",
    "transacao", "valor_transacao", "data_transacao", "valor_venal_referencia",
    "proporcao_transmitida", "venal_referencia_proporcional", "base_calculo",
    "tipo_financiamento", "valor_financiado", "cartorio_registro", "matricula",
    "situacao", "area_terreno", "testada", "fracao_ideal", "area_construida",
    "uso_iptu", "descricao_uso", "padrao_iptu", "descricao_padrao", "acc_iptu",
]

CABECALHOS = {
    "n° do cadastro (sql)": "id",
    "nº do cadastro (sql)": "id",
    "nome do logradouro": "logradouro",
    "número": "numero",
    "complemento": "complemento",
    "bairro": "bairro",
    "referência": "referencia",
    "cep": "cep",
    "natureza de transação": "transacao",
    "valor de transação (declarado pelo contribuinte)": "valor_transacao",
    "data de transação": "data_transacao",
    "valor venal de referência": "valor_venal_referencia",
    "proporção transmitida (%)": "proporcao_transmitida",
    "valor venal de referência (proporcional)": "venal_referencia_proporcional",
    "base de cálculo adotada": "base_calculo",
    "tipo de financiamento": "tipo_financiamento",
    "valor financiado": "valor_financiado",
    "cartório de registro": "cartorio_registro",
    "matrícula do imóvel": "matricula",
    "situação do sql": "situacao",
    "área do terreno (m2)": "area_terreno",
    "testada (m)": "testada",
    "fração ideal": "fracao_ideal",
    "área construída (m2)": "area_construida",
    "uso (iptu)": "uso_iptu",
    "descrição do uso (iptu)": "descricao_uso",
    "descrição (iptu)": "descricao_uso",
    "padrão (iptu)": "padrao_iptu",
    "descrição do padrão (iptu)": "descricao_padrao",
    "descricao do padrao (iptu)": "descricao_padrao",
    "descrição padrão (iptu)": "descricao_padrao",
    "descricao padrao (iptu)": "descricao_padrao",
    "descrição do pardão (iptu)": "descricao_padrao",  # grafia de FEV-2026
    "acc (iptu)": "acc_iptu",
    "acc(iptu)": "acc_iptu",
    "acc iptu": "acc_iptu",
}

MESES = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]
_RE_ABA_MENSAL = re.compile(r"^(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)-(\d{4})$")


def normalizar_cabecalho(valor) -> str:
    if valor is None:
        return ""
    return re.sub(r"\s+", " ", str(valor)).strip().lower()


def aba_mensal(nome: str) -> tuple[str, int] | None:
    """'JAN-2026' -> ('JAN', 2026); abas como LEGENDA retornam None."""
    m = _RE_ABA_MENSAL.match(nome.strip().upper())
    return (m.group(1), int(m.group(2))) if m else None

# Regras de tratamento dos registros de ITBI-SP, executadas no ESP32 (MicroPython).
#
# Derivadas de clean_sp() em codigo_inicial/ITBI/SP/ExtractionRawSP.py, reimplementadas
# sem pandas. O arquivo roda igual em CPython (testes em tests/test_regras.py) e em
# MicroPython: evitar re, zfill, datetime, f-strings complexas e bibliotecas externas.
#
# Diferenças documentadas em relação a clean_sp():
#  1. numero: remove ".0" apenas no FINAL (clean_sp removia qualquer ocorrência de ".0").
#  2. cep: zero à esquerda só é completado quando a célula de origem era numérica
#     (tipo "n"). CEP textual com tamanho diferente de 8, com mais de 8 dígitos ou com
#     caracteres fora de dígitos/"-"/"."/espaço vira null com erro (clean_sp removia
#     qualquer não dígito e completava com zeros).
#  3. números: o resultado é texto decimal canônico (sem float), para evitar
#     arredondamento binário; notação científica em texto é rejeitada com erro.
#  4. data_transacao: aceita ISO (AAAA-MM-DD) e DD/MM/AAAA (dia primeiro, padrão BR);
#     pandas assumia mês primeiro em textos ambíguos. Número em célula de data vira erro.
#  5. acc_iptu: aceita inteiro ou inteiro com parte decimal zero ("1977.0"); fração
#     diferente de zero vira erro (pd.to_numeric + Int64 falharia ou truncaria).
#  6. Toda conversão que falha gera null + erro {campo, motivo, valor_original}.

VERSAO_REGRAS = "1"

COLS_DOUBLE = (
    "valor_transacao", "valor_venal_referencia", "venal_referencia_proporcional",
    "base_calculo", "valor_financiado", "area_terreno", "area_construida",
    "proporcao_transmitida", "testada", "fracao_ideal",
)

COLS_STR = (
    "id", "logradouro", "numero", "complemento", "bairro", "referencia", "cep",
    "transacao", "tipo_financiamento", "cartorio_registro", "matricula", "situacao",
    "uso_iptu", "descricao_uso", "padrao_iptu", "descricao_padrao",
)

VAZIOS_TEXTO = ("", "nan", "None")
VAZIOS_NUMERO = ("", "nan", "None", "-")
DIGITOS = "0123456789"


class ErroCampo(Exception):
    def __init__(self, motivo):
        super().__init__(motivo)  # Exception.__init__ não existe no MicroPython
        self.motivo = motivo


def _so_digitos(s):
    if not s:
        return False
    for ch in s:
        if ch not in DIGITOS:
            return False
    return True


def _zeros_esquerda(s, tamanho):
    while len(s) < tamanho:
        s = "0" + s
    return s


def texto(valor):
    """strip + vazios textuais -> None (COLS_STR em clean_sp)."""
    if valor is None:
        return None
    v = str(valor).strip()
    if v in VAZIOS_TEXTO:
        return None
    return v


def decimal_canonico(s):
    """'00605994.390' -> '605994.39'; levanta ErroCampo se não for decimal simples."""
    sinal = ""
    if s[:1] in ("+", "-"):
        sinal = "-" if s[0] == "-" else ""
        s = s[1:]
    partes = s.split(".")
    if len(partes) > 2:
        raise ErroCampo("formato_numerico_invalido")
    inteiro = partes[0]
    frac = partes[1] if len(partes) == 2 else ""
    if inteiro == "" and frac == "":
        raise ErroCampo("formato_numerico_invalido")
    if (inteiro and not _so_digitos(inteiro)) or (frac and not _so_digitos(frac)):
        raise ErroCampo("formato_numerico_invalido")
    inteiro = inteiro.lstrip("0") or "0"
    frac = frac.rstrip("0")
    r = inteiro + ("." + frac if frac else "")
    if r == "0":
        sinal = ""
    return sinal + r


def numero_decimal(valor):
    """parse_number() de clean_sp, com saída em texto decimal canônico."""
    if valor is None:
        return None
    v = str(valor).strip()
    if v in VAZIOS_NUMERO:
        return None
    v = v.replace("R$", "").strip()
    if "," in v:
        v = v.replace(".", "").replace(",", ".")
    v = v.replace(" ", "")
    if v == "":
        return None
    return decimal_canonico(v)


def numero_logradouro(valor):
    v = texto(valor)
    if v is not None and v.endswith(".0"):
        v = v[:-2]
    return v


def cep(valor, tipo):
    v = texto(valor)
    if v is None:
        return None
    if tipo == "n":
        if v.endswith(".0"):
            v = v[:-2]
        if not _so_digitos(v):
            raise ErroCampo("cep_numerico_invalido")
        if len(v) > 8:
            raise ErroCampo("cep_mais_de_8_digitos")
        if v.strip("0") == "":
            raise ErroCampo("cep_zero")
        # A célula era número no Excel: o zero inicial se perdeu na representação.
        return _zeros_esquerda(v, 8)
    limpo = ""
    for ch in v:
        if ch in DIGITOS:
            limpo += ch
        elif ch in "-. ":
            continue
        else:
            raise ErroCampo("cep_caractere_inesperado")
    if len(limpo) > 8:
        raise ErroCampo("cep_mais_de_8_digitos")
    if len(limpo) < 8:
        raise ErroCampo("cep_texto_incompleto")
    return limpo


def _bissexto(a):
    return (a % 4 == 0 and a % 100 != 0) or a % 400 == 0


def _data_valida(a, m, d):
    if a < 1900 or a > 2100 or m < 1 or m > 12 or d < 1:
        return False
    dias = (31, 29 if _bissexto(a) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    return d <= dias[m - 1]


def data(valor, tipo):
    v = texto(valor)
    if v is None:
        return None
    if tipo == "n":
        raise ErroCampo("data_numerica_nao_suportada")
    base = v.split("T")[0].split(" ")[0]
    if len(base) == 10 and base[4] == "-" and base[7] == "-":
        a, m, d = base[0:4], base[5:7], base[8:10]
    elif len(base) == 10 and base[2] == "/" and base[5] == "/":
        d, m, a = base[0:2], base[3:5], base[6:10]
    else:
        raise ErroCampo("formato_data_invalido")
    if not (_so_digitos(a) and _so_digitos(m) and _so_digitos(d)):
        raise ErroCampo("formato_data_invalido")
    if not _data_valida(int(a), int(m), int(d)):
        raise ErroCampo("data_inexistente")
    return a + "-" + m + "-" + d


def inteiro(valor):
    v = texto(valor)
    if v is None:
        return None
    sinal = 1
    if v[:1] in ("+", "-"):
        sinal = -1 if v[0] == "-" else 1
        v = v[1:]
    partes = v.split(".")
    if len(partes) > 2 or not _so_digitos(partes[0]):
        raise ErroCampo("inteiro_invalido")
    if len(partes) == 2 and partes[1] and (not _so_digitos(partes[1]) or partes[1].strip("0") != ""):
        raise ErroCampo("inteiro_com_fracao")
    return sinal * int(partes[0])


def tratar_registro(dados, tipos):
    """Aplica as regras campo a campo.

    dados: dict campo -> texto ou None (como enviado pelo orquestrador).
    tipos: dict campo -> tipo da célula de origem ("n", "s", "d", "t", "b").
    Retorna (dados_tratados, erros). Campos sem regra aplicável são mantidos.
    """
    tratados = {}
    erros = []
    for campo in dados:
        valor = dados[campo]
        tipo = tipos.get(campo)
        try:
            if campo in COLS_DOUBLE:
                novo = numero_decimal(valor)
            elif campo == "cep":
                novo = cep(valor, tipo)
            elif campo == "numero":
                novo = numero_logradouro(valor)
            elif campo in COLS_STR:
                novo = texto(valor)
            elif campo == "data_transacao":
                novo = data(valor, tipo)
            elif campo == "acc_iptu":
                novo = inteiro(valor)
            else:
                novo = valor
        except ErroCampo as e:
            novo = None
            erros.append({"campo": campo, "motivo": e.motivo, "valor_original": valor})
        tratados[campo] = novo
    return tratados, erros

import pandas as pd
import glob
import re
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    StructType, StructField,
    StringType, DoubleType, DateType,
    IntegerType, TimestampType, LongType
)


CATALOG = "cdp_dev"
SCHEMA = "itbi"
VOLUME = "volume_itbi_sp"

UF = "SP"

TABLE = f"{CATALOG}.{SCHEMA}.itbi_sp"
LOG_TABLE = f"{CATALOG}.{SCHEMA}.itbi_log"
CONTROLE_TABLE = f"{CATALOG}.{SCHEMA}.itbi_controle"

VOLUME_BASE_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}"

MAX_WORKERS = 5


def get_spark():
    return (
        SparkSession.builder
        .appName("Extração ITBI São Paulo")
        .enableHiveSupport()
        .getOrCreate()
    )


spark = get_spark()


schema_sp = {
    "n° do cadastro (sql)": "id",
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
    "padrão (iptu)": "padrao_iptu",
    "descrição do padrão (iptu)": "descricao_padrao",
    "descricao do padrao (iptu)": "descricao_padrao",
    "descrição padrão (iptu)": "descricao_padrao",
    "descricao padrao (iptu)": "descricao_padrao",
    "acc (iptu)": "acc_iptu",
    "acc(iptu)": "acc_iptu",
    "acc iptu": "acc_iptu",
    "descrição (iptu)": "descricao_uso",
}


COLUNAS_PADRAO_SP = [
    "id",
    "logradouro",
    "numero",
    "complemento",
    "bairro",
    "referencia",
    "cep",
    "transacao",
    "valor_transacao",
    "data_transacao",
    "valor_venal_referencia",
    "proporcao_transmitida",
    "venal_referencia_proporcional",
    "base_calculo",
    "tipo_financiamento",
    "valor_financiado",
    "cartorio_registro",
    "matricula",
    "situacao",
    "area_terreno",
    "testada",
    "fracao_ideal",
    "area_construida",
    "uso_iptu",
    "descricao_uso",
    "padrao_iptu",
    "descricao_padrao",
    "acc_iptu",
]


SHEETS_IGNORADAS = {
    "legenda",
    "explicações",
    "tabela de usos",
    "tabela de padrões"
}


COLS_DOUBLE = [
    "valor_transacao",
    "valor_venal_referencia",
    "venal_referencia_proporcional",
    "base_calculo",
    "valor_financiado",
    "area_terreno",
    "area_construida",
    "proporcao_transmitida",
    "testada",
    "fracao_ideal",
]


COLS_STR = [
    "uf",
    "id",
    "logradouro",
    "numero",
    "complemento",
    "bairro",
    "referencia",
    "cep",
    "transacao",
    "tipo_financiamento",
    "cartorio_registro",
    "matricula",
    "situacao",
    "uso_iptu",
    "descricao_uso",
    "padrao_iptu",
    "descricao_padrao",
    "mes",
    "arquivo_origem",
]


SPARK_SCHEMA = StructType([
    StructField("uf", StringType(), True),
    StructField("id", StringType(), True),
    StructField("matricula", StringType(), True),
    StructField("logradouro", StringType(), True),
    StructField("numero", StringType(), True),
    StructField("complemento", StringType(), True),
    StructField("bairro", StringType(), True),
    StructField("referencia", StringType(), True),
    StructField("cep", StringType(), True),
    StructField("transacao", StringType(), True),
    StructField("valor_transacao", DoubleType(), True),
    StructField("data_transacao", DateType(), True),
    StructField("valor_venal_referencia", DoubleType(), True),
    StructField("venal_referencia_proporcional", DoubleType(), True),
    StructField("base_calculo", DoubleType(), True),
    StructField("tipo_financiamento", StringType(), True),
    StructField("valor_financiado", DoubleType(), True),
    StructField("cartorio_registro", StringType(), True),
    StructField("situacao", StringType(), True),
    StructField("area_terreno", DoubleType(), True),
    StructField("testada", DoubleType(), True),
    StructField("fracao_ideal", DoubleType(), True),
    StructField("area_construida", DoubleType(), True),
    StructField("uso_iptu", StringType(), True),
    StructField("descricao_uso", StringType(), True),
    StructField("padrao_iptu", StringType(), True),
    StructField("descricao_padrao", StringType(), True),
    StructField("acc_iptu", IntegerType(), True),
    StructField("proporcao_transmitida", DoubleType(), True),
    StructField("mes", StringType(), True),
    StructField("arquivo_origem", StringType(), True),
    StructField("data_insercao", TimestampType(), True),
])


COLUNAS_SCHEMA = [f.name for f in SPARK_SCHEMA.fields]


LOG_SCHEMA = StructType([
    StructField("uf", StringType(), True),
    StructField("arquivo", StringType(), True),
    StructField("sheet", StringType(), True),
    StructField("status", StringType(), True),
    StructField("mensagem", StringType(), True),
    StructField("data_execucao", TimestampType(), True),
])


CONTROLE_SCHEMA = StructType([
    StructField("uf", StringType(), True),
    StructField("arquivo", StringType(), True),
    StructField("registros", LongType(), True),
    StructField("status", StringType(), True),
    StructField("mensagem", StringType(), True),
    StructField("data_execucao", TimestampType(), True),
])


def gravar_log(arquivo, sheet, status, mensagem):
    log = [{
        "uf": UF,
        "arquivo": str(arquivo),
        "sheet": str(sheet) if sheet is not None else None,
        "status": str(status),
        "mensagem": str(mensagem) if mensagem is not None else None,
        "data_execucao": datetime.now()
    }]

    spark.createDataFrame(log, schema=LOG_SCHEMA) \
        .write \
        .format("delta") \
        .mode("append") \
        .saveAsTable(LOG_TABLE)


def gravar_controle(arquivo, registros, status, mensagem=None):
    controle = [{
        "uf": UF,
        "arquivo": str(arquivo),
        "registros": int(registros),
        "status": str(status),
        "mensagem": str(mensagem) if mensagem is not None else None,
        "data_execucao": datetime.now()
    }]

    spark.createDataFrame(controle, schema=CONTROLE_SCHEMA) \
        .write \
        .format("delta") \
        .mode("append") \
        .saveAsTable(CONTROLE_TABLE)


def extrair_mes_ano(sheet_name: str) -> str | None:
    match = re.search(r"([A-Z]{3})-(\d{4})", sheet_name.upper())
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    return None


def parse_number(val) -> float | None:
    val = str(val).strip()

    if val in ("", "nan", "None", "-"):
        return None

    val = val.replace("R$", "").strip()

    if "," in val:
        val = val.replace(".", "").replace(",", ".")

    try:
        return float(val)
    except ValueError:
        return None


def padronizar_colunas_com_cabecalho(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
        .str.lower()
    )

    cols = []
    acc_count = 0

    for col in df.columns:
        if col in ["acc(iptu)", "acc (iptu)", "acc iptu"]:
            acc_count += 1

            if acc_count == 1:
                cols.append("acc_iptu")
            else:
                cols.append("descricao_padrao")
        else:
            cols.append(schema_sp.get(col, col))

    df.columns = cols
    return df


def aba_tem_cabecalho(file: str, sheet: str) -> bool:
    df_teste = pd.read_excel(file, sheet_name=sheet, nrows=1)

    colunas = (
        pd.Series(df_teste.columns)
        .astype(str)
        .str.strip()
        .str.lower()
        .tolist()
    )

    qtd_colunas_reconhecidas = sum(1 for c in colunas if c in schema_sp)

    return qtd_colunas_reconhecidas >= 3


def ler_aba_itbi(file: str, sheet: str) -> pd.DataFrame:
    if aba_tem_cabecalho(file, sheet):
        df = pd.read_excel(file, sheet_name=sheet)
        df = padronizar_colunas_com_cabecalho(df)
    else:
        df = pd.read_excel(file, sheet_name=sheet, header=None)
        df = df.iloc[:, :len(COLUNAS_PADRAO_SP)]
        df.columns = COLUNAS_PADRAO_SP

    return df


def process_file(file: str) -> pd.DataFrame | None:
    filename = os.path.basename(file)
    dfs = []

    try:
        excel_file = pd.ExcelFile(file)

        for sheet in excel_file.sheet_names:
            if sheet.lower() in SHEETS_IGNORADAS:
                continue

            mes_ano = extrair_mes_ano(sheet)

            if not mes_ano:
                continue

            try:
                df = ler_aba_itbi(file, sheet)

                df = df.loc[:, ~df.columns.duplicated(keep="first")]

                df["uf"] = UF
                df["mes"] = mes_ano
                df["arquivo_origem"] = filename
                df["data_insercao"] = datetime.now()

                dfs.append(df)

            except Exception as e:
                print(f"[{filename}] Erro na sheet {sheet}: {e}")
                gravar_log(filename, sheet, "ERRO_SHEET", e)

        if not dfs:
            gravar_log(filename, None, "SEM_DADOS", "Nenhuma aba válida encontrada")
            return None

        return pd.concat(dfs, ignore_index=True)

    except Exception as e:
        print(f"Erro ao abrir {filename}: {e}")
        gravar_log(filename, None, "ERRO_ABRIR_ARQUIVO", e)
        return None


def clean_sp(df: pd.DataFrame) -> pd.DataFrame:

    df["uf"] = UF

    for col_name in COLS_DOUBLE:
        if col_name in df.columns:
            df[col_name] = (
                df[col_name]
                .astype(str)
                .str.replace("R$", "", regex=False)
                .str.strip()
                .apply(parse_number)
            )

    for col_name in COLS_STR:
        if col_name in df.columns:

            df[col_name] = (
                df[col_name]
                .astype(str)
                .str.strip()
                .replace({
                    "nan": None,
                    "None": None,
                    "": None
                })
            )

            if col_name == "numero":
                df[col_name] = (
                    df[col_name]
                    .str.replace(".0", "", regex=False)
                )

            if col_name == "cep":
                df[col_name] = (
                    df[col_name]
                    .str.replace(".0", "", regex=False)
                    .str.replace(r"\D", "", regex=True)
                    .str.zfill(8)
                )

    df["uf"] = UF

    if "data_transacao" in df.columns:
        df["data_transacao"] = pd.to_datetime(
            df["data_transacao"],
            errors="coerce"
        ).dt.date

    if "acc_iptu" in df.columns:
        df["acc_iptu"] = pd.to_numeric(
            df["acc_iptu"],
            errors="coerce"
        ).astype("Int64")

    if "data_insercao" in df.columns:
        df["data_insercao"] = pd.to_datetime(
            df["data_insercao"],
            errors="coerce"
        )
    else:
        df["data_insercao"] = datetime.now()

    if "arquivo_origem" not in df.columns:
        df["arquivo_origem"] = None

    for c in COLUNAS_SCHEMA:
        if c not in df.columns:
            df[c] = None

    df["uf"] = UF

    return df[COLUNAS_SCHEMA]


def process_file_worker(file: str):
    filename = os.path.basename(file)

    print(f"\nIniciando: {filename}")

    try:
        df = process_file(file)

        if df is None or df.empty:
            gravar_controle(
                arquivo=filename,
                registros=0,
                status="SEM_DADOS",
                mensagem="Nenhum dado extraído"
            )
            return None, file, filename, "SEM_DADOS"

        df = clean_sp(df)

        print(f"{filename}: {df.shape[0]} registros tratados em memória")

        return df, file, filename, "SUCESSO"

    except Exception as e:
        print(f"{filename}: erro no processamento: {e}")

        gravar_log(
            arquivo=filename,
            sheet=None,
            status="ERRO_PROCESSAMENTO",
            mensagem=e
        )

        gravar_controle(
            arquivo=filename,
            registros=0,
            status="ERRO",
            mensagem=e
        )

        return None, file, filename, "ERRO"


def insert_sp(df: pd.DataFrame, filename: str):
    sdf = spark.createDataFrame(df, schema=SPARK_SCHEMA)

    temp_view = "temp_itbi_sp"
    sdf.createOrReplaceTempView(temp_view)

    total = df.shape[0]

    colunas_insert = ", ".join(COLUNAS_SCHEMA)
    valores_insert = ", ".join([f"source.{c}" for c in COLUNAS_SCHEMA])

    spark.sql(f"""
        MERGE INTO {TABLE} AS target
        USING {temp_view} AS source
        ON  target.uf = source.uf
        AND target.mes = source.mes
        AND target.id = source.id
        AND COALESCE(target.matricula, '') = COALESCE(source.matricula, '')

        WHEN NOT MATCHED THEN
        INSERT ({colunas_insert})
        VALUES ({valores_insert})
    """)

    print(f"{filename}: {total} registros processados no MERGE final")


def run_pipeline():
    files = glob.glob(f"{VOLUME_BASE_PATH}/*.xlsx")

    if not files:
        raise FileNotFoundError(
            f"Nenhum arquivo encontrado em: {VOLUME_BASE_PATH}"
        )

    print(f"{len(files)} arquivos encontrados — {MAX_WORKERS} workers paralelos\n")

    dfs_processados = []
    arquivos_sucesso = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_file_worker, f): f
            for f in files
        }

        for future in as_completed(futures):
            df, file_path, filename, status = future.result()

            if status == "SUCESSO" and df is not None:
                dfs_processados.append(df)
                arquivos_sucesso.append(file_path)

                gravar_controle(
                    arquivo=filename,
                    registros=df.shape[0],
                    status="PROCESSADO_MEMORIA",
                    mensagem=f"Arquivo processado com sucesso. Registros: {df.shape[0]}"
                )

    if not dfs_processados:
        print("Nenhum arquivo válido para inserir.")
        return

    print("Unificando DataFrames processados...")

    df_final = pd.concat(dfs_processados, ignore_index=True)

    print(f"Total antes de remover duplicados: {df_final.shape[0]}")

    df_final = df_final.drop_duplicates(
        subset=["uf", "mes", "id", "matricula"]
    )

    print(f"Total após remover duplicados: {df_final.shape[0]}")

    try:
        insert_sp(df_final, "CARGA_UNIFICADA_ITBI_SP")

        gravar_controle(
            arquivo="CARGA_UNIFICADA_ITBI_SP",
            registros=df_final.shape[0],
            status="SUCESSO",
            mensagem=f"Carga finalizada com sucesso. Total de registros: {df_final.shape[0]}"
        )

        for file_path in arquivos_sucesso:
            os.remove(file_path)

        print("Carga finalizada com sucesso. Arquivos processados removidos do Volume.")

    except Exception as e:
        gravar_log(
            arquivo="CARGA_UNIFICADA_ITBI_SP",
            sheet=None,
            status="ERRO_MERGE_FINAL",
            mensagem=e
        )

        gravar_controle(
            arquivo="CARGA_UNIFICADA_ITBI_SP",
            registros=0,
            status="ERRO",
            mensagem=e
        )

        print(f"Erro no MERGE final: {e}")
        print("Arquivos mantidos no Volume para reprocessamento.")


run_pipeline()
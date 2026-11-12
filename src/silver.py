import json
import shutil
import unicodedata
from datetime import datetime

import pandas as pd

from src.config import (
    ANIOS_ESPERADOS,
    BRONZE_DESERCION,
    NIVELES_ESPERADOS,
    SILVER_CALIDAD,
    SILVER_DESERCION,
    SILVER_RESPALDOS_DIR,
    crear_directorios,
)
from src.logger import logger


def normalizar_departamento(valor):
    texto = unicodedata.normalize("NFKD", valor.strip())

    texto = "".join(
        caracter
        for caracter in texto
        if not unicodedata.combining(caracter)
    )

    return " ".join(texto.upper().split())


def transformar_desercion():
    crear_directorios()

    if not BRONZE_DESERCION.is_file():
        raise FileNotFoundError(
            f"No se encontró bronze: {BRONZE_DESERCION}"
        )

    logger.info("Iniciando transformación silver")

    bronze = pd.read_csv(
        BRONZE_DESERCION,
        encoding="utf-8-sig",
        dtype="string",
        keep_default_na=False,
    )

    requeridas = {
        "nivel_formacion",
        "departamento_original",
        "linea_origen",
        *ANIOS_ESPERADOS,
    }

    faltantes = requeridas - set(bronze.columns)

    if faltantes:
        raise ValueError(
            f"Faltan columnas en bronze: {sorted(faltantes)}"
        )

    if bronze.empty:
        raise ValueError("El archivo bronze está vacío.")

    silver = bronze.melt(
        id_vars=[
            "nivel_formacion",
            "departamento_original",
            "linea_origen",
        ],
        value_vars=list(ANIOS_ESPERADOS),
        var_name="anio",
        value_name="tasa_original",
    )

    silver = silver.rename(
        columns={"departamento_original": "departamento"}
    )

    silver["departamento"] = silver["departamento"].str.strip()
    silver["nivel_formacion"] = silver["nivel_formacion"].str.strip()
    silver["tasa_original"] = silver["tasa_original"].str.strip()

    silver["anio"] = pd.to_numeric(
        silver["anio"],
        errors="raise",
    ).astype("Int64")

    silver["linea_origen"] = pd.to_numeric(
        silver["linea_origen"],
        errors="raise",
    ).astype("Int64")

    silver["departamento_clave"] = (
        silver["departamento"].map(normalizar_departamento)
    )

    es_na = silver["tasa_original"].str.upper().eq("NA")
    es_vacio = silver["tasa_original"].eq("")
    es_numerico_esperado = ~(es_na | es_vacio)

    silver["estado_dato"] = "reportado"
    silver.loc[es_na, "estado_dato"] = "no_aplica"
    silver.loc[es_vacio, "estado_dato"] = "sin_dato"

    silver["tasa_desercion"] = pd.to_numeric(
        silver["tasa_original"].mask(es_na | es_vacio, pd.NA),
        errors="coerce",
    ).astype("Float64")

    conversion_invalida = (
        es_numerico_esperado
        & silver["tasa_desercion"].isna()
    )

    if conversion_invalida.any():
        ejemplos = silver.loc[
            conversion_invalida,
            ["departamento", "nivel_formacion", "anio", "tasa_original"],
        ].head(10)

        raise ValueError(
            "Se encontraron valores no reconocidos en las tasas:\n"
            f"{ejemplos.to_string(index=False)}"
        )

    fuera_rango = (
        silver["tasa_desercion"].notna()
        & ~silver["tasa_desercion"].between(0, 1)
    )

    if fuera_rango.any():
        ejemplos = silver.loc[
            fuera_rango,
            ["departamento", "nivel_formacion", "anio", "tasa_original"],
        ].head(10)

        raise ValueError(
            "Se encontraron tasas fuera del rango 0–1:\n"
            f"{ejemplos.to_string(index=False)}"
        )

    if silver["departamento"].eq("").any():
        raise ValueError("Hay departamentos vacíos.")

    niveles = set(silver["nivel_formacion"].unique())

    if niveles != set(NIVELES_ESPERADOS):
        raise ValueError(f"Niveles inesperados: {niveles}")

    claves = [
        "departamento_clave",
        "nivel_formacion",
        "anio",
    ]

    duplicados = silver.duplicated(subset=claves, keep=False)

    if duplicados.any():
        ejemplos = silver.loc[duplicados, claves].head(10)

        raise ValueError(
            "Hay claves duplicadas; no se eliminarán automáticamente:\n"
            f"{ejemplos.to_string(index=False)}"
        )

    esperadas = len(bronze) * len(ANIOS_ESPERADOS)

    if len(silver) != esperadas:
        raise ValueError(
            f"Se esperaban {esperadas} filas y se obtuvieron {len(silver)}."
        )

    silver["fuente_archivo"] = "td_departamento.csv"
    silver["indicador"] = "tasa_desercion_anual"

    columnas = [
        "departamento",
        "departamento_clave",
        "nivel_formacion",
        "anio",
        "tasa_desercion",
        "estado_dato",
        "tasa_original",
        "fuente_archivo",
        "linea_origen",
        "indicador",
    ]

    silver = silver[columnas].sort_values(
        ["nivel_formacion", "departamento_clave", "anio"]
    ).reset_index(drop=True)

    departamentos_por_nivel = {
        nivel: sorted(
            silver.loc[
                silver["nivel_formacion"].eq(nivel),
                "departamento",
            ].unique().tolist()
        )
        for nivel in NIVELES_ESPERADOS
    }

    referencia = set(departamentos_por_nivel["Universitario"])

    reporte = {
        "archivo_fuente": "td_departamento.csv",
        "filas_bronze": int(len(bronze)),
        "filas_silver": int(len(silver)),
        "anio_minimo": int(silver["anio"].min()),
        "anio_maximo": int(silver["anio"].max()),
        "tasas_reportadas": int(silver["tasa_desercion"].notna().sum()),
        "no_aplica": int(silver["estado_dato"].eq("no_aplica").sum()),
        "sin_dato": int(silver["estado_dato"].eq("sin_dato").sum()),
        "claves_duplicadas": int(duplicados.sum()),
        "tasas_fuera_rango": int(fuera_rango.sum()),
        "departamentos_por_nivel": departamentos_por_nivel,
        "ausentes_respecto_universitario": {
            nivel: sorted(referencia - set(departamentos))
            for nivel, departamentos in departamentos_por_nivel.items()
        },
    }

    if SILVER_DESERCION.exists():
        SILVER_RESPALDOS_DIR.mkdir(parents=True, exist_ok=True)

        marca = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        respaldo = SILVER_RESPALDOS_DIR / (
            f"{SILVER_DESERCION.stem}_{marca}.csv"
        )

        shutil.copy2(SILVER_DESERCION, respaldo)
        logger.info("Silver anterior respaldado: %s", respaldo.name)

    silver.to_csv(
        SILVER_DESERCION,
        index=False,
        encoding="utf-8-sig",
    )

    SILVER_CALIDAD.write_text(
        json.dumps(reporte, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info("Silver generado: %s", SILVER_DESERCION.name)
    logger.info("Filas silver: %s", len(silver))
    logger.info("Tasas reportadas: %s", reporte["tasas_reportadas"])
    logger.info("Valores no aplica: %s", reporte["no_aplica"])
    logger.info("Valores sin dato: %s", reporte["sin_dato"])
    logger.info("Claves duplicadas: %s", reporte["claves_duplicadas"])
    logger.info(
        "Ausentes respecto a Universitario: %s",
        reporte["ausentes_respecto_universitario"],
    )

    return silver


def ejecutar_silver():
    try:
        return transformar_desercion()
    except Exception:
        logger.exception("Falló la transformación silver")
        raise


if __name__ == "__main__":
    ejecutar_silver()
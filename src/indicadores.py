import pandas as pd

from src.config import GOLD_FINAL, crear_directorios
from src.logger import logger


RUTA_INDICADORES = (
    GOLD_FINAL.parent / "gold_indicadores_por_nivel_anio.csv"
)

RUTA_RESUMEN = (
    GOLD_FINAL.parent / "gold_resumen_calidad.csv"
)


def leer_booleano(serie, nombre):
    texto = (
        serie.astype("string")
        .str.strip()
        .str.lower()
    )

    resultado = texto.map({
        "true": True,
        "false": False,
    })

    if resultado.isna().any():
        raise ValueError(
            f"Valores booleanos no reconocidos en {nombre}."
        )

    return resultado.astype(bool)


def generar_indicadores():
    crear_directorios()

    if not GOLD_FINAL.is_file():
        raise FileNotFoundError(
            f"No se encontró el gold: {GOLD_FINAL}"
        )

    logger.info("Generando indicadores de entrega")

    df = pd.read_csv(
        GOLD_FINAL,
        dtype="string",
        keep_default_na=False,
        encoding="utf-8-sig",
    )

    requeridas = {
        "codigo_departamento",
        "nivel_formacion",
        "anio",
        "tasa_desercion_porcentaje",
        "estado_dato",
        "variacion_desercion_pp",
        "coincidio_matricula",
        "par_sin_alertas_tecnicas",
    }

    faltantes = requeridas - set(df.columns)

    if faltantes:
        raise ValueError(
            f"Faltan columnas: {sorted(faltantes)}"
        )

    if df.empty:
        raise ValueError("El gold está vacío.")

    for columna in [
        "anio",
        "tasa_desercion_porcentaje",
        "variacion_desercion_pp",
    ]:
        df[columna] = pd.to_numeric(
            df[columna].replace("", pd.NA),
            errors="raise",
        )

    df["anio"] = df["anio"].astype("Int64")

    for columna in [
        "coincidio_matricula",
        "par_sin_alertas_tecnicas",
    ]:
        df[columna] = leer_booleano(
            df[columna],
            columna,
        )

    claves = [
        "codigo_departamento",
        "nivel_formacion",
        "anio",
    ]

    if df.duplicated(subset=claves).any():
        raise ValueError(
            "Hay claves duplicadas; no se generarán indicadores."
        )

    df["es_no_aplica"] = df["estado_dato"].eq("no_aplica")
    df["es_sin_dato"] = df["estado_dato"].eq("sin_dato")

    indicadores = (
        df.groupby(
            ["nivel_formacion", "anio"],
            as_index=False,
        )
        .agg(
            departamentos_presentes=(
                "codigo_departamento",
                "nunique",
            ),
            departamentos_con_tasa=(
                "tasa_desercion_porcentaje",
                "count",
            ),
            departamentos_no_aplica=(
                "es_no_aplica",
                "sum",
            ),
            departamentos_sin_dato=(
                "es_sin_dato",
                "sum",
            ),
            tasa_media_simple_pct=(
                "tasa_desercion_porcentaje",
                "mean",
            ),
            tasa_mediana_pct=(
                "tasa_desercion_porcentaje",
                "median",
            ),
            tasa_minima_pct=(
                "tasa_desercion_porcentaje",
                "min",
            ),
            tasa_maxima_pct=(
                "tasa_desercion_porcentaje",
                "max",
            ),
            cambio_anual_medio_pp=(
                "variacion_desercion_pp",
                "mean",
            ),
            departamentos_con_variacion=(
                "variacion_desercion_pp",
                "count",
            ),
            coincidencias_matricula=(
                "coincidio_matricula",
                "sum",
            ),
            pares_sin_alertas_tecnicas=(
                "par_sin_alertas_tecnicas",
                "sum",
            ),
        )
        .sort_values(["nivel_formacion", "anio"])
        .reset_index(drop=True)
    )

    indicadores["disponibilidad_tasa_pct"] = (
        indicadores["departamentos_con_tasa"]
        / indicadores["departamentos_presentes"]
        * 100
    )

    indicadores["cobertura_cruce_pct"] = (
        indicadores["coincidencias_matricula"]
        / indicadores["departamentos_presentes"]
        * 100
    )

    indicadores["tipo_agregacion"] = (
        "DESCRIPTIVA_DEPARTAMENTAL_NO_PONDERADA"
    )

    total = len(df)

    resumen = pd.DataFrame([
        {
            "metrica": "observaciones_gold",
            "valor": total,
            "unidad": "observaciones",
        },
        {
            "metrica": "tasas_disponibles",
            "valor": int(
                df["tasa_desercion_porcentaje"].notna().sum()
            ),
            "unidad": "observaciones",
        },
        {
            "metrica": "observaciones_no_aplica",
            "valor": int(df["es_no_aplica"].sum()),
            "unidad": "observaciones",
        },
        {
            "metrica": "observaciones_sin_dato",
            "valor": int(df["es_sin_dato"].sum()),
            "unidad": "observaciones",
        },
        {
            "metrica": "disponibilidad_tasa_pct",
            "valor": (
                df["tasa_desercion_porcentaje"]
                .notna()
                .mean()
                * 100
            ),
            "unidad": "porcentaje_de_filas_gold",
        },
        {
            "metrica": "cobertura_cruce_pct",
            "valor": df["coincidio_matricula"].mean() * 100,
            "unidad": "porcentaje_de_filas_gold",
        },
        {
            "metrica": "pares_sin_alertas_tecnicas",
            "valor": int(
                df["par_sin_alertas_tecnicas"].sum()
            ),
            "unidad": "observaciones",
        },
        {
            "metrica": "variaciones_anuales_calculadas",
            "valor": int(
                df["variacion_desercion_pp"].notna().sum()
            ),
            "unidad": "comparaciones",
        },
    ])

    indicadores.to_csv(
        RUTA_INDICADORES,
        index=False,
        encoding="utf-8-sig",
    )

    resumen.to_csv(
        RUTA_RESUMEN,
        index=False,
        encoding="utf-8-sig",
    )

    logger.info(
        "Indicadores por nivel y año: %s filas",
        len(indicadores),
    )

    logger.info(
        "Archivo de indicadores: %s",
        RUTA_INDICADORES.name,
    )

    logger.info(
        "Resumen de calidad: %s",
        RUTA_RESUMEN.name,
    )

    logger.info(
        "No se estimaron tasas nacionales ponderadas, "
        "desertores ni permanencia."
    )

    return indicadores, resumen


def ejecutar_indicadores():
    try:
        return generar_indicadores()
    except Exception:
        logger.exception(
            "Falló la generación de indicadores"
        )
        raise


if __name__ == "__main__":
    ejecutar_indicadores()
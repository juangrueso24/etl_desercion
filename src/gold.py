import json
import shutil
from datetime import datetime

import numpy as np
import pandas as pd

from src.config import (
    GOLD_FINAL,
    SILVER_DIR,
    crear_directorios,
)
from src.logger import logger


RUTA_INTEGRADO = SILVER_DIR / "silver_integrado.csv"

RUTA_CALIDAD = GOLD_FINAL.parent / "calidad_gold.json"

RUTA_VARIACIONES = (
    GOLD_FINAL.parent / "gold_variaciones_anuales.csv"
)

RUTA_TOP20 = (
    GOLD_FINAL.parent / "gold_top20_departamentos.csv"
)

RUTA_RESPALDOS = GOLD_FINAL.parent / "respaldos"

CLAVES = [
    "codigo_departamento",
    "nivel_formacion",
    "anio",
]


def convertir_booleano(serie, nombre):
    texto = (
        serie.astype("string")
        .str.strip()
        .str.lower()
    )

    resultado = texto.map({
        "true": True,
        "false": False,
    }).astype("boolean")

    invalidos = texto.ne("") & resultado.isna()

    if invalidos.any():
        raise ValueError(
            f"Valores booleanos no reconocidos en {nombre}."
        )

    return resultado


def convertir_numero(serie):
    texto = serie.astype("string").str.strip()

    return pd.to_numeric(
        texto.mask(texto.eq(""), pd.NA),
        errors="raise",
    ).astype("Float64")


def agregar_variaciones(df):
    df = df.sort_values(
        ["codigo_departamento", "nivel_formacion", "anio"]
    ).copy()

    grupos = df.groupby(
        ["codigo_departamento", "nivel_formacion"],
        sort=False,
    )

    anio_anterior = grupos["anio"].shift(1)
    tasa_anterior = grupos["tasa_desercion"].shift(1)

    comparables = (
        df["anio"].sub(anio_anterior).eq(1)
        & df["tasa_desercion"].notna()
        & tasa_anterior.notna()
    ).fillna(False)

    df["anio_anterior_comparable"] = (
        anio_anterior.where(comparables).astype("Int64")
    )

    df["tasa_anterior_comparable"] = (
        tasa_anterior.where(comparables).astype("Float64")
    )

    df["variacion_desercion_pp"] = (
        (df["tasa_desercion"] - tasa_anterior) * 100
    ).where(comparables).astype("Float64")

    df["variacion_calculable"] = comparables

    return df


def crear_ranking(df):
    ranking = df.loc[
        df["tasa_desercion"].notna()
    ].copy()

    # Los empates se ordenan por código para seleccionar
    # una cantidad exacta de filas y hacer reproducible el resultado.
    ranking = ranking.sort_values(
        [
            "anio",
            "nivel_formacion",
            "tasa_desercion",
            "codigo_departamento",
        ],
        ascending=[True, True, False, True],
    )

    grupos = ranking.groupby(
        ["anio", "nivel_formacion"],
        sort=False,
    )

    ranking["posicion_tasa"] = grupos.cumcount() + 1

    ranking["departamentos_con_tasa_grupo"] = (
        grupos["codigo_departamento"].transform("size")
    )

    ranking["cantidad_top20_grupo"] = np.ceil(
        ranking["departamentos_con_tasa_grupo"] * 0.20
    ).astype(int)

    ranking["es_top20_departamental"] = (
        ranking["posicion_tasa"]
        <= ranking["cantidad_top20_grupo"]
    )

    columnas = [
        *CLAVES,
        "posicion_tasa",
        "departamentos_con_tasa_grupo",
        "cantidad_top20_grupo",
        "es_top20_departamental",
    ]

    return ranking[columnas]


def crear_gold_final():
    crear_directorios()

    if not RUTA_INTEGRADO.is_file():
        raise FileNotFoundError(
            f"No se encontró {RUTA_INTEGRADO}. "
            "Ejecuta primero src.integracion."
        )

    logger.info("Iniciando gold integrado")

    df = pd.read_csv(
        RUTA_INTEGRADO,
        dtype="string",
        keep_default_na=False,
        encoding="utf-8-sig",
    )

    requeridas = {
        *CLAVES,
        "departamento",
        "departamento_clave",
        "tasa_desercion",
        "estado_dato",
        "indicador",
        "matricula_reportada",
        "estado_matricula",
        "coincidio_matricula",
        "estado_integracion_matricula",
        "requiere_revision_matricula",
    }

    faltantes = requeridas - set(df.columns)

    if faltantes:
        raise ValueError(
            f"Faltan columnas: {sorted(faltantes)}"
        )

    if df.empty:
        raise ValueError("El silver integrado está vacío.")

    for columna in ["anio", "linea_origen"]:
        if columna in df.columns:
            numeros = convertir_numero(df[columna])

            if (
                numeros.isna().any()
                or numeros.mod(1).ne(0).any()
            ):
                raise ValueError(
                    f"Valores no enteros o vacíos en {columna}."
                )

            df[columna] = numeros.astype("Int64")

    df["tasa_desercion"] = convertir_numero(
        df["tasa_desercion"]
    )

    df["matricula_reportada"] = convertir_numero(
        df["matricula_reportada"]
    )

    for columna in [
        "coincidio_matricula",
        "requiere_revision_matricula",
        "alerta_revision_silver_origen",
    ]:
        if columna in df.columns:
            df[columna] = convertir_booleano(
                df[columna],
                columna,
            )

    if df[CLAVES].isna().any(axis=1).any():
        raise ValueError("Hay claves nulas.")

    if df[CLAVES].astype("string").eq("").any(axis=1).any():
        raise ValueError("Hay claves vacías.")

    if df.duplicated(subset=CLAVES).any():
        raise ValueError("Hay claves duplicadas.")

    tasa = df["tasa_desercion"]

    if (
        tasa.notna() & ~tasa.between(0, 1)
    ).any():
        raise ValueError("Hay tasas fuera del rango 0–1.")

    if not df["estado_dato"].isin(
        ["reportado", "sin_dato", "no_aplica"]
    ).all():
        raise ValueError("Hay estados de dato no reconocidos.")

    if df["estado_dato"].eq("reportado").ne(
        tasa.notna()
    ).any():
        raise ValueError(
            "Hay inconsistencias entre estado y tasa."
        )

    if not df["indicador"].eq(
        "tasa_desercion_anual"
    ).all():
        raise ValueError("Se encontraron otros indicadores.")

    if (
        df["matricula_reportada"].notna()
        & df["matricula_reportada"].lt(0)
    ).any():
        raise ValueError("Hay matrículas negativas.")

    for columna in [
        "coincidio_matricula",
        "requiere_revision_matricula",
    ]:
        if df[columna].isna().any():
            raise ValueError(
                f"Hay banderas vacías en {columna}."
            )

    df["tasa_desercion_porcentaje"] = tasa * 100
    df["tasa_disponible"] = tasa.notna()

    df["par_sin_alertas_tecnicas"] = (
        df["coincidio_matricula"]
        & df["estado_integracion_matricula"].eq(
            "COINCIDENCIA_TECNICA"
        )
        & df["estado_matricula"].eq("reportado")
        & df["matricula_reportada"].notna()
        & ~df["requiere_revision_matricula"]
        & df["tasa_disponible"]
    ).fillna(False)

    df = agregar_variaciones(df)

    ranking = crear_ranking(df)

    gold = df.merge(
        ranking,
        on=CLAVES,
        how="left",
        validate="one_to_one",
    )

    for columna in [
        "posicion_tasa",
        "departamentos_con_tasa_grupo",
        "cantidad_top20_grupo",
    ]:
        gold[columna] = gold[columna].astype("Int64")

    gold["es_top20_departamental"] = (
        gold["es_top20_departamental"].astype("boolean")
    )

    gold = gold.sort_values(
        ["nivel_formacion", "codigo_departamento", "anio"]
    ).reset_index(drop=True)

    variaciones = gold.loc[
        gold["variacion_calculable"]
    ].copy()

    top20 = gold.loc[
        gold["es_top20_departamental"].fillna(False)
    ].copy()

    reporte = {
        "fuente": RUTA_INTEGRADO.name,
        "filas_gold": int(len(gold)),
        "tasas_disponibles": int(
            gold["tasa_disponible"].sum()
        ),
        "observaciones_sin_tasa": int(
            (~gold["tasa_disponible"]).sum()
        ),
        "coincidencias_matricula": int(
            gold["coincidio_matricula"].sum()
        ),
        "pares_sin_alertas_tecnicas": int(
            gold["par_sin_alertas_tecnicas"].sum()
        ),
        "variaciones_anuales_calculadas": int(
            len(variaciones)
        ),
        "filas_seleccionadas_top20": int(len(top20)),
        "claves_duplicadas": 0,
        "anio_minimo": int(gold["anio"].min()),
        "anio_maximo": int(gold["anio"].max()),
        "integracion_matricula": (
            "CRUCE_TECNICO_REALIZADO"
        ),
        "advertencias_analisis": [
            (
                "Un cruce técnico no demuestra equivalencia "
                "de las poblaciones de ambas fuentes."
            ),
            (
                "par_sin_alertas_tecnicas no certifica "
                "comparabilidad metodológica."
            ),
            (
                "No se calculan desertores multiplicando "
                "la matrícula por la tasa."
            ),
            (
                "Las variaciones se expresan en puntos "
                "porcentuales, no en cambio porcentual relativo."
            ),
            (
                "Solo se comparan años consecutivos "
                "con tasas disponibles en ambos años."
            ),
            (
                "El ranking selecciona ceil(20 % de los "
                "departamentos con tasa) por año y nivel."
            ),
            (
                "Los empates en el ranking se resuelven por "
                "código; la selección no implica diferencias "
                "estadísticamente significativas."
            ),
            (
                "El ranking departamental es complementario: "
                "no sustituye el KR original de instituciones, "
                "niveles o periodos."
            ),
            (
                "TyT sigue sin matrícula integrada; "
                "no se suman otros niveles para construirla."
            ),
            (
                "Las tasas departamentales no se ponderan "
                "con esta matrícula para estimar una tasa nacional."
            ),
            (
                "Se conserva la advertencia sobre exclusión "
                "del SENA desde 2019 en deserción tecnológica."
            ),
        ],
    }

    if GOLD_FINAL.exists():
        RUTA_RESPALDOS.mkdir(
            parents=True,
            exist_ok=True,
        )

        marca = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        respaldo = RUTA_RESPALDOS / (
            f"gold_final_{marca}.csv"
        )

        shutil.copy2(GOLD_FINAL, respaldo)

        logger.info(
            "Gold anterior respaldado: %s",
            respaldo.name,
        )

    gold.to_csv(
        GOLD_FINAL,
        index=False,
        encoding="utf-8-sig",
    )

    variaciones.to_csv(
        RUTA_VARIACIONES,
        index=False,
        encoding="utf-8-sig",
    )

    top20.to_csv(
        RUTA_TOP20,
        index=False,
        encoding="utf-8-sig",
    )

    RUTA_CALIDAD.write_text(
        json.dumps(
            reporte,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    for campo in [
        "filas_gold",
        "tasas_disponibles",
        "observaciones_sin_tasa",
        "coincidencias_matricula",
        "pares_sin_alertas_tecnicas",
        "variaciones_anuales_calculadas",
        "filas_seleccionadas_top20",
    ]:
        logger.info("%s: %s", campo, reporte[campo])

    logger.info("Gold integrado finalizado")
    logger.info("No se realizó carga a base de datos")

    return gold


def ejecutar_gold():
    try:
        return crear_gold_final()
    except Exception:
        logger.exception("Falló la construcción de gold")
        raise


if __name__ == "__main__":
    ejecutar_gold()
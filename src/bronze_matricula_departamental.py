import json

import pandas as pd
import requests

from src.config import (
    BRONZE_DIR,
    RAW_DIR,
    crear_directorios,
)
from src.logger import logger
from src.utils import normalizar_texto


RECURSO = "4hrb-y62g"

URL_DATOS = (
    f"https://www.datos.gov.co/resource/{RECURSO}.json"
)

URL_METADATA = (
    f"https://www.datos.gov.co/api/views/{RECURSO}.json"
)

RUTA_RAW = RAW_DIR / "matricula_departamental_original.json"

RUTA_METADATA = (
    RAW_DIR / "matricula_departamental_metadatos.json"
)

RUTA_BRONZE = (
    BRONZE_DIR / "bronze_matricula_departamental.csv"
)

RUTA_DIAGNOSTICO = (
    BRONZE_DIR / "diagnostico_matricula_departamental.json"
)

LIMITE = 50000

CLAVES = [
    "a_o",
    "c_digo_deldepartamento",
]

METRICAS = [
    "tecnica_profesional",
    "tecnologica",
    "universitaria",
    "especializacion",
    "maestria",
    "doctorado",
    "ies_con_oferta",
]


def consultar(session, url, parametros=None):
    respuesta = session.get(
        url,
        params=parametros,
        timeout=120,
    )

    respuesta.raise_for_status()
    return respuesta.json()


def consultar_total(session):
    resultado = consultar(
        session,
        URL_DATOS,
        {"$select": "count(*) AS total"},
    )

    return int(resultado[0]["total"])


def diagnosticar(df):
    revision = df.astype("string").fillna("")

    for columna in revision.columns:
        revision[columna] = revision[columna].str.strip()

    revision["nombre_del_departamento"] = (
        revision["nombre_del_departamento"]
        .map(normalizar_texto)
    )

    codigo = revision["c_digo_deldepartamento"]

    codigo_valido = (
        codigo.str.fullmatch(r"[0-9]{1,2}")
        .fillna(False)
    )

    revision.loc[
        codigo_valido,
        "c_digo_deldepartamento",
    ] = codigo.loc[codigo_valido].str.zfill(2)

    anios = pd.to_numeric(
        revision["a_o"],
        errors="coerce",
    )

    anio_valido = (
        anios.notna()
        & anios.between(1900, 2100)
        & anios.mod(1).eq(0)
    ).fillna(False)

    claves_validas = codigo_valido & anio_valido

    unicas = (
        revision.loc[claves_validas]
        .drop_duplicates()
        .copy()
    )

    conteos = (
        unicas.groupby(CLAVES, dropna=False)
        .size()
    )

    claves_repetidas = conteos[conteos.gt(1)]

    diferencias_metricas = (
        unicas.groupby(CLAVES, dropna=False)[METRICAS]
        .nunique(dropna=False)
        .gt(1)
        .any(axis=1)
    )

    anios_observados = sorted(
        anios.loc[anio_valido]
        .astype(int)
        .unique()
        .tolist()
    )

    reporte = {
        "recurso": RECURSO,
        "filas_bronze": int(len(df)),
        "copias_exactas_adicionales": int(
            df.duplicated().sum()
        ),
        "copias_adicionales_tras_normalizar": int(
            revision.duplicated().sum()
        ),
        "filas_con_clave_invalida": int(
            (~claves_validas).sum()
        ),
        "filas_distintas_con_clave_valida": int(
            len(unicas)
        ),
        "claves_validas_distintas": int(
            len(conteos)
        ),
        "claves_con_varios_registros": int(
            len(claves_repetidas)
        ),
        "claves_con_metricas_distintas": int(
            diferencias_metricas.sum()
        ),
        "anios_observados": anios_observados,
        "ejemplos_claves_repetidas": (
            claves_repetidas
            .rename("registros_distintos")
            .reset_index()
            .head(20)
            .to_dict(orient="records")
        ),
        "alcance": (
            "Diagnóstico sobre una copia temporal. "
            "Bronze conserva todos los registros recibidos. "
            "No se han sumado matrículas."
        ),
    }

    return reporte


def extraer_matricula_departamental():
    crear_directorios()

    logger.info(
        "Iniciando bronze de matrícula departamental"
    )

    with requests.Session() as session:
        total_antes = consultar_total(session)

        if total_antes == 0:
            raise ValueError(
                "La fuente departamental no contiene registros."
            )

        if total_antes > LIMITE:
            raise ValueError(
                f"La fuente contiene {total_antes} registros. "
                "Se requiere implementar paginación."
            )

        datos = consultar(
            session,
            URL_DATOS,
            {
                "$limit": LIMITE,
                "$order": "a_o, c_digo_deldepartamento",
            },
        )

        if not isinstance(datos, list):
            raise ValueError(
                "La API no devolvió una lista de registros."
            )

        total_despues = consultar_total(session)

        if not (
            total_antes == total_despues == len(datos)
        ):
            raise ValueError(
                "No se pudo verificar la extracción completa. "
                f"Inicial: {total_antes}; "
                f"recibidos: {len(datos)}; "
                f"final: {total_despues}."
            )

        metadatos = consultar(
            session,
            URL_METADATA,
        )

    df = pd.DataFrame(datos)

    requeridas = {
        *CLAVES,
        *METRICAS,
        "nombre_del_departamento",
    }

    faltantes = requeridas - set(df.columns)

    if faltantes:
        raise ValueError(
            f"Faltan columnas: {sorted(faltantes)}"
        )

    RUTA_RAW.write_text(
        json.dumps(
            datos,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    RUTA_METADATA.write_text(
        json.dumps(
            metadatos,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    df.to_csv(
        RUTA_BRONZE,
        index=False,
        encoding="utf-8-sig",
    )

    reporte = diagnosticar(df)

    RUTA_DIAGNOSTICO.write_text(
        json.dumps(
            reporte,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    logger.info(
        "Filas bronze: %s",
        reporte["filas_bronze"],
    )

    logger.info(
        "Copias exactas adicionales: %s",
        reporte["copias_exactas_adicionales"],
    )

    logger.info(
        "Copias adicionales tras normalizar: %s",
        reporte["copias_adicionales_tras_normalizar"],
    )

    logger.info(
        "Filas con clave inválida: %s",
        reporte["filas_con_clave_invalida"],
    )

    logger.info(
        "Filas distintas con clave válida: %s",
        reporte["filas_distintas_con_clave_valida"],
    )

    logger.info(
        "Claves con varios registros: %s",
        reporte["claves_con_varios_registros"],
    )

    logger.info(
        "Claves con métricas distintas: %s",
        reporte["claves_con_metricas_distintas"],
    )

    logger.info(
        "Años observados: %s",
        reporte["anios_observados"],
    )

    logger.info(
        "Bronze guardado sin eliminar ni agregar registros"
    )

    return df


def ejecutar_bronze_matricula_departamental():
    try:
        return extraer_matricula_departamental()
    except Exception:
        logger.exception(
            "Falló bronze de matrícula departamental"
        )
        raise


if __name__ == "__main__":
    ejecutar_bronze_matricula_departamental()
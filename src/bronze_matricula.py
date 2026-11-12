import json

import pandas as pd
import requests

from src.config import (
    API_URL,
    BRONZE_MATRICULA,
    RAW_MATRICULA_API,
    RAW_MATRICULA_METADATA,
    crear_directorios,
)
from src.logger import logger


METADATA_URL = "https://www.datos.gov.co/api/views/y9ga-zwzy.json"
LIMITE = 50000


def consultar_json(session, url, parametros=None):
    respuesta = session.get(
        url,
        params=parametros,
        timeout=120,
    )
    respuesta.raise_for_status()
    return respuesta.json()


def consultar_total(session):
    resultado = consultar_json(
        session,
        API_URL,
        {"$select": "count(*) AS total"},
    )
    return int(resultado[0]["total"])


def extraer_matricula():
    crear_directorios()
    logger.info("Iniciando extracción de matrícula municipal")

    with requests.Session() as session:
        total_antes = consultar_total(session)

        if total_antes == 0:
            raise ValueError("La API no contiene registros.")

        if total_antes > LIMITE:
            raise ValueError(
                f"La API contiene {total_antes} registros. "
                "Se necesita implementar paginación."
            )

        datos = consultar_json(
            session,
            API_URL,
            {"$limit": LIMITE},
        )

        if not isinstance(datos, list):
            raise ValueError("La API no devolvió una lista de registros.")

        total_despues = consultar_total(session)

        if not (
            total_antes == total_despues == len(datos)
        ):
            raise ValueError(
                "No se pudo verificar la extracción completa. "
                f"Conteo inicial: {total_antes}; "
                f"recibidos: {len(datos)}; "
                f"conteo final: {total_despues}."
            )

        metadatos = consultar_json(session, METADATA_URL)

    df = pd.DataFrame(datos)

    requeridas = {
        "a_o",
        "c_digo_deldepartamento",
        "c_digo_delmunicipio",
        "tecnica_profesional",
        "tecnologica",
        "universitaria",
    }

    faltantes = requeridas - set(df.columns)

    if faltantes:
        raise ValueError(
            f"Faltan columnas esperadas: {sorted(faltantes)}"
        )

    RAW_MATRICULA_API.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    RAW_MATRICULA_METADATA.write_text(
        json.dumps(metadatos, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    df.to_csv(
        BRONZE_MATRICULA,
        index=False,
        encoding="utf-8-sig",
    )

    logger.info("Registros recibidos: %s", len(df))
    logger.info(
        "Duplicados exactos adicionales: %s",
        int(df.duplicated().sum()),
    )
    logger.info("Bronze generado: %s", BRONZE_MATRICULA.name)
    logger.info("No se eliminaron ni agregaron registros.")

    return df


def ejecutar_bronze_matricula():
    try:
        return extraer_matricula()
    except Exception:
        logger.exception("Falló la extracción de matrícula")
        raise


if __name__ == "__main__":
    ejecutar_bronze_matricula()
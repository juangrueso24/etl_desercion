import argparse
import sys
from time import perf_counter

from src.bronze import ejecutar_bronze
from src.bronze_matricula_departamental import (
    ejecutar_bronze_matricula_departamental,
)
from src.carga_dw import ejecutar_carga
from src.config import (
    BRONZE_DIR,
    GOLD_FINAL,
    RAW_DIR,
    crear_directorios,
)
from src.gold import ejecutar_gold
from src.indicadores import ejecutar_indicadores
from src.integracion import ejecutar_integracion
from src.logger import logger
from src.silver import ejecutar_silver
from src.silver_matricula_departamental import (
    ejecutar_silver_matricula_departamental,
)
from src.validacion import validar_gold


RUTA_EXCEL = (
    RAW_DIR / "articles-415244_recurso_19.xlsx"
)

RUTA_BRONZE_MATRICULA = (
    BRONZE_DIR / "bronze_matricula_departamental.csv"
)


def leer_argumentos():
    parser = argparse.ArgumentParser(
        description=(
            "Extracción desde Excel y API, transformación, "
            "integración e indicadores."
        )
    )

    parser.add_argument(
        "--actualizar-api",
        action="store_true",
        help=(
            "Descargar nuevamente el recurso departamental "
            "4hrb-y62g."
        ),
    )

    parser.add_argument(
        "--cargar",
        action="store_true",
        help="Validar Gold y cargarlo en PostgreSQL al terminar.",
    )

    return parser.parse_args()


def validar_entradas(actualizar_api):
    if not RUTA_EXCEL.is_file():
        raise FileNotFoundError(
            f"No se encontró el Excel: {RUTA_EXCEL}"
        )

    if (
        not actualizar_api
        and not RUTA_BRONZE_MATRICULA.is_file()
    ):
        raise FileNotFoundError(
            "No existe el bronze de matrícula departamental. "
            "Ejecuta main.py con --actualizar-api."
        )


def main():
    argumentos = leer_argumentos()
    inicio = perf_counter()

    crear_directorios()

    logger.info("=" * 65)
    logger.info("INICIO: EXCEL, API, TRANSFORMACIÓN E INDICADORES")
    logger.info("=" * 65)

    try:
        validar_entradas(argumentos.actualizar_api)

        logger.info("ETAPA 1/7: Excel y bronze de deserción")
        ejecutar_bronze()

        if argumentos.actualizar_api:
            logger.info(
                "ETAPA 2/7: Extracción de API departamental"
            )
            ejecutar_bronze_matricula_departamental()
        else:
            logger.info(
                "ETAPA 2/7: Reutilizando bronze "
                "departamental local"
            )

        logger.info("ETAPA 3/7: Silver de deserción")
        ejecutar_silver()

        logger.info(
            "ETAPA 4/7: Silver de matrícula departamental"
        )
        ejecutar_silver_matricula_departamental()

        logger.info("ETAPA 5/7: Integración")
        ejecutar_integracion()

        logger.info("ETAPA 6/7: Gold, variaciones y ranking")
        ejecutar_gold()

        logger.info("ETAPA 7/7: Indicadores de entrega")
        ejecutar_indicadores()

        if argumentos.cargar:
            logger.info("CARGA: validación de Gold y carga a PostgreSQL")
            validar_gold()
            ejecutar_carga()

    except Exception:
        logger.exception(
            "PIPELINE DETENIDO. No se completaron todas las etapas."
        )
        logger.error(
            "Pueden permanecer salidas anteriores; "
            "no deben presentarse como una nueva ejecución completa."
        )
        return 1

    logger.info("=" * 65)
    logger.info("PIPELINE FINALIZADO CORRECTAMENTE")
    logger.info(
        "Duración: %.2f segundos",
        perf_counter() - inicio,
    )
    logger.info("Gold final: %s", GOLD_FINAL)
    logger.info("Indicadores generados en data/gold")
    logger.info(
        "Cruce técnico realizado; comparabilidad "
        "metodológica no certificada."
    )
    if argumentos.cargar:
        logger.info("Gold cargado en PostgreSQL.")
    else:
        logger.info(
            "No se realizó carga a base de datos (usa --cargar)."
        )
    logger.info(
        "Ejecuta y guarda el notebook para actualizar evidencias."
    )
    logger.info("=" * 65)

    return 0


if __name__ == "__main__":
    sys.exit(main())
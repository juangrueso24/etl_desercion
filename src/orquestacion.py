# funciones que llama cada tarea del dag, usan los modulos de src

import json
import re
import shutil
from datetime import datetime, timezone

from src.bronze import (
    RUTA_EXCEL,
    RUTA_HOJA_EXTRAIDA,
    RUTA_TRAZABILIDAD,
    ejecutar_bronze,
)
from src.bronze_matricula_departamental import (
    RUTA_DIAGNOSTICO,
    RUTA_RAW,
    URL_DATOS,
    ejecutar_bronze_matricula_departamental,
)
from src.config import (
    BRONZE_DIR,
    GOLD_FINAL,
    SILVER_CALIDAD,
    SILVER_RESPALDOS_DIR,
)
from src.gold import RUTA_CALIDAD as GOLD_CALIDAD
from src.gold import RUTA_RESPALDOS as GOLD_RESPALDOS_DIR
from src.gold import ejecutar_gold
from src.indicadores import ejecutar_indicadores
from src.integracion import RUTA_CALIDAD as INTEGRACION_CALIDAD
from src.integracion import RUTA_INTEGRADO, ejecutar_integracion
from src.logger import logger
from src.silver import ejecutar_silver
from src.silver_matricula_departamental import (
    RUTA_CALIDAD as MATRICULA_CALIDAD,
)
from src.silver_matricula_departamental import (
    ejecutar_silver_matricula_departamental,
)

# carpeta del bronze de cada corrida
CORRIDAS_DIR = BRONZE_DIR / "corridas"

# respaldos que se guardan
RESPALDOS_A_CONSERVAR = 10


def _ahora_utc():
    return datetime.now(timezone.utc)


def _leer_json(ruta):
    return json.loads(ruta.read_text(encoding="utf-8"))


def _identificador_corrida():
    # run_id de airflow, o la fecha y hora si se corre sin airflow
    try:
        from airflow.sdk import get_current_context

        identificador = get_current_context()["run_id"]
    except Exception:
        identificador = _ahora_utc().strftime("%Y%m%d_%H%M%S")

    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(identificador))


def _carpeta_corrida():
    carpeta = CORRIDAS_DIR / _identificador_corrida()
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def _guardar_manifiesto(carpeta, nombre, datos):
    ruta = carpeta / nombre
    ruta.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return ruta


def _limpiar_respaldos(carpeta):
    if not carpeta.is_dir():
        return

    respaldos = sorted(carpeta.glob("*.csv"), key=lambda ruta: ruta.name)

    for antiguo in respaldos[:-RESPALDOS_A_CONSERVAR]:
        antiguo.unlink()
        logger.info("Respaldo antiguo eliminado: %s", antiguo.name)


def extraer_api_bronze():
    hora = _ahora_utc()
    bronze = ejecutar_bronze_matricula_departamental()

    diagnostico = _leer_json(RUTA_DIAGNOSTICO)
    carpeta = _carpeta_corrida()

    # copia de la respuesta de la api
    copia = carpeta / RUTA_RAW.name
    shutil.copy2(RUTA_RAW, copia)

    _guardar_manifiesto(
        carpeta,
        "manifiesto_api.json",
        {
            "fuente": "API REST datos.gov.co",
            "procedencia": URL_DATOS,
            "recurso": diagnostico["recurso"],
            "hora_utc": hora.isoformat(timespec="seconds"),
            "registros_recibidos": int(len(bronze)),
            "copias_exactas_adicionales": diagnostico[
                "copias_exactas_adicionales"
            ],
            "archivo_original_de_la_corrida": copia.name,
        },
    )

    logger.info(
        "Bronze API de la corrida: %s (%s registros, %s UTC)",
        carpeta.name,
        len(bronze),
        hora.strftime("%Y-%m-%d %H:%M:%S"),
    )

    return {
        "corrida": carpeta.name,
        "registros": int(len(bronze)),
        "ruta": str(copia),
    }


def extraer_excel_bronze():
    hora = _ahora_utc()
    bronze = ejecutar_bronze()

    trazabilidad = _leer_json(RUTA_TRAZABILIDAD)
    carpeta = _carpeta_corrida()

    # copia de la hoja leida
    copia = carpeta / RUTA_HOJA_EXTRAIDA.name
    shutil.copy2(RUTA_HOJA_EXTRAIDA, copia)

    # el excel no se copia, se guarda su sha256
    _guardar_manifiesto(
        carpeta,
        "manifiesto_excel.json",
        {
            "fuente": "Archivo Excel local",
            "procedencia": trazabilidad["ubicacion_original"],
            "hoja": trazabilidad["hoja"],
            "hora_utc": hora.isoformat(timespec="seconds"),
            "registros_extraidos": int(len(bronze)),
            "filas_por_nivel": trazabilidad["filas_por_nivel"],
            "sha256_excel": trazabilidad["sha256_excel"],
            "excel_original_sin_modificar": trazabilidad[
                "archivo_original_sin_modificar"
            ],
            "hoja_exportada_de_la_corrida": copia.name,
        },
    )

    logger.info(
        "Bronze Excel de la corrida: %s (%s registros, SHA-256 %s)",
        carpeta.name,
        len(bronze),
        trazabilidad["sha256_excel"][:12],
    )

    return {
        "corrida": carpeta.name,
        "registros": int(len(bronze)),
        "sha256_excel": trazabilidad["sha256_excel"],
    }


def transformar_silver():
    ejecutar_silver()
    ejecutar_silver_matricula_departamental()
    ejecutar_integracion()

    desercion = _leer_json(SILVER_CALIDAD)
    matricula = _leer_json(MATRICULA_CALIDAD)
    integracion = _leer_json(INTEGRACION_CALIDAD)

    logger.info(
        "Silver deserción: bronze=%s filas, silver=%s filas, "
        "claves duplicadas=%s",
        desercion["filas_bronze"],
        desercion["filas_silver"],
        desercion["claves_duplicadas"],
    )

    logger.info(
        "Silver matrícula: entrada=%s, copias eliminadas=%s, "
        "claves inválidas separadas=%s, salida=%s filas",
        matricula["filas_bronze"],
        matricula["copias_eliminadas_tras_normalizar"],
        matricula["filas_separadas_por_clave"],
        matricula["filas_silver"],
    )

    logger.info(
        "Integración: entrada=%s, salida=%s, con coincidencia=%s, "
        "sin coincidencia=%s",
        integracion["filas_desercion"],
        integracion["filas_integradas"],
        integracion["filas_con_coincidencia"],
        integracion["filas_sin_coincidencia"],
    )

    _limpiar_respaldos(SILVER_RESPALDOS_DIR)

    return {
        "silver_integrado": str(RUTA_INTEGRADO),
        "filas": int(integracion["filas_integradas"]),
    }


def construir_gold():
    ejecutar_gold()
    ejecutar_indicadores()

    reporte = _leer_json(GOLD_CALIDAD)

    logger.info(
        "Gold: %s filas, %s tasas disponibles, %s variaciones, "
        "%s selecciones top 20",
        reporte["filas_gold"],
        reporte["tasas_disponibles"],
        reporte["variaciones_anuales_calculadas"],
        reporte["filas_seleccionadas_top20"],
    )

    _limpiar_respaldos(GOLD_RESPALDOS_DIR)

    return {
        "gold_final": str(GOLD_FINAL),
        "filas": int(reporte["filas_gold"]),
    }


def validar_gold():
    from src.validacion import validar_gold as ejecutar_validacion

    return ejecutar_validacion()


def cargar_gold_postgres():
    from src.carga_dw import ejecutar_carga

    return ejecutar_carga(_identificador_corrida())

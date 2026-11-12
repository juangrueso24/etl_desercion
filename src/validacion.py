# validacion de la capa gold (tarea validate_gold)
# si falla una regla se lanza una excepcion y el dag se detiene

import json

import pandas as pd

from src.config import (
    ANIOS_ESPERADOS,
    GOLD_FINAL,
    NIVELES_ESPERADOS,
)
from src.gold import RUTA_CALIDAD, RUTA_TOP20, RUTA_VARIACIONES
from src.indicadores import RUTA_INDICADORES, RUTA_RESUMEN
from src.integracion import RUTA_INTEGRADO
from src.logger import logger


CLAVES = ["codigo_departamento", "nivel_formacion", "anio"]

COLUMNAS_GOLD_FINAL = {
    *CLAVES,
    "departamento",
    "tasa_desercion",
    "tasa_desercion_porcentaje",
    "estado_dato",
    "indicador",
    "matricula_reportada",
    "coincidio_matricula",
    "estado_integracion_matricula",
    "par_sin_alertas_tecnicas",
    "variacion_calculable",
    "es_top20_departamental",
}

COLUMNAS_INDICADORES = {
    "nivel_formacion",
    "anio",
    "departamentos_presentes",
    "departamentos_con_tasa",
    "coincidencias_matricula",
    "tasa_media_simple_pct",
    "cambio_anual_medio_pp",
    "disponibilidad_tasa_pct",
    "cobertura_cruce_pct",
}

ESTADOS_DATO = {"reportado", "sin_dato", "no_aplica"}


def _exigir(condicion, mensaje):
    if not condicion:
        logger.error("VALIDACIÓN FALLIDA: %s", mensaje)
        raise ValueError(f"Validación de Gold fallida: {mensaje}")


def _leer(ruta):
    return pd.read_csv(
        ruta,
        dtype="string",
        keep_default_na=False,
        encoding="utf-8-sig",
    )


def _numero(serie):
    texto = serie.astype("string").str.strip()

    return pd.to_numeric(
        texto.mask(texto.eq(""), pd.NA),
        errors="raise",
    ).astype("Float64")


def _verdadero(serie):
    return serie.astype("string").str.strip().str.lower().eq("true")


def validar_gold():
    logger.info("Iniciando validación de Gold")

    # archivos
    archivos = {
        "gold_final.csv": GOLD_FINAL,
        "gold_variaciones_anuales.csv": RUTA_VARIACIONES,
        "gold_top20_departamentos.csv": RUTA_TOP20,
        "gold_indicadores_por_nivel_anio.csv": RUTA_INDICADORES,
        "gold_resumen_calidad.csv": RUTA_RESUMEN,
        "calidad_gold.json": RUTA_CALIDAD,
        "silver_integrado.csv": RUTA_INTEGRADO,
    }

    ausentes = [
        nombre for nombre, ruta in archivos.items() if not ruta.is_file()
    ]

    if ausentes:
        logger.error("Archivos ausentes: %s", ausentes)
        raise FileNotFoundError(f"Faltan archivos de Gold: {ausentes}")

    logger.info("Existencia: %s archivos encontrados", len(archivos))

    gold = _leer(GOLD_FINAL)
    variaciones = _leer(RUTA_VARIACIONES)
    top20 = _leer(RUTA_TOP20)
    indicadores = _leer(RUTA_INDICADORES)
    resumen = _leer(RUTA_RESUMEN)
    silver = _leer(RUTA_INTEGRADO)
    calidad = json.loads(RUTA_CALIDAD.read_text(encoding="utf-8"))

    # esquema
    _exigir(not gold.empty, "gold_final.csv está vacío.")

    faltantes = COLUMNAS_GOLD_FINAL - set(gold.columns)
    _exigir(not faltantes, f"Faltan columnas en gold_final: {sorted(faltantes)}")

    faltantes = COLUMNAS_INDICADORES - set(indicadores.columns)
    _exigir(
        not faltantes,
        f"Faltan columnas en indicadores: {sorted(faltantes)}",
    )

    logger.info("Esquema: columnas esperadas presentes")

    # claves
    for nombre, tabla, claves in [
        ("gold_final", gold, CLAVES),
        ("gold_variaciones_anuales", variaciones, CLAVES),
        ("gold_top20_departamentos", top20, CLAVES),
        ("indicadores", indicadores, ["nivel_formacion", "anio"]),
        ("resumen", resumen, ["metrica"]),
    ]:
        vacias = tabla[claves].apply(lambda columna: columna.str.strip().eq(""))
        _exigir(
            not vacias.any(axis=None),
            f"Hay claves nulas o vacías en {nombre}.",
        )

        duplicados = int(tabla.duplicated(subset=claves).sum())
        _exigir(
            duplicados == 0,
            f"{nombre} tiene {duplicados} claves duplicadas ({claves}).",
        )

    logger.info("Claves: sin nulos y sin duplicados en las 5 tablas")

    # rangos y estados
    tasa = _numero(gold["tasa_desercion"])
    porcentaje = _numero(gold["tasa_desercion_porcentaje"])
    matricula = _numero(gold["matricula_reportada"])

    _exigir(
        not (tasa.notna() & ~tasa.between(0, 1)).any(),
        "Hay tasas fuera del rango 0–1.",
    )
    _exigir(
        not (porcentaje.notna() & ~porcentaje.between(0, 100)).any(),
        "Hay porcentajes fuera del rango 0–100.",
    )
    _exigir(not matricula.lt(0).any(), "Hay matrículas negativas.")
    _exigir(
        set(gold["estado_dato"]) <= ESTADOS_DATO,
        "Hay estados de dato no reconocidos.",
    )

    logger.info("Rangos: tasas, porcentajes y matrículas en rango")

    # consistencia entre capas
    filas = len(gold)
    tasas_disponibles = int(tasa.notna().sum())
    coincidencias = int(_verdadero(gold["coincidio_matricula"]).sum())

    _exigir(
        len(silver) == filas,
        f"Silver integrado tiene {len(silver)} filas y Gold {filas}.",
    )
    _exigir(
        int(calidad["filas_gold"]) == filas,
        "calidad_gold.json no coincide con gold_final.csv.",
    )

    resumen_valores = dict(
        zip(resumen["metrica"], _numero(resumen["valor"]))
    )

    _exigir(
        resumen_valores.get("observaciones_gold") == filas,
        "gold_resumen_calidad no coincide en observaciones_gold.",
    )
    _exigir(
        resumen_valores.get("tasas_disponibles") == tasas_disponibles,
        "gold_resumen_calidad no coincide en tasas_disponibles.",
    )

    esperados = {
        (nivel, int(anio))
        for nivel in NIVELES_ESPERADOS
        for anio in ANIOS_ESPERADOS
    }
    observados = set(
        zip(
            indicadores["nivel_formacion"],
            _numero(indicadores["anio"]).astype(int),
        )
    )

    _exigir(
        observados == esperados,
        "Los indicadores no cubren todos los niveles y años esperados.",
    )

    for columna, esperado in [
        ("departamentos_presentes", filas),
        ("departamentos_con_tasa", tasas_disponibles),
        ("coincidencias_matricula", coincidencias),
    ]:
        suma = int(_numero(indicadores[columna]).sum())
        _exigir(
            suma == esperado,
            f"La suma de {columna} es {suma} y Gold indica {esperado}.",
        )

    _exigir(
        len(variaciones)
        == int(_verdadero(gold["variacion_calculable"]).sum()),
        "gold_variaciones_anuales no coincide con las variaciones de Gold.",
    )
    _exigir(
        len(top20)
        == int(_verdadero(gold["es_top20_departamental"]).sum()),
        "gold_top20_departamentos no coincide con el ranking de Gold.",
    )

    logger.info("Consistencia: Silver, Gold e indicadores coinciden")

    logger.info("Registros en Gold final: %s", filas)
    logger.info("Registros duplicados detectados: 0")
    logger.info("Indicadores por nivel y año: %s filas", len(indicadores))
    logger.info("Validación de Gold exitosa")

    return {
        "gold_final": str(GOLD_FINAL),
        "filas_gold": int(filas),
        "filas_indicadores": int(len(indicadores)),
        "duplicados": 0,
    }


if __name__ == "__main__":
    validar_gold()

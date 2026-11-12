import csv
import hashlib
import json

import pandas as pd

from src.config import (
    ANIOS_ESPERADOS,
    BRONZE_DESERCION,
    BRONZE_DIR,
    BRONZE_NOTAS,
    NIVELES_ESPERADOS,
    RAW_DIR,
    crear_directorios,
)
from src.logger import logger
from src.utils import normalizar_texto


RUTA_EXCEL = RAW_DIR / "articles-415244_recurso_19.xlsx"

HOJA_EXCEL = "TD - departamento"

RUTA_HOJA_EXTRAIDA = (
    BRONZE_DIR / "excel_extraido" / "td_departamento.csv"
)

RUTA_TRAZABILIDAD = (
    BRONZE_DIR / "trazabilidad_excel.json"
)


def calcular_sha256(ruta):
    huella = hashlib.sha256()

    with ruta.open("rb") as archivo:
        for bloque in iter(
            lambda: archivo.read(1024 * 1024),
            b"",
        ):
            huella.update(bloque)

    return huella.hexdigest()


def texto_celda(valor):
    if pd.isna(valor):
        return ""

    if isinstance(valor, (int, float)):
        numero = float(valor)

        if numero.is_integer():
            return str(int(numero))

    return str(valor).strip()


def extraer_desercion_departamento():
    crear_directorios()

    if not RUTA_EXCEL.is_file():
        raise FileNotFoundError(
            f"No se encontró el Excel original: {RUTA_EXCEL}"
        )

    logger.info(
        "Leyendo Excel original: %s",
        RUTA_EXCEL.name,
    )

    huella_inicial = calcular_sha256(RUTA_EXCEL)

    with pd.ExcelFile(
        RUTA_EXCEL,
        engine="openpyxl",
    ) as libro:
        if HOJA_EXCEL not in libro.sheet_names:
            raise ValueError(
                f"No existe la hoja {HOJA_EXCEL!r}. "
                f"Hojas disponibles: {libro.sheet_names}"
            )

        tabla = pd.read_excel(
            libro,
            sheet_name=HOJA_EXCEL,
            header=None,
            dtype=object,
            keep_default_na=False,
        )

    if tabla.empty:
        raise ValueError("La hoja seleccionada está vacía.")

    huella_final = calcular_sha256(RUTA_EXCEL)

    if huella_inicial != huella_final:
        raise ValueError(
            "El Excel cambió durante la lectura."
        )

    RUTA_HOJA_EXTRAIDA.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tabla.to_csv(
        RUTA_HOJA_EXTRAIDA,
        index=False,
        header=False,
        encoding="utf-8-sig",
        quoting=csv.QUOTE_MINIMAL,
    )

    registros = []
    notas = []
    niveles_detectados = []

    nivel_actual = None
    posiciones_anios = None
    columna_departamento = None

    niveles_por_clave = {
        normalizar_texto(nivel): nivel
        for nivel in NIVELES_ESPERADOS
    }

    for numero_fila, valores in enumerate(
        tabla.itertuples(index=False, name=None),
        start=1,
    ):
        fila = [texto_celda(valor) for valor in valores]

        posiciones_con_texto = [
            indice
            for indice, valor in enumerate(fila)
            if valor
        ]

        if not posiciones_con_texto:
            continue

        primera_posicion = posiciones_con_texto[0]
        primera = fila[primera_posicion]
        texto = normalizar_texto(primera)

        prefijo = "NIVEL DE FORMACION "

        if texto.startswith(prefijo):
            nombre_nivel = texto[len(prefijo):].strip()
            nivel_actual = niveles_por_clave.get(nombre_nivel)

            if nivel_actual is None:
                raise ValueError(
                    f"Nivel no reconocido en fila Excel "
                    f"{numero_fila}: {primera}"
                )

            niveles_detectados.append(nivel_actual)
            posiciones_anios = None
            columna_departamento = None
            continue

        if texto.startswith("DEPARTAMENTO DE OFERTA"):
            if nivel_actual is None:
                raise ValueError(
                    f"Encabezado sin nivel en fila {numero_fila}."
                )

            posiciones_anios = {
                valor: indice
                for indice, valor in enumerate(fila)
                if valor in ANIOS_ESPERADOS
            }

            if set(posiciones_anios) != set(ANIOS_ESPERADOS):
                raise ValueError(
                    f"Años incompletos para {nivel_actual}."
                )

            columna_departamento = primera_posicion
            continue

        if texto.startswith(
            ("NA:", "NOTA:", "FUENTE:", "CORTE DE")
        ):
            notas.append({
                "fila_excel": numero_fila,
                "texto": primera,
            })

            if texto.startswith(("NA:", "NOTA:")):
                posiciones_anios = None
                columna_departamento = None

            continue

        if (
            nivel_actual is None
            or posiciones_anios is None
            or columna_departamento is None
        ):
            notas.append({
                "fila_excel": numero_fila,
                "texto": primera,
            })
            continue

        departamento = fila[columna_departamento]

        if not departamento:
            continue

        registro = {
            "nivel_formacion": nivel_actual,
            "departamento_original": departamento,
        }

        for anio in ANIOS_ESPERADOS:
            registro[anio] = fila[posiciones_anios[anio]]

        # Corresponde a la fila de Excel y a la fila lógica
        # de la hoja exportada sin encabezado adicional.
        registro["linea_origen"] = numero_fila

        registros.append(registro)

    if (
        len(niveles_detectados) != len(NIVELES_ESPERADOS)
        or set(niveles_detectados) != set(NIVELES_ESPERADOS)
    ):
        raise ValueError(
            f"Bloques encontrados: {niveles_detectados}"
        )

    bronze = pd.DataFrame(registros)

    if bronze.empty:
        raise ValueError(
            "No se extrajeron registros departamentales."
        )

    conteos = bronze.groupby("nivel_formacion").size()

    if set(conteos.index) != set(NIVELES_ESPERADOS):
        raise ValueError("Hay bloques sin registros.")

    bronze.to_csv(
        BRONZE_DESERCION,
        index=False,
        encoding="utf-8-sig",
    )

    BRONZE_NOTAS.write_text(
        json.dumps(
            notas,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    trazabilidad = {
        "archivo_original": RUTA_EXCEL.name,
        "ubicacion_original": (
            f"data/raw/{RUTA_EXCEL.name}"
        ),
        "sha256_excel": huella_inicial,
        "hoja": HOJA_EXCEL,
        "hoja_extraida": (
            "data/bronze/excel_extraido/td_departamento.csv"
        ),
        "archivo_bronze": BRONZE_DESERCION.name,
        "filas_extraidas": int(len(bronze)),
        "filas_por_nivel": {
            nivel: int(cantidad)
            for nivel, cantidad in conteos.items()
        },
        "significado_linea_origen": (
            "Número de fila de la hoja Excel. "
            "La exportación CSV conserva el orden de filas."
        ),
        "archivo_original_sin_modificar": True,
    }

    RUTA_TRAZABILIDAD.write_text(
        json.dumps(
            trazabilidad,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    logger.info("Hoja leída: %s", HOJA_EXCEL)
    logger.info(
        "Hoja exportada: %s",
        RUTA_HOJA_EXTRAIDA,
    )
    logger.info(
        "Bronze generado: %s",
        BRONZE_DESERCION.name,
    )
    logger.info("Filas extraídas: %s", len(bronze))
    logger.info(
        "Filas por nivel:\n%s",
        conteos.to_string(),
    )
    logger.info(
        "Excel original conservado sin modificar"
    )

    return bronze


def ejecutar_bronze():
    try:
        return extraer_desercion_departamento()
    except Exception:
        logger.exception(
            "Falló la extracción bronze desde Excel"
        )
        raise


if __name__ == "__main__":
    ejecutar_bronze()
import json

import pandas as pd

from src.config import (
    SILVER_DESERCION,
    SILVER_DIR,
    crear_directorios,
)
from src.logger import logger
from src.utils import normalizar_texto


RUTA_MATRICULA = (
    SILVER_DIR / "silver_matricula_departamental.csv"
)

RUTA_INTEGRADO = (
    SILVER_DIR / "silver_integrado.csv"
)

RUTA_CALIDAD = (
    SILVER_DIR / "calidad_integracion.json"
)

RUTA_SIN_CORRESPONDENCIA = (
    SILVER_DIR / "desercion_territorios_sin_correspondencia.csv"
)

# Correspondencias construidas con el catálogo observado.
DEPARTAMENTOS = {
    "05": "ANTIOQUIA",
    "08": "ATLANTICO",
    "11": "BOGOTA D.C.",
    "13": "BOLIVAR",
    "15": "BOYACA",
    "17": "CALDAS",
    "18": "CAQUETA",
    "19": "CAUCA",
    "20": "CESAR",
    "23": "CORDOBA",
    "25": "CUNDINAMARCA",
    "27": "CHOCO",
    "41": "HUILA",
    "44": "LA GUAJIRA",
    "47": "MAGDALENA",
    "50": "META",
    "52": "NARINO",
    "54": "NORTE DE SANTANDER",
    "63": "QUINDIO",
    "66": "RISARALDA",
    "68": "SANTANDER",
    "70": "SUCRE",
    "73": "TOLIMA",
    "76": "VALLE DEL CAUCA",
    "81": "ARAUCA",
    "85": "CASANARE",
    "86": "PUTUMAYO",
    "88": (
        "ARCHIPIELAGO DE SAN ANDRES, "
        "PROVIDENCIA Y SANTA CATALINA"
    ),
    "91": "AMAZONAS",
    "94": "GUAINIA",
    "95": "GUAVIARE",
    "97": "VAUPES",
    "99": "VICHADA",
}

ALIAS = {
    "BOGOTA D.C": "BOGOTA D.C.",
    "BOGOTA, D.C.": "BOGOTA D.C.",
    "GUAJIRA": "LA GUAJIRA",
    "NARINIO": "NARINO",
    "SAN ANDRES Y PROVIDENCIA": DEPARTAMENTOS["88"],
    "SAN ANDRES Y PROVI": DEPARTAMENTOS["88"],
    "ARCHIPIELAGO DE SA": DEPARTAMENTOS["88"],
}


def nombre_canonico(valor):
    texto = normalizar_texto(valor)

    if pd.isna(texto):
        return pd.NA

    return ALIAS.get(texto, texto)


def leer_booleano(serie, nombre):
    resultado = (
        serie.astype("string")
        .str.strip()
        .str.lower()
        .map({"true": True, "false": False})
    )

    if resultado.isna().any():
        raise ValueError(
            f"Valores booleanos no reconocidos en {nombre}."
        )

    return resultado.astype(bool)


def construir_integracion():
    crear_directorios()

    for ruta in [SILVER_DESERCION, RUTA_MATRICULA]:
        if not ruta.is_file():
            raise FileNotFoundError(
                f"No se encontró la entrada: {ruta}"
            )

    logger.info("Iniciando integración departamental")

    desercion = pd.read_csv(
        SILVER_DESERCION,
        encoding="utf-8-sig",
        dtype="string",
        keep_default_na=False,
    )

    matricula = pd.read_csv(
        RUTA_MATRICULA,
        encoding="utf-8-sig",
        dtype="string",
        keep_default_na=False,
    )

    requeridas_desercion = {
        "departamento",
        "departamento_clave",
        "nivel_formacion",
        "anio",
        "tasa_desercion",
        "estado_dato",
    }

    requeridas_matricula = {
        "codigo_departamento",
        "departamento_matricula",
        "nivel_formacion",
        "anio",
        "matricula_reportada",
        "estado_matricula",
        "requiere_revision",
        "fuente_recurso",
    }

    for nombre, datos, requeridas in [
        ("deserción", desercion, requeridas_desercion),
        ("matrícula", matricula, requeridas_matricula),
    ]:
        faltantes = requeridas - set(datos.columns)

        if faltantes:
            raise ValueError(
                f"Faltan columnas en {nombre}: "
                f"{sorted(faltantes)}"
            )

        if datos.empty:
            raise ValueError(
                f"La fuente de {nombre} está vacía."
            )

    filas_desercion = len(desercion)

    codigo_por_nombre = {
        nombre: codigo
        for codigo, nombre in DEPARTAMENTOS.items()
    }

    desercion["departamento_canonico"] = (
        desercion["departamento"].map(nombre_canonico)
    )

    desercion["codigo_departamento"] = (
        desercion["departamento_canonico"]
        .map(codigo_por_nombre)
        .astype("string")
    )

    sin_correspondencia = desercion.loc[
        desercion["codigo_departamento"].isna()
    ].copy()

    sin_correspondencia.to_csv(
        RUTA_SIN_CORRESPONDENCIA,
        index=False,
        encoding="utf-8-sig",
    )

    if not sin_correspondencia.empty:
        nombres = (
            sin_correspondencia["departamento"]
            .drop_duplicates()
            .tolist()
        )

        raise ValueError(
            "Hay territorios de deserción sin correspondencia. "
            f"Revisar: {nombres}"
        )

    matricula["codigo_departamento"] = (
        matricula["codigo_departamento"]
        .str.strip()
        .str.zfill(2)
    )

    matricula["departamento_canonico_matricula"] = (
        matricula["codigo_departamento"].map(DEPARTAMENTOS)
    )

    nombre_matricula_normalizado = (
        matricula["departamento_matricula"]
        .map(nombre_canonico)
    )

    nombre_inconsistente = (
        matricula["departamento_canonico_matricula"].isna()
        | nombre_matricula_normalizado.ne(
            matricula["departamento_canonico_matricula"]
        ).fillna(True)
    )

    if nombre_inconsistente.any():
        ejemplos = matricula.loc[
            nombre_inconsistente,
            ["codigo_departamento", "departamento_matricula"],
        ].drop_duplicates()

        raise ValueError(
            "Hay nombres incompatibles con el catálogo:\n"
            f"{ejemplos.to_string(index=False)}"
        )

    matricula["alerta_revision_silver_origen"] = (
        leer_booleano(
            matricula["requiere_revision"],
            "requiere_revision",
        )
    )

    for datos in [desercion, matricula]:
        datos["anio"] = pd.to_numeric(
            datos["anio"],
            errors="raise",
        ).astype("Int64")

    for datos, columna in [
        (desercion, "tasa_desercion"),
        (matricula, "matricula_reportada"),
    ]:
        texto = datos[columna].str.strip()

        datos[columna] = pd.to_numeric(
            texto.mask(texto.eq(""), pd.NA),
            errors="raise",
        ).astype("Float64")

    claves = [
        "codigo_departamento",
        "nivel_formacion",
        "anio",
    ]

    for nombre, datos in [
        ("deserción", desercion),
        ("matrícula", matricula),
    ]:
        if datos.duplicated(subset=claves).any():
            raise ValueError(
                f"Claves duplicadas en {nombre}. "
                "El cruce se ha detenido."
            )

    columnas_matricula = [
        *claves,
        "departamento_matricula",
        "matricula_reportada",
        "estado_matricula",
        "alerta_revision_silver_origen",
        "fuente_recurso",
    ]

    integrado = desercion.merge(
        matricula[columnas_matricula],
        on=claves,
        how="left",
        validate="one_to_one",
        indicator="_resultado_cruce",
    )

    if len(integrado) != filas_desercion:
        raise ValueError(
            "El cruce cambió la cantidad de filas de deserción."
        )

    integrado["coincidio_matricula"] = (
        integrado["_resultado_cruce"].eq("both")
    )

    anios_matricula = set(
        matricula["anio"].dropna().astype(int)
    )

    niveles_matricula = set(
        matricula["nivel_formacion"].unique()
    )

    estado = pd.Series(
        "SIN_COINCIDENCIA",
        index=integrado.index,
        dtype="string",
    )

    coincide = integrado["coincidio_matricula"]

    estado.loc[
        ~integrado["anio"].isin(anios_matricula)
    ] = "FUERA_COBERTURA_TEMPORAL"

    estado.loc[
        ~integrado["nivel_formacion"].isin(niveles_matricula)
    ] = "NIVEL_SIN_EQUIVALENCIA_DEFINIDA"

    estado.loc[coincide] = "COINCIDENCIA_TECNICA"

    estado.loc[
        coincide
        & integrado["estado_matricula"].ne("reportado")
    ] = "MATRICULA_POR_REVISAR"

    integrado["estado_integracion_matricula"] = estado

    integrado["alerta_revision_silver_origen"] = (
        integrado["alerta_revision_silver_origen"]
        .astype("boolean")
    )

    integrado["requiere_revision_matricula"] = (
        coincide
        & integrado["estado_matricula"].ne("reportado")
    ).fillna(False)

    integrado = integrado.drop(
        columns="_resultado_cruce"
    ).sort_values(
        ["nivel_formacion", "codigo_departamento", "anio"]
    ).reset_index(drop=True)

    reporte = {
        "filas_desercion": int(filas_desercion),
        "filas_integradas": int(len(integrado)),
        "filas_con_coincidencia": int(
            integrado["coincidio_matricula"].sum()
        ),
        "filas_sin_coincidencia": int(
            (~integrado["coincidio_matricula"]).sum()
        ),
        "filas_matricula_por_revisar": int(
            integrado["requiere_revision_matricula"].sum()
        ),
        "claves_duplicadas": int(
            integrado.duplicated(subset=claves).sum()
        ),
        "estados_integracion": {
            estado: int(cantidad)
            for estado, cantidad in (
                integrado["estado_integracion_matricula"]
                .value_counts()
                .items()
            )
        },
        "recurso_matricula": "4hrb-y62g",
        "regla_cruce": (
            "Código de departamento + nivel de formación + año. "
            "Se conservan todas las observaciones de deserción."
        ),
        "advertencias": [
            (
                "La coincidencia técnica no demuestra "
                "equivalencia de las poblaciones estadísticas."
            ),
            (
                "No usar la matrícula como denominador "
                "de la tasa de deserción sin verificar "
                "la metodología de ambas fuentes."
            ),
            (
                "No se calcula matrícula TyT "
                "mediante suma de otros niveles."
            ),
            (
                "Las variantes territoriales conocidas "
                "se resuelven mediante el catálogo por código."
            ),
            (
                "Los valores decimales permanecen "
                "marcados para revisión."
            ),
            (
                "La nota sobre exclusión del SENA desde 2019 "
                "en deserción tecnológica sigue vigente; "
                "no se supone el mismo ajuste en matrícula."
            ),
        ],
    }

    integrado.to_csv(
        RUTA_INTEGRADO,
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

    logger.info(
        "Filas de deserción conservadas: %s",
        len(integrado),
    )

    logger.info(
        "Filas con coincidencia de matrícula: %s",
        reporte["filas_con_coincidencia"],
    )

    logger.info(
        "Filas sin coincidencia: %s",
        reporte["filas_sin_coincidencia"],
    )

    logger.info(
        "Matrícula por revisar en el cruce: %s",
        reporte["filas_matricula_por_revisar"],
    )

    logger.info(
        "Estados de integración: %s",
        reporte["estados_integracion"],
    )

    logger.info(
        "Integración guardada: %s",
        RUTA_INTEGRADO.name,
    )

    return integrado


def ejecutar_integracion():
    try:
        return construir_integracion()
    except Exception:
        logger.exception("Falló la integración")
        raise


if __name__ == "__main__":
    ejecutar_integracion()
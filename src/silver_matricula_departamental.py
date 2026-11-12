import json

import pandas as pd

from src.config import (
    BRONZE_DIR,
    SILVER_DIR,
    crear_directorios,
)
from src.logger import logger
from src.utils import normalizar_texto


RUTA_BRONZE = (
    BRONZE_DIR / "bronze_matricula_departamental.csv"
)

RUTA_SILVER = (
    SILVER_DIR / "silver_matricula_departamental.csv"
)

RUTA_RECHAZADOS = (
    SILVER_DIR / "matricula_departamental_claves_invalidas.csv"
)

RUTA_REVISION = (
    SILVER_DIR / "matricula_departamental_por_revisar.csv"
)

RUTA_CALIDAD = (
    SILVER_DIR / "calidad_matricula_departamental.json"
)

MAPA_NIVELES = {
    "tecnica_profesional": "Técnico Profesional",
    "tecnologica": "Tecnológico",
    "universitaria": "Universitario",
}

CLAVES_FUENTE = [
    "a_o",
    "c_digo_deldepartamento",
]


def transformar_matricula_departamental():
    crear_directorios()

    if not RUTA_BRONZE.is_file():
        raise FileNotFoundError(
            f"No se encontró el bronze: {RUTA_BRONZE}"
        )

    logger.info("Iniciando silver de matrícula departamental")

    df = pd.read_csv(
        RUTA_BRONZE,
        dtype="string",
        keep_default_na=False,
        encoding="utf-8-sig",
    )

    requeridas = {
        *CLAVES_FUENTE,
        "nombre_del_departamento",
        *MAPA_NIVELES,
    }

    faltantes = requeridas - set(df.columns)

    if faltantes:
        raise ValueError(
            f"Faltan columnas: {sorted(faltantes)}"
        )

    if df.empty:
        raise ValueError("El archivo bronze está vacío.")

    filas_originales = len(df)

    for columna in df.columns:
        df[columna] = df[columna].str.strip()

    df["nombre_del_departamento"] = (
        df["nombre_del_departamento"].map(normalizar_texto)
    )

    df = df.drop_duplicates().reset_index(drop=True)

    copias_normalizacion = filas_originales - len(df)

    codigo = df["c_digo_deldepartamento"]

    codigo_valido = (
        codigo.str.fullmatch(r"[0-9]{1,2}")
        .fillna(False)
    )

    anios = pd.to_numeric(
        df["a_o"],
        errors="coerce",
    )

    anio_valido = (
        anios.notna()
        & anios.between(1900, 2100)
        & anios.mod(1).eq(0)
    ).fillna(False)

    clave_valida = codigo_valido & anio_valido

    rechazados = df.loc[~clave_valida].copy()

    motivos = pd.Series(
        "",
        index=df.index,
        dtype="string",
    )

    motivos.loc[~codigo_valido] = (
        "CODIGO_DEPARTAMENTO_INVALIDO"
    )

    motivos.loc[
        codigo_valido & ~anio_valido
    ] = "ANIO_INVALIDO"

    rechazados["motivo_revision"] = motivos.loc[
        rechazados.index
    ]

    rechazados.to_csv(
        RUTA_RECHAZADOS,
        index=False,
        encoding="utf-8-sig",
    )

    df = df.loc[clave_valida].copy()

    if df.empty:
        raise ValueError(
            "No quedaron registros con claves válidas."
        )

    df["c_digo_deldepartamento"] = (
        df["c_digo_deldepartamento"].str.zfill(2)
    )

    df["a_o"] = anios.loc[df.index].astype("Int64")

    antes_deduplicacion_final = len(df)

    df = df.drop_duplicates().reset_index(drop=True)

    copias_adicionales = (
        antes_deduplicacion_final - len(df)
    )

    duplicadas = df.duplicated(
        subset=CLAVES_FUENTE,
        keep=False,
    )

    if duplicadas.any():
        ejemplos = df.loc[
            duplicadas,
            [
                *CLAVES_FUENTE,
                "nombre_del_departamento",
                *MAPA_NIVELES,
            ],
        ].head(10)

        raise ValueError(
            "Existen registros distintos para departamento y año:\n"
            f"{ejemplos.to_string(index=False)}"
        )

    filas_departamento_anio = len(df)

    nombres_por_codigo = (
        df.groupby("c_digo_deldepartamento")[
            "nombre_del_departamento"
        ]
        .nunique(dropna=False)
    )

    codigos_con_varios_nombres = (
        nombres_por_codigo[
            nombres_por_codigo.gt(1)
        ].index.tolist()
    )

    silver = df.melt(
        id_vars=[
            "a_o",
            "c_digo_deldepartamento",
            "nombre_del_departamento",
        ],
        value_vars=list(MAPA_NIVELES),
        var_name="campo_fuente",
        value_name="matricula_original",
    )

    silver = silver.rename(columns={
        "a_o": "anio",
        "c_digo_deldepartamento": "codigo_departamento",
        "nombre_del_departamento": "departamento_matricula",
    })

    silver["nivel_formacion"] = (
        silver["campo_fuente"].map(MAPA_NIVELES)
    )

    texto = silver["matricula_original"].str.strip()
    vacios = texto.eq("")

    numeros = pd.to_numeric(
        texto.mask(vacios, pd.NA),
        errors="coerce",
    ).astype("Float64")

    invalidos = (
        (~vacios & numeros.isna())
        | numeros.lt(0)
        | numeros.isin([float("inf"), float("-inf")])
    ).fillna(False)

    if invalidos.any():
        ejemplos = silver.loc[
            invalidos,
            [
                "anio",
                "codigo_departamento",
                "nivel_formacion",
                "matricula_original",
            ],
        ].head(10)

        raise ValueError(
            "Hay valores de matrícula no válidos:\n"
            f"{ejemplos.to_string(index=False)}"
        )

    decimales = (
        numeros.notna()
        & numeros.mod(1).ne(0)
    ).fillna(False)

    silver["matricula_reportada"] = numeros

    silver["estado_matricula"] = "reportado"
    silver.loc[vacios, "estado_matricula"] = "sin_dato"
    silver.loc[
        decimales,
        "estado_matricula",
    ] = "decimal_por_revisar"

    nombre_invalido = (
        silver["departamento_matricula"].eq("")
        | silver["departamento_matricula"].isna()
    )

    nombre_variable = silver["codigo_departamento"].isin(
        codigos_con_varios_nombres
    )

    silver["requiere_revision"] = (
        vacios
        | decimales
        | nombre_invalido
        | nombre_variable
    )

    silver["fuente_recurso"] = "4hrb-y62g"

    claves_silver = [
        "codigo_departamento",
        "nivel_formacion",
        "anio",
    ]

    if silver.duplicated(subset=claves_silver).any():
        raise ValueError(
            "Se generaron claves duplicadas en silver."
        )

    filas_esperadas = (
        filas_departamento_anio * len(MAPA_NIVELES)
    )

    if len(silver) != filas_esperadas:
        raise ValueError(
            "El número de filas no coincide con la "
            "transformación de niveles."
        )

    reconciliadas = (
        copias_normalizacion
        + len(rechazados)
        + copias_adicionales
        + filas_departamento_anio
    )

    if reconciliadas != filas_originales:
        raise ValueError(
            "Los conteos de limpieza no cuadran."
        )

    columnas = [
        "codigo_departamento",
        "departamento_matricula",
        "nivel_formacion",
        "anio",
        "matricula_reportada",
        "estado_matricula",
        "requiere_revision",
        "matricula_original",
        "campo_fuente",
        "fuente_recurso",
    ]

    silver = silver[columnas].sort_values(
        [
            "codigo_departamento",
            "nivel_formacion",
            "anio",
        ]
    ).reset_index(drop=True)

    por_revisar = silver.loc[
        silver["requiere_revision"]
    ].copy()

    reporte = {
        "recurso": "4hrb-y62g",
        "filas_bronze": int(filas_originales),
        "copias_eliminadas_tras_normalizar": int(
            copias_normalizacion
        ),
        "filas_separadas_por_clave": int(
            len(rechazados)
        ),
        "copias_adicionales_tras_tipificar_claves": int(
            copias_adicionales
        ),
        "filas_departamento_anio": int(
            filas_departamento_anio
        ),
        "filas_silver": int(len(silver)),
        "filas_sin_matricula": int(
            silver["matricula_reportada"].isna().sum()
        ),
        "filas_con_decimales": int(decimales.sum()),
        "filas_por_revisar": int(len(por_revisar)),
        "claves_duplicadas": 0,
        "anio_minimo": int(silver["anio"].min()),
        "anio_maximo": int(silver["anio"].max()),
        "codigos_con_varios_nombres": (
            codigos_con_varios_nombres
        ),
        "conteos_reconciliados": True,
        "niveles_generados": list(MAPA_NIVELES.values()),
        "advertencias": [
            "No se genera matrícula TyT.",
            "No se suman matrículas entre niveles.",
            "Los faltantes no se convierten en cero.",
            "Los decimales se conservan y se marcan.",
            (
                "La comparabilidad con deserción debe "
                "documentarse antes del análisis integrado."
            ),
        ],
    }

    silver.to_csv(
        RUTA_SILVER,
        index=False,
        encoding="utf-8-sig",
    )

    por_revisar.to_csv(
        RUTA_REVISION,
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

    logger.info("Filas bronze: %s", filas_originales)
    logger.info(
        "Copias eliminadas: %s",
        copias_normalizacion,
    )
    logger.info(
        "Registros separados por clave inválida: %s",
        len(rechazados),
    )
    logger.info(
        "Filas departamento + año: %s",
        filas_departamento_anio,
    )
    logger.info("Filas silver: %s", len(silver))
    logger.info(
        "Filas sin matrícula: %s",
        reporte["filas_sin_matricula"],
    )
    logger.info(
        "Filas con decimales: %s",
        reporte["filas_con_decimales"],
    )
    logger.info(
        "Filas por revisar: %s",
        len(por_revisar),
    )
    logger.info(
        "Códigos con varios nombres: %s",
        codigos_con_varios_nombres,
    )
    logger.info(
        "Años disponibles: %s–%s",
        reporte["anio_minimo"],
        reporte["anio_maximo"],
    )

    catalogo = (
        silver[
            [
                "codigo_departamento",
                "departamento_matricula",
            ]
        ]
        .drop_duplicates()
        .sort_values("codigo_departamento")
    )

    logger.info(
        "Catálogo territorial observado:\n%s",
        catalogo.to_string(index=False),
    )

    logger.info(
        "Silver departamental finalizado. "
        "No se sumaron matrículas."
    )

    return silver


def ejecutar_silver_matricula_departamental():
    try:
        return transformar_matricula_departamental()
    except Exception:
        logger.exception(
            "Falló silver de matrícula departamental"
        )
        raise


if __name__ == "__main__":
    ejecutar_silver_matricula_departamental()
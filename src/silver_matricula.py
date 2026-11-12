import json

import pandas as pd

from src.config import (
    BRONZE_MATRICULA,
    SILVER_DIR,
    SILVER_MATRICULA,
    SILVER_MATRICULA_CALIDAD,
    SILVER_MATRICULA_REVISION,
    crear_directorios,
)
from src.logger import logger
from src.utils import normalizar_texto


CLAVES = [
    "a_o",
    "c_digo_deldepartamento",
    "c_digo_delmunicipio",
]

COLUMNAS_NUMERICAS = [
    "tecnica_profesional",
    "tecnologica",
    "universitaria",
    "especializacion",
    "maestria",
    "doctorado",
    "ies_con_oferta",
]

RUTA_CODIGOS_INVALIDOS = (
    SILVER_DIR / "matricula_codigos_invalidos.csv"
)


def separar_codigos_invalidos(df):
    df = df.copy()

    departamento = df["c_digo_deldepartamento"].str.strip()
    municipio = df["c_digo_delmunicipio"].str.strip()

    departamento_valido = (
        departamento.str.fullmatch(r"[0-9]{1,2}")
        .fillna(False)
    )

    municipio_valido = (
        municipio.str.fullmatch(r"[0-9]{1,5}")
        .fillna(False)
    )

    departamento_normalizado = departamento.str.zfill(2)
    municipio_normalizado = municipio.str.zfill(5)

    prefijo_coincide = (
        municipio_normalizado.str[:2]
        == departamento_normalizado
    ).fillna(False)

    validos = (
        departamento_valido
        & municipio_valido
        & prefijo_coincide
    )

    motivos = pd.Series("", index=df.index, dtype="string")

    motivos.loc[~departamento_valido] = (
        "CODIGO_DEPARTAMENTO_INVALIDO"
    )

    motivos.loc[
        departamento_valido & ~municipio_valido
    ] = "CODIGO_MUNICIPIO_INVALIDO"

    motivos.loc[
        departamento_valido
        & municipio_valido
        & ~prefijo_coincide
    ] = "CODIGOS_INCONSISTENTES"

    rechazados = df.loc[~validos].copy()
    rechazados["motivo_revision"] = motivos.loc[~validos]

    aceptados = df.loc[validos].copy()

    aceptados["c_digo_deldepartamento"] = (
        departamento_normalizado.loc[validos]
    )

    aceptados["c_digo_delmunicipio"] = (
        municipio_normalizado.loc[validos]
    )

    return aceptados, rechazados


def convertir_numeros(df):
    df = df.copy()

    df["requiere_revision_numerica"] = False
    df["campos_con_decimales"] = ""

    for columna in ["a_o", *COLUMNAS_NUMERICAS]:
        texto = df[columna].str.strip()
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
            columnas_ejemplo = list(
                dict.fromkeys([*CLAVES, columna])
            )

            ejemplos = df.loc[
                invalidos,
                columnas_ejemplo,
            ].head(10)

            raise ValueError(
                f"Valores no válidos en '{columna}':\n"
                f"{ejemplos.to_string(index=False)}"
            )

        tiene_decimales = (
            numeros.notna()
            & numeros.mod(1).ne(0)
        ).fillna(False)

        if columna == "a_o":
            if numeros.isna().any() or tiene_decimales.any():
                raise ValueError(
                    "Hay años vacíos o con parte decimal."
                )

            df[columna] = numeros.astype("Int64")
            continue

        df[columna] = numeros

        if tiene_decimales.any():
            df.loc[
                tiene_decimales,
                "requiere_revision_numerica",
            ] = True

            anteriores = df.loc[
                tiene_decimales,
                "campos_con_decimales",
            ]

            df.loc[
                tiene_decimales,
                "campos_con_decimales",
            ] = anteriores.map(
                lambda valor: (
                    f"{valor};{columna}"
                    if valor
                    else columna
                )
            )

            logger.warning(
                "Valores decimales conservados en %s: %s",
                columna,
                int(tiene_decimales.sum()),
            )

    return df


def transformar_matricula():
    crear_directorios()

    if not BRONZE_MATRICULA.is_file():
        raise FileNotFoundError(
            f"No se encontró el archivo: {BRONZE_MATRICULA}"
        )

    logger.info("Iniciando silver de matrícula")

    df = pd.read_csv(
        BRONZE_MATRICULA,
        dtype="string",
        keep_default_na=False,
        encoding="utf-8-sig",
    )

    requeridas = {
        *CLAVES,
        *COLUMNAS_NUMERICAS,
        "nombre_del_departamento",
        "nombre_del_municipio",
    }

    faltantes = requeridas - set(df.columns)

    if faltantes:
        raise ValueError(
            f"Faltan columnas en bronze: {sorted(faltantes)}"
        )

    if df.empty:
        raise ValueError("El bronze de matrícula está vacío.")

    filas_originales = len(df)

    for columna in [
        "nombre_del_departamento",
        "nombre_del_municipio",
    ]:
        df[columna] = df[columna].map(normalizar_texto)

    df = df.drop_duplicates().reset_index(drop=True)

    copias_normalizacion = filas_originales - len(df)

    logger.info(
        "Copias eliminadas después de normalizar: %s",
        copias_normalizacion,
    )

    df, codigos_invalidos = separar_codigos_invalidos(df)

    cantidad_codigos_invalidos = len(codigos_invalidos)

    codigos_invalidos.to_csv(
        RUTA_CODIGOS_INVALIDOS,
        index=False,
        encoding="utf-8-sig",
    )

    logger.info(
        "Registros separados por códigos inválidos: %s",
        cantidad_codigos_invalidos,
    )

    if df.empty:
        raise ValueError(
            "No quedaron registros con códigos válidos. "
            "Revisa matricula_codigos_invalidos.csv."
        )

    df = convertir_numeros(df)

    antes_deduplicacion_final = len(df)

    df = df.drop_duplicates().reset_index(drop=True)

    copias_tipificacion = (
        antes_deduplicacion_final - len(df)
    )

    df["registros_por_clave"] = (
        df.groupby(CLAVES, dropna=False)["a_o"]
        .transform("size")
        .astype("Int64")
    )

    df["clave_ambigua"] = df["registros_por_clave"].gt(1)

    df["tiene_datos_faltantes"] = (
        df[COLUMNAS_NUMERICAS].isna().any(axis=1)
        | df["nombre_del_municipio"].eq("").fillna(True)
    )

    df["requiere_revision"] = (
        df["clave_ambigua"]
        | df["requiere_revision_numerica"]
        | df["tiene_datos_faltantes"]
    )

    df = df.rename(columns={
        "a_o": "anio",
        "c_digo_deldepartamento": "codigo_departamento",
        "c_digo_delmunicipio": "codigo_municipio",
        "nombre_del_municipio": "municipio",
        "nombre_del_departamento": "departamento_campo_fuente",
    })

    df = df.sort_values(
        ["anio", "codigo_departamento", "codigo_municipio"],
        kind="stable",
    ).reset_index(drop=True)

    por_revisar = df.loc[
        df["requiere_revision"]
    ].copy()

    claves_salida = [
        "anio",
        "codigo_departamento",
        "codigo_municipio",
    ]

    cantidad_claves_ambiguas = (
        df.loc[
            df["clave_ambigua"],
            claves_salida,
        ]
        .drop_duplicates()
        .shape[0]
    )

    filas_reconciliadas = (
        copias_normalizacion
        + cantidad_codigos_invalidos
        + copias_tipificacion
        + len(df)
    )

    if filas_reconciliadas != filas_originales:
        raise ValueError(
            "Los conteos de limpieza no coinciden "
            "con el total de registros originales."
        )

    reporte = {
        "filas_bronze": int(filas_originales),
        "copias_eliminadas_tras_normalizar": int(
            copias_normalizacion
        ),
        "filas_separadas_por_codigos": int(
            cantidad_codigos_invalidos
        ),
        "copias_adicionales_tras_tipificar": int(
            copias_tipificacion
        ),
        "filas_silver": int(len(df)),
        "claves_con_varios_registros": int(
            cantidad_claves_ambiguas
        ),
        "filas_con_clave_ambigua": int(
            df["clave_ambigua"].sum()
        ),
        "filas_con_decimales": int(
            df["requiere_revision_numerica"].sum()
        ),
        "filas_con_datos_faltantes": int(
            df["tiene_datos_faltantes"].sum()
        ),
        "filas_por_revisar": int(len(por_revisar)),
        "filas_sin_alertas_detectadas": int(
            (~df["requiere_revision"]).sum()
        ),
        "anio_minimo": int(df["anio"].min()),
        "anio_maximo": int(df["anio"].max()),
        "conteos_reconciliados": True,
        "nulos_por_columna": {
            columna: int(cantidad)
            for columna, cantidad in df.isna().sum().items()
        },
        "motivos_codigos_invalidos": {
            motivo: int(cantidad)
            for motivo, cantidad in (
                codigos_invalidos["motivo_revision"]
                .value_counts()
                .items()
            )
        },
        "reglas_aplicadas": [
            "Nombres en mayúsculas y sin tildes.",
            "Eliminación de filas equivalentes.",
            "Códigos inválidos separados para revisión.",
            "Códigos territoriales conservados como texto.",
            "Vacíos numéricos conservados como nulos.",
            "Decimales conservados sin redondear y marcados.",
            "Claves ambiguas conservadas y marcadas.",
            "Registros con datos faltantes marcados.",
            "No se suman matrículas.",
        ],
    }

    df.to_csv(
        SILVER_MATRICULA,
        index=False,
        encoding="utf-8-sig",
    )

    por_revisar.to_csv(
        SILVER_MATRICULA_REVISION,
        index=False,
        encoding="utf-8-sig",
    )

    SILVER_MATRICULA_CALIDAD.write_text(
        json.dumps(
            reporte,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    logger.info("Filas bronze: %s", filas_originales)
    logger.info("Filas silver: %s", len(df))
    logger.info(
        "Copias adicionales tras tipificar: %s",
        copias_tipificacion,
    )
    logger.info(
        "Claves con varios registros: %s",
        cantidad_claves_ambiguas,
    )
    logger.info(
        "Filas con decimales: %s",
        reporte["filas_con_decimales"],
    )
    logger.info(
        "Filas con datos faltantes: %s",
        reporte["filas_con_datos_faltantes"],
    )
    logger.info("Filas por revisar: %s", len(por_revisar))
    logger.info(
        "Años disponibles: %s–%s",
        reporte["anio_minimo"],
        reporte["anio_maximo"],
    )
    logger.info("Conteos reconciliados correctamente")
    logger.info("No se sumaron matrículas")
    logger.info("Silver de matrícula finalizado")

    return df


def ejecutar_silver_matricula():
    try:
        return transformar_matricula()
    except Exception:
        logger.exception("Falló silver de matrícula")
        raise


if __name__ == "__main__":
    ejecutar_silver_matricula()
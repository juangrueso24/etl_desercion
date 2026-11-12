# carga de la capa gold a postgresql (tarea load_gold_postgres)
# cada tabla se reemplaza completa en una sola transaccion (truncate + copy),
# si algo falla se revierte todo
# dim_departamento y las llaves foraneas dan la integridad referencial
# historial_cargas guarda una fila por tabla en cada corrida
# la conexion sale de DW_HOST, DW_PORT, DW_NAME, DW_USER y DW_PASSWORD

import hashlib
import io
import os
import re
from datetime import datetime, timezone

import pandas as pd

from src.config import GOLD_DIR
from src.logger import logger


ESQUEMA = "gold"

CLAVES_GOLD = ["codigo_departamento", "nivel_formacion", "anio"]

# tabla: (archivo csv, llave primaria)
TABLAS = {
    "gold_final": ("gold_final.csv", CLAVES_GOLD),
    "gold_variaciones_anuales": ("gold_variaciones_anuales.csv", CLAVES_GOLD),
    "gold_top20_departamentos": ("gold_top20_departamentos.csv", CLAVES_GOLD),
    "gold_indicadores_por_nivel_anio": (
        "gold_indicadores_por_nivel_anio.csv",
        ["nivel_formacion", "anio"],
    ),
    "gold_resumen_calidad": ("gold_resumen_calidad.csv", ["metrica"]),
}

DIMENSION = "dim_departamento"
HISTORIAL = "historial_cargas"

# (tabla, nombre de la fk, columnas, tabla referenciada, columnas)
RELACIONES = [
    (
        "gold_final",
        "fk_gold_final_departamento",
        ["codigo_departamento"],
        DIMENSION,
        ["codigo_departamento"],
    ),
    (
        "gold_variaciones_anuales",
        "fk_variaciones_gold_final",
        CLAVES_GOLD,
        "gold_final",
        CLAVES_GOLD,
    ),
    (
        "gold_top20_departamentos",
        "fk_top20_gold_final",
        CLAVES_GOLD,
        "gold_final",
        CLAVES_GOLD,
    ),
]

TIPO_CATALOGO = {
    "BOOLEAN": "boolean",
    "INTEGER": "integer",
    "BIGINT": "bigint",
    "DOUBLE PRECISION": "double precision",
    "TEXT": "text",
}

ENTERO = r"-?(0|[1-9][0-9]*)"
DECIMAL = r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][-+]?[0-9]+)?"


def conectar():
    try:
        import psycopg2
    except ImportError as error:
        raise ImportError(
            "Falta psycopg2. Instálalo con: pip install psycopg2-binary"
        ) from error

    contrasena = os.environ.get("DW_PASSWORD")

    if not contrasena:
        raise EnvironmentError(
            "Falta la variable de entorno DW_PASSWORD "
            "(se define en airflow-medallon/.env)."
        )

    return psycopg2.connect(
        host=os.environ.get("DW_HOST", "localhost"),
        port=int(os.environ.get("DW_PORT", "5433")),
        dbname=os.environ.get("DW_NAME", "desercion_dw"),
        user=os.environ.get("DW_USER", "desercion"),
        password=contrasena,
        connect_timeout=15,
    )


def tipo_sql(nombre, serie):
    if nombre.startswith("codigo_"):
        return "TEXT"

    valores = serie[serie != ""]

    if valores.empty:
        return "TEXT"

    if valores.isin(["True", "False"]).all():
        return "BOOLEAN"

    if valores.str.fullmatch(ENTERO).all():
        return "INTEGER" if valores.str.len().max() <= 9 else "BIGINT"

    if valores.str.fullmatch(DECIMAL).all():
        return "DOUBLE PRECISION"

    return "TEXT"


def sha256_archivo(ruta):
    huella = hashlib.sha256()

    with open(ruta, "rb") as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            huella.update(bloque)

    return huella.hexdigest()


def _literal(texto):
    return "'" + str(texto).replace("'", "''") + "'"


def columnas_actuales(cursor, tabla):
    cursor.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        f"WHERE table_schema = '{ESQUEMA}' AND table_name = '{tabla}' "
        "ORDER BY ordinal_position"
    )

    return cursor.fetchall()


def preparar_tabla(cursor, tabla, columnas, tipos, llave):
    esperado = [
        (columna, TIPO_CATALOGO[tipo])
        for columna, tipo in zip(columnas, tipos)
    ]
    actual = columnas_actuales(cursor, tabla)

    if actual == esperado:
        cursor.execute(f'TRUNCATE TABLE {ESQUEMA}."{tabla}" CASCADE')
        return

    if actual:
        logger.warning(
            "La tabla %s.%s tiene otro esquema; se recrea.",
            ESQUEMA,
            tabla,
        )
        cursor.execute(f'DROP TABLE {ESQUEMA}."{tabla}" CASCADE')

    definicion = ", ".join(
        f'"{columna}" {tipo}' for columna, tipo in zip(columnas, tipos)
    )
    clave = ", ".join(f'"{columna}"' for columna in llave)

    cursor.execute(
        f'CREATE TABLE {ESQUEMA}."{tabla}" '
        f"({definicion}, PRIMARY KEY ({clave}))"
    )


def cargar_tabla(cursor, tabla, archivo, llave):
    ruta = GOLD_DIR / archivo

    if not ruta.is_file():
        raise FileNotFoundError(f"No se encontró {ruta}")

    datos = pd.read_csv(
        ruta,
        dtype="string",
        keep_default_na=False,
        encoding="utf-8-sig",
    )

    if datos.empty:
        raise ValueError(f"{archivo} está vacío; no se carga.")

    columnas = list(datos.columns)

    faltantes = [columna for columna in llave if columna not in columnas]

    if faltantes:
        raise ValueError(
            f"Faltan las columnas de la llave en {archivo}: {faltantes}"
        )

    tipos = [tipo_sql(columna, datos[columna]) for columna in columnas]

    preparar_tabla(cursor, tabla, columnas, tipos, llave)

    lista = ", ".join(f'"{columna}"' for columna in columnas)

    with open(ruta, "r", encoding="utf-8-sig", newline="") as archivo_csv:
        cursor.copy_expert(
            f'COPY {ESQUEMA}."{tabla}" ({lista}) '
            "FROM STDIN WITH (FORMAT csv, HEADER true)",
            archivo_csv,
        )

    cursor.execute(f'SELECT count(*) FROM {ESQUEMA}."{tabla}"')
    cargadas = cursor.fetchone()[0]

    if cargadas != len(datos):
        raise ValueError(
            f"{tabla}: el CSV tiene {len(datos)} filas y la tabla "
            f"quedó con {cargadas}."
        )

    logger.info(
        "Cargada %s.%s: %s filas (archivo %s)",
        ESQUEMA,
        tabla,
        cargadas,
        archivo,
    )

    return int(cargadas)


def cargar_dimension(cursor):
    # un nombre por codigo, sale de gold_final.csv
    archivo = TABLAS["gold_final"][0]
    ruta = GOLD_DIR / archivo

    if not ruta.is_file():
        raise FileNotFoundError(f"No se encontró {ruta}")

    gold = pd.read_csv(
        ruta,
        dtype="string",
        keep_default_na=False,
        encoding="utf-8-sig",
    )

    columnas = ["codigo_departamento", "departamento_canonico"]
    faltantes = [columna for columna in columnas if columna not in gold.columns]

    if faltantes:
        raise ValueError(f"Faltan columnas en {archivo}: {faltantes}")

    datos = gold[columnas].drop_duplicates()

    if (datos == "").any().any():
        raise ValueError(
            "Hay departamentos sin código o sin nombre en gold_final."
        )

    repetidos = datos[datos.duplicated("codigo_departamento", keep=False)]

    if not repetidos.empty:
        raise ValueError(
            "Un mismo código de departamento tiene varios nombres: "
            f"{sorted(repetidos['codigo_departamento'].unique())}"
        )

    cursor.execute(
        f'CREATE TABLE IF NOT EXISTS {ESQUEMA}."{DIMENSION}" ('
        '"codigo_departamento" TEXT PRIMARY KEY, '
        '"departamento_canonico" TEXT NOT NULL)'
    )
    cursor.execute(f'TRUNCATE TABLE {ESQUEMA}."{DIMENSION}" CASCADE')

    buffer = io.StringIO()
    datos.sort_values("codigo_departamento").to_csv(buffer, index=False)
    buffer.seek(0)

    cursor.copy_expert(
        f'COPY {ESQUEMA}."{DIMENSION}" '
        '("codigo_departamento", "departamento_canonico") '
        "FROM STDIN WITH (FORMAT csv, HEADER true)",
        buffer,
    )

    cursor.execute(f'SELECT count(*) FROM {ESQUEMA}."{DIMENSION}"')
    cargadas = int(cursor.fetchone()[0])

    logger.info("Cargada %s.%s: %s filas", ESQUEMA, DIMENSION, cargadas)

    return cargadas


def asegurar_integridad(cursor):
    # crea las fk que falten y el indice
    for tabla, nombre, columnas, referencia, destino in RELACIONES:
        cursor.execute(
            "SELECT 1 FROM pg_constraint c "
            "JOIN pg_class t ON t.oid = c.conrelid "
            "JOIN pg_namespace n ON n.oid = t.relnamespace "
            f"WHERE n.nspname = '{ESQUEMA}' AND t.relname = '{tabla}' "
            f"AND c.conname = '{nombre}'"
        )

        if cursor.fetchone() is not None:
            continue

        origen = ", ".join(f'"{columna}"' for columna in columnas)
        objetivo = ", ".join(f'"{columna}"' for columna in destino)

        cursor.execute(
            f'ALTER TABLE {ESQUEMA}."{tabla}" '
            f"ADD CONSTRAINT {nombre} FOREIGN KEY ({origen}) "
            f'REFERENCES {ESQUEMA}."{referencia}" ({objetivo})'
        )
        logger.info("Llave foránea creada: %s.%s", tabla, nombre)

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_gold_final_nivel_anio "
        f'ON {ESQUEMA}."gold_final" ("nivel_formacion", "anio")'
    )


def registrar_historial(cursor, corrida, registros):
    cursor.execute(
        f'CREATE TABLE IF NOT EXISTS {ESQUEMA}."{HISTORIAL}" ('
        "id BIGSERIAL PRIMARY KEY, "
        "corrida TEXT NOT NULL, "
        "tabla TEXT NOT NULL, "
        "filas INTEGER NOT NULL, "
        "sha256_csv TEXT NOT NULL, "
        "cargado_utc TIMESTAMPTZ NOT NULL DEFAULT now())"
    )

    for tabla, archivo, filas in registros:
        huella = sha256_archivo(GOLD_DIR / archivo)

        cursor.execute(
            f'INSERT INTO {ESQUEMA}."{HISTORIAL}" '
            "(corrida, tabla, filas, sha256_csv) VALUES "
            f"({_literal(corrida)}, {_literal(tabla)}, {int(filas)}, "
            f"{_literal(huella)})"
        )


def cargar_gold(corrida=None):
    if not corrida:
        corrida = datetime.now(timezone.utc).strftime("manual_%Y%m%d_%H%M%S")

    corrida = re.sub(r"[^A-Za-z0-9_.-]", "_", str(corrida))

    logger.info("Iniciando carga de Gold a PostgreSQL (corrida %s)", corrida)

    conexion = conectar()
    cargadas = {}
    registros = []

    try:
        with conexion.cursor() as cursor:
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {ESQUEMA}")

            filas = cargar_dimension(cursor)
            cargadas[f"{ESQUEMA}.{DIMENSION}"] = filas
            registros.append((DIMENSION, TABLAS["gold_final"][0], filas))

            for tabla, (archivo, llave) in TABLAS.items():
                filas = cargar_tabla(cursor, tabla, archivo, llave)
                cargadas[f"{ESQUEMA}.{tabla}"] = filas
                registros.append((tabla, archivo, filas))

            asegurar_integridad(cursor)
            registrar_historial(cursor, corrida, registros)

        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()

    logger.info("Carga a PostgreSQL finalizada: %s", cargadas)

    return {"esquema": ESQUEMA, "corrida": corrida, "tablas": cargadas}


def ejecutar_carga(corrida=None):
    try:
        return cargar_gold(corrida)
    except Exception:
        logger.exception("Falló la carga de Gold a PostgreSQL")
        raise


if __name__ == "__main__":
    ejecutar_carga()

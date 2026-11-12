# pruebas de la carga a postgresql
# las que usan la base trabajan en el esquema gold_prueba, que se borra al terminar
# se omiten si no hay base (definir DW_PASSWORD y tener postgres-dw encendido)

import hashlib

import pandas as pd
import pytest

from src import carga_dw
from test.conftest import CSV_GOLD, escribir_csv, leer_csv


def serie(*valores):
    return pd.Series(valores, dtype="string")


# ---------- funciones puras (no necesitan base de datos) ----------

def test_c01_tipo_codigo_conserva_ceros():
    # válido: columna codigo_departamento ['05','11']
    assert carga_dw.tipo_sql("codigo_departamento", serie("05", "11")) == "TEXT"


def test_c02_tipo_entero():
    # válido: anio ['2010','2024']
    assert carga_dw.tipo_sql("anio", serie("2010", "2024")) == "INTEGER"


def test_c03_tipo_entero_grande():
    # límite: ['1234567890'] (10 dígitos)
    assert carga_dw.tipo_sql("x", serie("1234567890")) == "BIGINT"


def test_c04_tipo_decimal():
    # válido: ['0.5','-1','2e-3']
    assert carga_dw.tipo_sql("tasa", serie("0.5", "-1", "2e-3")) == "DOUBLE PRECISION"


def test_c05_tipo_booleano_con_vacios():
    # válido: ['True','False','']
    assert carga_dw.tipo_sql("bandera", serie("True", "False", "")) == "BOOLEAN"


def test_c06_tipo_todo_vacio():
    # límite: ['','']
    assert carga_dw.tipo_sql("x", serie("", "")) == "TEXT"


def test_c07_tipo_ceros_a_la_izquierda():
    # límite: ['01','02'] en columna normal
    assert carga_dw.tipo_sql("x", serie("01", "02")) == "TEXT"


def test_c08_tipo_mezcla():
    # incorrecto: ['1','a']
    assert carga_dw.tipo_sql("x", serie("1", "a")) == "TEXT"


def test_c09_literal_escapa_comillas():
    # incorrecto: "o'brien" (comilla simple)
    assert carga_dw._literal("o'brien") == "'o''brien'"


def test_c10_sha256_archivo(tmp_path):
    # válido: archivo con el texto 'abc'
    ruta = tmp_path / "a.txt"
    ruta.write_bytes(b"abc")
    assert carga_dw.sha256_archivo(ruta) == hashlib.sha256(b"abc").hexdigest()


# ---------- pruebas con PostgreSQL real ----------

@pytest.fixture
def bd(gold_copia, monkeypatch):
    try:
        conexion = carga_dw.conectar()
    except Exception as error:
        pytest.skip(f"PostgreSQL no disponible: {type(error).__name__}")

    monkeypatch.setattr(carga_dw, "ESQUEMA", "gold_prueba")

    def borrar_esquema():
        with conexion.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS gold_prueba CASCADE")
        conexion.commit()

    borrar_esquema()
    yield conexion
    borrar_esquema()
    conexion.close()


def consultar(conexion, sql):
    with conexion.cursor() as cursor:
        cursor.execute(sql)
        filas = cursor.fetchall()
    conexion.commit()  # cierra la transacción para no bloquear la siguiente carga
    return filas


def filas_csv(gold, nombre):
    return len(leer_csv(gold / nombre))


def test_c11_carga_completa(bd, gold_copia):
    # válido: Gold real en esquema de prueba
    resultado = carga_dw.cargar_gold(corrida="prueba_1")

    for tabla, (archivo, _) in carga_dw.TABLAS.items():
        cargadas = consultar(bd, f"SELECT count(*) FROM gold_prueba.{tabla}")[0][0]
        assert cargadas == filas_csv(gold_copia, archivo)
        assert resultado["tablas"][f"gold_prueba.{tabla}"] == cargadas

    departamentos = leer_csv(gold_copia / "gold_final.csv")["codigo_departamento"].nunique()
    assert consultar(bd, "SELECT count(*) FROM gold_prueba.dim_departamento")[0][0] == departamentos

    llaves = consultar(
        bd,
        "SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace "
        "WHERE c.contype = 'f' AND n.nspname = 'gold_prueba'",
    )[0][0]
    assert llaves == 3

    historial = consultar(bd, "SELECT corrida, tabla FROM gold_prueba.historial_cargas")
    assert len(historial) == 6
    assert {fila[0] for fila in historial} == {"prueba_1"}


def test_c12_codigo_conserva_cero_inicial(bd, gold_copia):
    # límite: código de departamento '05'
    carga_dw.cargar_gold(corrida="prueba_1")

    assert consultar(
        bd, "SELECT count(*) FROM gold_prueba.gold_final WHERE codigo_departamento = '05'"
    )[0][0] > 0


def test_c13_carga_repetida_no_duplica(bd, gold_copia):
    # válido: se carga dos veces
    carga_dw.cargar_gold(corrida="prueba_1")
    carga_dw.cargar_gold(corrida="prueba_2")

    assert consultar(bd, "SELECT count(*) FROM gold_prueba.gold_final")[0][0] == filas_csv(
        gold_copia, "gold_final.csv"
    )
    assert consultar(bd, "SELECT count(*) FROM gold_prueba.historial_cargas")[0][0] == 12
    assert consultar(
        bd, "SELECT count(DISTINCT corrida) FROM gold_prueba.historial_cargas"
    )[0][0] == 2


def test_c14_llave_foranea_huerfana(bd, gold_copia):
    # incorrecto: una fila de variaciones con llave que no existe en gold_final
    ruta = gold_copia / "gold_variaciones_anuales.csv"
    datos = leer_csv(ruta)
    datos.loc[0, "codigo_departamento"] = "ZZ"
    escribir_csv(datos, ruta)

    with pytest.raises(Exception, match="foreign key"):
        carga_dw.cargar_gold(corrida="prueba_x")

    tablas = consultar(
        bd,
        "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'gold_prueba'",
    )[0][0]
    assert tablas == 0


def test_c15_fallo_conserva_datos_anteriores(bd, gold_copia):
    # incorrecto: segunda carga con llave huérfana tras una carga buena
    carga_dw.cargar_gold(corrida="prueba_1")

    ruta = gold_copia / "gold_top20_departamentos.csv"
    datos = leer_csv(ruta)
    datos.loc[0, "anio"] = "1900"
    escribir_csv(datos, ruta)

    with pytest.raises(Exception, match="foreign key"):
        carga_dw.cargar_gold(corrida="prueba_2")

    assert consultar(bd, "SELECT count(*) FROM gold_prueba.gold_final")[0][0] == filas_csv(
        gold_copia, "gold_final.csv"
    )
    assert consultar(bd, "SELECT count(*) FROM gold_prueba.historial_cargas")[0][0] == 6


def test_c16_csv_vacio(bd, gold_copia):
    # límite: gold_indicadores_por_nivel_anio.csv solo con encabezado
    ruta = gold_copia / "gold_indicadores_por_nivel_anio.csv"
    escribir_csv(leer_csv(ruta).iloc[0:0], ruta)

    with pytest.raises(ValueError, match="vacío"):
        carga_dw.cargar_gold(corrida="prueba_x")

    assert consultar(
        bd,
        "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'gold_prueba'",
    )[0][0] == 0


def test_c17_integracion_api_y_base(bd, gold_copia, monkeypatch):
    # integración: lo que devuelve la api coincide con lo cargado en postgres
    pytest.importorskip("fastapi")
    from api import main

    monkeypatch.setattr(main, "RUTA_GOLD", gold_copia / "gold_final.csv")
    carga_dw.cargar_gold(corrida="prueba_1")

    en_base = consultar(bd, "SELECT count(*) FROM gold_prueba.gold_final")[0][0]
    en_api = main.consultar_gold_completo()["total_registros"]

    assert en_api == en_base == filas_csv(gold_copia, "gold_final.csv")

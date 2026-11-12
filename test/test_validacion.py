# pruebas de la validacion de gold, usan copias de data/gold

import pandas as pd
import pytest

from src import validacion
from test.conftest import escribir_csv, leer_csv


def test_v01_gold_real_valido(gold_copia):
    # válido: Gold real sin modificar
    reporte = validacion.validar_gold()

    assert reporte["duplicados"] == 0
    assert reporte["filas_gold"] > 0


def test_v02_clave_duplicada(gold_copia):
    # incorrecto: una fila repetida en gold_final
    ruta = gold_copia / "gold_final.csv"
    datos = leer_csv(ruta)
    escribir_csv(pd.concat([datos, datos.iloc[[0]]], ignore_index=True), ruta)

    with pytest.raises(ValueError, match="Validación de Gold fallida"):
        validacion.validar_gold()


def test_v03_tasa_fuera_de_rango(gold_copia):
    # límite: tasa_desercion = 1.5 (máximo permitido 1)
    ruta = gold_copia / "gold_final.csv"
    datos = leer_csv(ruta)
    fila = datos.index[datos["estado_dato"] == "reportado"][0]
    datos.loc[fila, "tasa_desercion"] = "1.5"
    escribir_csv(datos, ruta)

    with pytest.raises(ValueError, match="fuera del rango"):
        validacion.validar_gold()


def test_v04_matricula_negativa(gold_copia):
    # incorrecto: matricula_reportada = -5
    ruta = gold_copia / "gold_final.csv"
    datos = leer_csv(ruta)
    fila = datos.index[datos["matricula_reportada"] != ""][0]
    datos.loc[fila, "matricula_reportada"] = "-5"
    escribir_csv(datos, ruta)

    with pytest.raises(ValueError, match="negativas"):
        validacion.validar_gold()


def test_v05_columna_ausente(gold_copia):
    # incorrecto: gold_final sin la columna tasa_desercion
    ruta = gold_copia / "gold_final.csv"
    escribir_csv(leer_csv(ruta).drop(columns=["tasa_desercion"]), ruta)

    with pytest.raises(ValueError, match="Faltan columnas"):
        validacion.validar_gold()


def test_v06_archivo_ausente(gold_copia):
    # incorrecto: se borra gold_variaciones_anuales.csv
    (gold_copia / "gold_variaciones_anuales.csv").unlink()

    with pytest.raises(FileNotFoundError):
        validacion.validar_gold()


def test_v07_gold_vacio(gold_copia):
    # límite: gold_final solo con encabezado
    ruta = gold_copia / "gold_final.csv"
    escribir_csv(leer_csv(ruta).iloc[0:0], ruta)

    with pytest.raises(ValueError, match="vacío"):
        validacion.validar_gold()

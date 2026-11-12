# pruebas de limpieza y transformacion

import pandas as pd
import pytest

from src.gold import convertir_booleano, convertir_numero
from src.integracion import leer_booleano, nombre_canonico
from src.silver import normalizar_departamento
from src.utils import normalizar_texto


def test_t01_normalizar_texto_valido():
    # válido: '  Bogotá,  D.C. '
    assert normalizar_texto("  Bogotá,  D.C. ") == "BOGOTA, D.C."


def test_t02_normalizar_texto_enie():
    # válido: 'Nariño'
    assert normalizar_texto("Nariño") == "NARINO"


def test_t03_normalizar_texto_nulo():
    # incorrecto: None
    assert pd.isna(normalizar_texto(None))


def test_t04_normalizar_texto_solo_espacios():
    # límite: '   '
    assert normalizar_texto("   ") == ""


def test_t05_normalizar_departamento():
    # válido: ' Norte de Santander '
    assert normalizar_departamento(" Norte de Santander ") == "NORTE DE SANTANDER"


def test_t06_nombre_canonico_alias():
    # válido: 'Guajira'
    assert nombre_canonico("Guajira") == "LA GUAJIRA"


def test_t07_nombre_canonico_bogota_sin_punto():
    # válido: 'Bogotá D.C'
    assert nombre_canonico("Bogotá D.C") == "BOGOTA D.C."


def test_t08_nombre_canonico_nulo():
    # incorrecto: None
    assert pd.isna(nombre_canonico(None))


def test_t09_convertir_booleano_valido_y_vacio():
    # válido/límite: ['True',' false ','TRUE','']
    resultado = convertir_booleano(
        pd.Series(["True", " false ", "TRUE", ""]), "columna"
    )
    assert resultado.isna().tolist() == [False, False, False, True]
    assert [bool(resultado[0]), bool(resultado[1]), bool(resultado[2])] == [True, False, True]


def test_t10_convertir_booleano_invalido():
    # incorrecto: ['talvez']
    with pytest.raises(ValueError, match="booleanos"):
        convertir_booleano(pd.Series(["talvez"]), "columna")


def test_t11_leer_booleano_vacio_es_invalido():
    # límite: ['True','']
    with pytest.raises(ValueError):
        leer_booleano(pd.Series(["True", ""]), "columna")


def test_t12_convertir_numero_valido_y_vacio():
    # válido/límite: ['1.5',' 2 ','']
    resultado = convertir_numero(pd.Series(["1.5", " 2 ", ""]))
    assert resultado[0] == 1.5
    assert resultado[1] == 2.0
    assert pd.isna(resultado[2])


def test_t13_convertir_numero_invalido():
    # incorrecto: ['abc']
    with pytest.raises(ValueError):
        convertir_numero(pd.Series(["abc"]))

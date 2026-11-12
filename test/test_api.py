# pruebas de la api (api/main.py)
# se llaman las funciones de los endpoints directo y se compara con las copias de gold

import json

import pytest

pytest.importorskip("fastapi")

from api import main  # noqa: E402
from test.conftest import leer_csv  # noqa: E402


@pytest.fixture
def api_gold(gold_copia, monkeypatch):
    # la api lee las copias de gold, no los archivos reales
    monkeypatch.setattr(main, "RUTA_GOLD", gold_copia / "gold_final.csv")
    monkeypatch.setattr(
        main, "RUTA_INDICADORES", gold_copia / "gold_indicadores_por_nivel_anio.csv"
    )
    return gold_copia


def test_a01_health(api_gold):
    # válido: gold disponible
    assert main.health() == {"api": "OK", "Archivo": True}


def test_a02_health_sin_archivo(api_gold, monkeypatch, tmp_path):
    # incorrecto: gold_final.csv no existe
    monkeypatch.setattr(main, "RUTA_GOLD", tmp_path / "no_existe.csv")
    assert main.health() == {"api": "OK", "Archivo": False}


def test_a03_gold_completo(api_gold):
    # válido: /gold devuelve totales, nombres de columnas y datos
    respuesta = main.consultar_gold_completo()
    gold = leer_csv(api_gold / "gold_final.csv")

    assert respuesta["total_registros"] == len(gold)
    assert respuesta["total_columnas"] == gold.shape[1]
    assert respuesta["Nombre_columnas"] == list(gold.columns)
    assert len(respuesta["Data"]) == len(gold)


def test_a04_gold_data(api_gold):
    # válido: /gold/data trae solo la llave Data
    respuesta = main.consultar_solo_data()

    assert list(respuesta) == ["Data"]
    assert len(respuesta["Data"]) == len(leer_csv(api_gold / "gold_final.csv"))


def test_a05_gold_indicadores(api_gold):
    # válido: /gold/indicadores devuelve la tabla de indicadores
    respuesta = main.consultar_indicadores()

    assert len(respuesta["Data"]) == len(
        leer_csv(api_gold / "gold_indicadores_por_nivel_anio.csv")
    )


def test_a06_codigo_departamento_con_cero(api_gold):
    # límite: el código sigue como texto, '05' no pasa a 5
    codigos = {fila["codigo_departamento"] for fila in main.consultar_solo_data()["Data"]}

    assert "05" in codigos
    assert all(len(codigo) == 2 for codigo in codigos)


def test_a07_json_sin_nan(api_gold):
    # límite: los nulos salen como null, json.dumps con allow_nan=False no falla
    for respuesta in (main.consultar_gold_completo(), main.consultar_indicadores()):
        json.dumps(respuesta, allow_nan=False)


def test_a08_archivo_inexistente(api_gold, monkeypatch, tmp_path):
    # incorrecto: sin gold_final.csv responde 404
    monkeypatch.setattr(main, "RUTA_GOLD", tmp_path / "no_existe.csv")

    with pytest.raises(main.HTTPException) as error:
        main.consultar_gold_completo()

    assert error.value.status_code == 404


def test_a09_preparar_dataframe_json(api_gold):
    # límite: NaN y vacíos pasan a None, el original no se modifica
    import numpy as np
    import pandas as pd

    original = pd.DataFrame({"a": [1.0, np.nan], "b": ["x", None]})
    listo = main.preparar_dataframe_json(original)

    assert listo.iloc[1, 0] is None
    assert listo.iloc[1, 1] is None
    assert pd.isna(original.iloc[1, 0])


def test_a10_endpoints_registrados():
    # válido: la app tiene las rutas que pide el profe más indicadores
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    peticion = TestClient(main.app)

    assert peticion.get("/health").status_code == 200
    assert peticion.get("/docs").status_code == 200
    assert peticion.get("/healt").status_code == 404

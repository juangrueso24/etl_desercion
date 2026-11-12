# fixtures compartidas
# las pruebas trabajan con copias de data/gold y data/silver, no tocan los datos reales

import shutil
from pathlib import Path

import pandas as pd
import pytest


RAIZ = Path(__file__).resolve().parents[1]
GOLD_REAL = RAIZ / "data" / "gold"
SILVER_REAL = RAIZ / "data" / "silver"

CSV_GOLD = [
    "gold_final.csv",
    "gold_variaciones_anuales.csv",
    "gold_top20_departamentos.csv",
    "gold_indicadores_por_nivel_anio.csv",
    "gold_resumen_calidad.csv",
]


def leer_csv(ruta):
    return pd.read_csv(
        ruta, dtype="string", keep_default_na=False, encoding="utf-8-sig"
    )


def escribir_csv(datos, ruta):
    datos.to_csv(ruta, index=False, encoding="utf-8-sig")


@pytest.fixture
def gold_copia(tmp_path, monkeypatch):
    # copia de gold y silver en una carpeta temporal, los modulos apuntan a ella
    if not (GOLD_REAL / "gold_final.csv").is_file():
        pytest.skip("No hay data/gold: ejecuta primero el pipeline.")

    gold = tmp_path / "gold"
    silver = tmp_path / "silver"
    gold.mkdir()
    silver.mkdir()

    for nombre in CSV_GOLD + ["calidad_gold.json"]:
        shutil.copy(GOLD_REAL / nombre, gold / nombre)

    shutil.copy(SILVER_REAL / "silver_integrado.csv", silver / "silver_integrado.csv")

    from src import carga_dw, validacion

    monkeypatch.setattr(carga_dw, "GOLD_DIR", gold)
    monkeypatch.setattr(validacion, "GOLD_FINAL", gold / "gold_final.csv")
    monkeypatch.setattr(validacion, "RUTA_VARIACIONES", gold / "gold_variaciones_anuales.csv")
    monkeypatch.setattr(validacion, "RUTA_TOP20", gold / "gold_top20_departamentos.csv")
    monkeypatch.setattr(validacion, "RUTA_INDICADORES", gold / "gold_indicadores_por_nivel_anio.csv")
    monkeypatch.setattr(validacion, "RUTA_RESUMEN", gold / "gold_resumen_calidad.csv")
    monkeypatch.setattr(validacion, "RUTA_CALIDAD", gold / "calidad_gold.json")
    monkeypatch.setattr(validacion, "RUTA_INTEGRADO", silver / "silver_integrado.csv")

    return gold

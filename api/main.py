from pathlib import Path

import pandas as pd
from fastapi import FastAPI
from fastapi import HTTPException


# ruta donde esta el proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

RUTA_GOLD = BASE_DIR / "data" / "gold" / "gold_final.csv"
RUTA_INDICADORES = (
    BASE_DIR / "data" / "gold" / "gold_indicadores_por_nivel_anio.csv"
)


# funciones para leer los datos y dejarlos listos para json
def cargar_csv(ruta):
    if not ruta.exists():
        raise HTTPException(
            status_code=404,
            detail="El archivo no existe, ejecuta primero el pipeline",
        )

    return pd.read_csv(
        ruta,
        dtype={"codigo_departamento": str},
        encoding="utf-8-sig",
    )


def preparar_dataframe_json(df):
    df = df.copy()

    # los nulos de pandas pasan a None para que salgan como null
    df = df.astype(object).where(pd.notnull(df), None)

    return df


# creacion de la api
app = FastAPI(
    title="API ETL deserción y matrícula",
    description="Servicio para consultar los datos de la capa gold",
    version="1.0.0",
)


# endpoints
@app.get("/")
def inicio():
    return {
        "mensaje": "Bienvenidos a la API del ETL de deserción y matrícula",
        "documentacion": "/docs",
        "gold": "/gold",
        "data": "/gold/data",
        "indicadores": "/gold/indicadores",
        "salud": "/health",
    }


@app.get("/gold")
def consultar_gold_completo():
    df = cargar_csv(RUTA_GOLD)

    df = preparar_dataframe_json(df)

    return {
        "total_registros": len(df),
        "total_columnas": len(df.columns),
        "Nombre_columnas": df.columns.tolist(),
        "Data": df.to_dict(orient="records"),
    }


@app.get("/gold/data")
def consultar_solo_data():
    df = cargar_csv(RUTA_GOLD)

    df = preparar_dataframe_json(df)

    return {"Data": df.to_dict(orient="records")}


@app.get("/gold/indicadores")
def consultar_indicadores():
    df = cargar_csv(RUTA_INDICADORES)

    df = preparar_dataframe_json(df)

    return {"Data": df.to_dict(orient="records")}


@app.get("/health")
def health():
    return {
        "api": "OK",
        "Archivo": RUTA_GOLD.exists(),
    }

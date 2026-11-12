# pruebas del dag, se lee el archivo sin necesitar airflow instalado
# la ejecucion real se prueba en la interfaz de airflow

import ast
import re
import sys
import types

from src import orquestacion
from test.conftest import RAIZ


RUTA_DAG = RAIZ / "airflow-medallon" / "dags" / "etl_desercion_hourly.py"

TAREAS_ESPERADAS = [
    "extract_api_bronze",
    "extract_excel_bronze",
    "transform_silver",
    "build_gold",
    "validate_gold",
    "load_gold_postgres",
]


def argumentos_del_dag():
    arbol = ast.parse(RUTA_DAG.read_text(encoding="utf-8"))

    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.FunctionDef):
            for decorador in nodo.decorator_list:
                if isinstance(decorador, ast.Call) and getattr(decorador.func, "id", "") == "dag":
                    return {k.arg: ast.unparse(k.value) for k in decorador.keywords}

    raise AssertionError("No se encontró el decorador @dag")


def test_o01_configuracion_del_dag():
    # válido: lectura del archivo
    argumentos = argumentos_del_dag()

    assert argumentos["dag_id"] == "'etl_desercion_hourly'"
    assert argumentos["schedule"] == "'0 * * * *'"
    assert argumentos["catchup"] == "False"
    assert argumentos["max_active_runs"] == "1"
    assert "'retries': 2" in argumentos["default_args"]
    assert "timedelta(minutes=5)" in argumentos["default_args"]


def test_o02_tareas_del_dag():
    # válido: lectura del archivo
    arbol = ast.parse(RUTA_DAG.read_text(encoding="utf-8"))
    tareas = [
        nodo.name
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.FunctionDef)
        and any(getattr(d, "id", "") == "task" for d in nodo.decorator_list)
    ]

    assert tareas == TAREAS_ESPERADAS


def test_o03_identificador_de_corrida_sin_airflow(monkeypatch):
    # límite: fuera de Airflow (sin run_id)
    monkeypatch.setitem(sys.modules, "airflow.sdk", None)  # fuerza el ImportError

    assert re.fullmatch(r"[0-9]{8}_[0-9]{6}", orquestacion._identificador_corrida())


def test_o04_identificador_de_corrida_con_run_id(monkeypatch):
    # válido: run_id de Airflow 'manual__2026-11-06T23:07:44+00:00'
    falso = types.ModuleType("airflow.sdk")
    falso.get_current_context = lambda: {"run_id": "manual__2026-11-06T23:07:44+00:00"}
    monkeypatch.setitem(sys.modules, "airflow", types.ModuleType("airflow"))
    monkeypatch.setitem(sys.modules, "airflow.sdk", falso)

    assert orquestacion._identificador_corrida() == "manual__2026-11-06T23_07_44_00_00"


def test_o05_respaldos_conserva_los_ultimos(tmp_path):
    # límite: 15 respaldos en la carpeta
    for numero in range(15):
        (tmp_path / f"respaldo_{numero:02d}.csv").write_text("x")

    orquestacion._limpiar_respaldos(tmp_path)

    nombres = sorted(archivo.name for archivo in tmp_path.glob("*.csv"))
    assert len(nombres) == orquestacion.RESPALDOS_A_CONSERVAR == 10
    assert nombres[0] == "respaldo_05.csv"
    assert nombres[-1] == "respaldo_14.csv"


def test_o06_respaldos_carpeta_inexistente(tmp_path):
    # incorrecto: la carpeta no existe
    orquestacion._limpiar_respaldos(tmp_path / "no_existe")

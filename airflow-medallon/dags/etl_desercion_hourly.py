import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow.sdk import dag, task

# ruta del proyecto dentro del contenedor
PROJECT_DIR = Path(os.environ.get("MEDALLON_DIR", "/opt/airflow/medallon"))
sys.path.insert(0, str(PROJECT_DIR))


@dag(
    dag_id="etl_desercion_hourly",
    description="ETL Medallion: deserción y matrícula en educación superior",
    start_date=datetime(2026, 10, 1),
    schedule="0 * * * *",  # cada hora, en utc
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
    tags=["ETL", "medallion", "desercion"],
)
def etl_desercion_hourly():
    @task
    def extract_api_bronze():
        from src.orquestacion import extraer_api_bronze

        return extraer_api_bronze()

    @task
    def extract_excel_bronze():
        from src.orquestacion import extraer_excel_bronze

        return extraer_excel_bronze()

    @task
    def transform_silver(api_info, excel_info):
        from src.orquestacion import transformar_silver

        return transformar_silver()

    @task
    def build_gold(silver_info):
        from src.orquestacion import construir_gold

        return construir_gold()

    @task
    def validate_gold(gold_info):
        from src.orquestacion import validar_gold

        return validar_gold()

    @task
    def load_gold_postgres(validation_info):
        from src.orquestacion import cargar_gold_postgres

        return cargar_gold_postgres()

    api = extract_api_bronze()
    excel = extract_excel_bronze()
    silver = transform_silver(api, excel)
    gold = build_gold(silver)
    validated = validate_gold(gold)
    load_gold_postgres(validated)


etl_desercion_hourly()

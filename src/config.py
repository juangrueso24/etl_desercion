from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR = DATA_DIR / "gold"
LOG_DIR = BASE_DIR / "logs"

RAW_DESERCION = RAW_DIR / "td_departamento.csv"

BRONZE_DESERCION = BRONZE_DIR / "bronze_desercion_departamento.csv"
BRONZE_NOTAS = BRONZE_DIR / "notas_desercion_departamento.json"

SILVER_DESERCION = SILVER_DIR / "silver_desercion_departamento.csv"
GOLD_FINAL = GOLD_DIR / "gold_final.csv"

API_URL = "https://www.datos.gov.co/resource/y9ga-zwzy.json"

NIVELES_ESPERADOS = (
    "Universitario",
    "TyT",
    "Técnico Profesional",
    "Tecnológico",
)

ANIOS_ESPERADOS = tuple(str(anio) for anio in range(2010, 2025))


def crear_directorios():
    for carpeta in (
        RAW_DIR,
        BRONZE_DIR,
        SILVER_DIR,
        GOLD_DIR,
        LOG_DIR,
    ):
        carpeta.mkdir(parents=True, exist_ok=True)

SILVER_CALIDAD = SILVER_DIR / "calidad_desercion_departamento.json"
SILVER_RESPALDOS_DIR = SILVER_DIR / "respaldos"

RAW_MATRICULA_API = RAW_DIR / "matricula_api_original.json"
RAW_MATRICULA_METADATA = RAW_DIR / "matricula_api_metadatos.json"
BRONZE_MATRICULA = BRONZE_DIR / "bronze_matricula_municipios.csv"

SILVER_MATRICULA = (
    SILVER_DIR / "silver_matricula_municipios.csv"
)

SILVER_MATRICULA_REVISION = (
    SILVER_DIR / "matricula_registros_por_revisar.csv"
)

SILVER_MATRICULA_CALIDAD = (
    SILVER_DIR / "calidad_matricula.json"
)

SILVER_MATRICULA_CODIGOS_INVALIDOS = (
    SILVER_DIR / "matricula_codigos_invalidos.csv"
)
# Deserción y matrícula en educación superior en Colombia

Autor: Juan José Grueso (trabajo individual).  
Repositorio: https://github.com/juangrueso24/etl_desercion

## Alcance
Proyecto de extracción, transformación e integración mediante arquitectura medallion, módulos Python, logs, indicadores y un único notebook. El pipeline se orquesta con Apache Airflow (DAG `etl_desercion_hourly`, una ejecución por hora) y la capa Gold se carga en PostgreSQL desde el DAG. El script `main.py` ejecuta las mismas etapas sin Airflow y, con la opción `--cargar`, valida Gold y lo carga en PostgreSQL. Una API FastAPI (`uvicorn api.main:app --reload`) sirve los datos de Gold y un dashboard Streamlit la consume.

Flujo: Excel + API → bronze → silver → JOIN → gold → indicadores → validación → PostgreSQL. Gold (CSV) → API FastAPI → dashboard.

El cruce es técnico y no certifica equivalencia metodológica entre las poblaciones. El análisis actual es departamental, no institucional. Los objetivos del Avance 1 que requieren otras fuentes siguen documentados como pendientes.

## Problema, usuarios y objetivos
**Problema.** La deserción en educación superior en Colombia se publica en un archivo Excel por departamento, nivel de formación y año, y la matrícula en un conjunto de datos abiertos distinto. No hay una vista única, verificada y consultable que permita ver cuánta deserción hay, dónde y cuándo, ni cruzarla con la matrícula reportada.

**Usuarios y necesidades** (hipótesis de partida; se validan con usuarios reales en `docs/FEEDBACK_USUARIOS.md`):
| Usuario | Necesita |
|---|---|
| Analista de educación superior (secretaría de educación, institución) | Consultar la tasa de deserción por departamento, nivel y año, y ver la evolución. |
| Tomador de decisiones | Identificar los departamentos con mayor deserción en un año y nivel (ranking del 20 %). |
| Equipo de datos / desarrollador | Un pipeline reproducible, trazable y servido por API, sin acceder directamente a la base de datos. |

**Objetivo.** Construir un ETL con arquitectura medallón que integre deserción (Excel) y matrícula departamental (API de datos.gov.co), cargue el resultado en PostgreSQL y lo ofrezca por una API y un dashboard.

**Alcance.** Análisis departamental, por nivel de formación (Universitario, TyT, Técnico Profesional y Tecnológico), 2010–2024. Fuera de alcance: datos institucionales, permanencia, cantidad de desertores y análisis causal (ver *Limitaciones y alcance académico*).

**KPIs del pipeline y del producto** (los KPI de la capa Gold están en *Tabla de KPI*):
| KPI | Meta |
|---|---|
| Filas de `gold_final` | 1.950 (33 lugares, es decir, 32 departamentos y Bogotá D.C., × 4 niveles × 15 años, menos combinaciones sin fila en la fuente) |
| Claves duplicadas o nulas en Gold | 0 |
| Corridas del DAG con las 6 tareas en verde | 100 % de las corridas sin fallas externas |
| Coincidencia entre filas del CSV y filas en PostgreSQL | 100 % en las 5 tablas |
| Disponibilidad de la tasa en `gold_indicadores_por_nivel_anio` | Mostrada por nivel y año (ej. Universitario 2020: 100 %) |
| Respuesta de la API (`/health`) | `{"api": "OK", "Archivo": true}` con Gold disponible |

**OKR originales (Avance 1).** El estado de cada resultado clave está en `notebooks/analisis_gold.ipynb` (sección *Estado de los objetivos e indicadores originales*): KR1 y KR3 parciales, KR2 con selección descriptiva, KR4 con todos los años disponibles de deserción y KR5 no alcanzado en la evaluación estricta.

**MVP (prioridad alta).**
1. Extraer Excel y API con trazabilidad (huella SHA-256 y registro de la corrida).
2. Limpiar, integrar y construir Gold con indicadores.
3. Validar la calidad de Gold antes de cargarlo.
4. Cargar Gold en PostgreSQL con llaves, historial de cargas y sin duplicados.
5. Orquestar con Airflow (cada hora, con reintentos).
6. Servir los datos por API (`/health`, `/gold`, `/gold/data`, `/gold/indicadores`) y mostrarlos en un dashboard.

**Criterios de aceptación** (cada uno se verifica como se indica):
| # | Criterio | Cómo se verifica |
|---|---|---|
| 1 | `main.py` o el DAG terminan sin error y generan los 5 CSV de Gold. | DAG en verde; `data/gold/` |
| 2 | `validate_gold` pasa: archivos, esquema, claves únicas, rangos y consistencia entre capas. | Log de la tarea; `test/test_validacion.py` |
| 3 | Cada tabla de PostgreSQL tiene las mismas filas que su CSV y tiene llaves primarias y foráneas. | `docker compose exec postgres-dw psql ...`; `test/test_carga.py` |
| 4 | Repetir la carga no duplica filas y el historial registra cada corrida. | `gold.historial_cargas`; prueba C13 |
| 5 | La API responde 200 en `/health`, `/gold`, `/gold/data` y `/gold/indicadores`, y 404 si falta `gold_final.csv`. | `http://127.0.0.1:8000/docs`; `test/test_api.py` |
| 6 | El dashboard muestra KPI, evolución y ranking sin errores. | `streamlit run dashboard/app_dashboard.py` |
| 7 | El DAG corre cada hora y reintenta 2 veces ante fallas. | Interfaz de Airflow; `test/test_orquestacion.py` |

## Arquitectura
```text
Excel (TD - departamento) ──┐
                            ├─► Bronze ─► Silver ─► JOIN ─► Gold ─► validación ─► PostgreSQL (esquema gold)
API datos.gov.co 4hrb-y62g ─┘                                  │
                                                               └─► CSV de Gold ─► API FastAPI (uvicorn api.main:app)
                                                                                          │
                                                                                          ▼
                                                                        Dashboard Streamlit / navegador (/docs)

Orquestación: Apache Airflow, DAG etl_desercion_hourly (cada hora, UTC, 2 reintentos)
```
La API solo lee los CSV de Gold: no modifica nada y no se conecta a la base de datos, así que quien la consulta no recibe credenciales de PostgreSQL.

## Fuentes activas
### Deserción
- Entrada: `data/raw/articles-415244_recurso_19.xlsx`.
- Hoja: `TD - departamento`.
- Indicador: tasa de deserción anual.
- Periodo observado: 2010–2024.
- Corte de la hoja: cierre estadístico de 2025.
- Bloques: Universitario, TyT, Técnico Profesional y Tecnológico.

El Excel se conserva sin modificar. Su huella SHA-256, hoja y exportación se documentan en `data/bronze/trazabilidad_excel.json`.

Se genera `data/bronze/excel_extraido/td_departamento.csv`. El campo `fuente_archivo` de silver identifica esa exportación; el manifiesto enlaza con el Excel original. `linea_origen` corresponde a la fila del Excel. Los CSV antiguos de raw no son entradas obligatorias del flujo actual.

### Matrícula departamental
- Recurso activo: `4hrb-y62g`.
- API: https://www.datos.gov.co/resource/4hrb-y62g.json
- Metadatos: https://www.datos.gov.co/api/views/4hrb-y62g.json
- Nombre: MEN_ESTADISTICAS DE MATRICULA POR DEPARTAMENTOS_ES.
- Atribución consultada: Ministerio de Educación Nacional - MinEducación, Bogotá D.C.
- Periodo observado: 2005–2021, aunque la descripción anuncia hasta 2024.

Se guardan `data/raw/matricula_departamental_original.json` y `data/raw/matricula_departamental_metadatos.json`.

La fuente municipal anterior `y9ga-zwzy` y sus módulos son antecedentes, no parte del pipeline activo. No se mezclan ambas matrículas.

## Estructura activa
```text
etl_desercion/
├── airflow-medallon/
│   ├── dags/
│   │   └── etl_desercion_hourly.py      # DAG de Airflow
│   ├── config/airflow.cfg
│   ├── logs/                            # logs de Airflow (los genera Airflow)
│   ├── plugins/                         # vacía; la monta Docker
│   ├── .env.example                     # variables necesarias (se copia a .env)
│   ├── Dockerfile
│   ├── docker-compose.yaml              # Airflow, Redis, Postgres de Airflow y Postgres de Gold
│   └── requirements-airflow.txt
├── data/
│   ├── raw/
│   ├── bronze/
│   │   ├── excel_extraido/
│   │   └── corridas/                    # Bronze original de cada corrida (Airflow)
│   ├── silver/
│   │   └── respaldos/
│   └── gold/
│       └── respaldos/
├── logs/etl.log
├── notebooks/analisis_gold.ipynb
├── api/
│   ├── __init__.py
│   └── main.py                          # API FastAPI (uvicorn api.main:app --reload)
├── dashboard/
│   └── app_dashboard.py                 # dashboard Streamlit (consume la API)
├── docs/
│   ├── PRUEBAS.md                       # casos de prueba y resultados
│   ├── CHECKLIST_EVIDENCIAS.md          # checklist del docente con su evidencia
│   ├── EVIDENCIAS.md                    # capturas de pruebas, base de datos, API y dashboard
│   ├── capturas/                        # imágenes de EVIDENCIAS.md
│   └── FEEDBACK_USUARIOS.md             # feedback de usuarios y cambios (a completar)
├── test/                                # pruebas con pytest
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── logger.py
│   ├── utils.py
│   ├── bronze.py
│   ├── bronze_matricula_departamental.py
│   ├── silver.py
│   ├── silver_matricula_departamental.py
│   ├── integracion.py
│   ├── gold.py
│   ├── indicadores.py
│   ├── orquestacion.py                  # funciones que llama cada tarea del DAG
│   ├── validacion.py                    # tarea validate_gold
│   └── carga_dw.py                      # tarea load_gold_postgres
├── main.py                              # ETL sin Airflow (python main.py, con --cargar carga a PostgreSQL)
├── pytest.ini
├── requirements.txt
├── README.md
└── .gitignore
```
Pueden permanecer inspectores y módulos históricos adicionales. `.venv` es local, no un entregable.

## Transformaciones y controles
### Bronze
Lee directamente el Excel y exporta la hoja, extrae sus bloques y conserva valores NA, notas y filas de origen. La API conserva todos los registros recibidos, incluidos duplicados.

La extracción verifica cantidades antes y después de la consulta. No equivale a una instantánea transaccional si el servidor cambia datos durante la lectura. El límite actual es 50.000 registros; si se supera, se detiene y requiere paginación.

### Silver
Transforma años de columnas a filas, normaliza nombres y códigos, valida tipos y rangos, elimina filas equivalentes y separa claves inválidas. No convierte faltantes o no aplicables en cero.

Los decimales de matrícula se conservan y marcan, no se redondean para aparentar conteos enteros. Las alertas de nombres variables en silver pueden resolverse después con el catálogo por código. Las alertas se superponen y no se suman como grupos independientes.

### Integración
LEFT JOIN desde deserción, validado uno a uno por código de departamento + nivel + año. Conserva todas las observaciones de deserción y utiliza correspondencias territoriales explícitas, no coincidencias difusas.

Estados:
- COINCIDENCIA_TECNICA.
- MATRICULA_POR_REVISAR.
- NIVEL_SIN_EQUIVALENCIA_DEFINIDA.
- FUERA_COBERTURA_TEMPORAL.
- SIN_COINCIDENCIA, si aparece un caso no explicado por los anteriores.

Los estados son exclusivos: para TyT prima la falta de equivalencia aunque algunos años también estén fuera de cobertura. Una clave puede coincidir aunque no exista tasa. `par_sin_alertas_tecnicas` requiere ambos valores disponibles y ausencia de alertas técnicas definidas, no comparabilidad metodológica certificada.

### Gold e indicadores
Conserva proporciones y añade porcentajes. Calcula cambios en puntos porcentuales únicamente entre años consecutivos con ambas tasas disponibles.

El ranking selecciona ceil(20 % de departamentos con tasa) por año y nivel. Los empates se resuelven por código, sin implicar significancia estadística. No se suman tasas ni se construye matrícula TyT sumando otros niveles.

## Orquestación con Apache Airflow
El DAG `etl_desercion_hourly` (`airflow-medallon/dags/etl_desercion_hourly.py`) ejecuta el pipeline cada hora. Airflow decide el orden, los reintentos y el registro de cada ejecución; Python y pandas conservan la lógica de transformación (`src/`). El DAG solo llama a `src/orquestacion.py`, que invoca los módulos existentes y devuelve rutas y metadatos pequeños (nunca DataFrames).

### Arquitectura y dependencias
```text
extract_api_bronze ───┐
                      ├─► transform_silver ─► build_gold ─► validate_gold ─► load_gold_postgres
extract_excel_bronze ─┘
```
Las dos extracciones corren en paralelo. Silver solo se ejecuta si ambas terminan bien; Gold depende de Silver; la validación depende de Gold; la carga a PostgreSQL solo se ejecuta si la validación pasó.

| Tarea | Qué hace | Módulos de `src/` | Salida |
|---|---|---|---|
| `extract_api_bronze` | Consume la API de matrícula departamental (recurso `4hrb-y62g`), conserva la respuesta original por corrida y registra cantidad de registros, hora y procedencia. | `bronze_matricula_departamental.py` | `data/raw/matricula_departamental_original.json`, `data/bronze/bronze_matricula_departamental.csv`, `data/bronze/corridas/<corrida>/` |
| `extract_excel_bronze` | Lee la hoja `TD - departamento` del Excel, genera bronze y guarda por corrida la hoja leída y un manifiesto con la huella SHA-256 del Excel. | `bronze.py` | `data/bronze/bronze_desercion_departamento.csv`, `data/bronze/trazabilidad_excel.json`, `data/bronze/corridas/<corrida>/` |
| `transform_silver` | Silver de deserción, silver de matrícula e integración (LEFT JOIN por código de departamento + nivel + año). Registra filas de entrada, salida y descartes. | `silver.py`, `silver_matricula_departamental.py`, `integracion.py` | `data/silver/silver_integrado.csv` y reportes de calidad |
| `build_gold` | Genera `gold_final.csv`, variaciones anuales, ranking e indicadores por nivel y año. | `gold.py`, `indicadores.py` | `data/gold/` |
| `validate_gold` | Comprueba existencia de archivos, esquema, claves, duplicados, rangos y consistencia entre Silver, Gold e indicadores. Lanza una excepción si falla una regla crítica. | `validacion.py` | Resultado en el log de la tarea |
| `load_gold_postgres` | Carga las cinco tablas de Gold y la dimensión de departamentos en PostgreSQL (esquema `gold`) dentro de una sola transacción, crea las llaves foráneas y registra la carga en el historial. | `carga_dw.py` | Tablas `gold.*` y `gold.historial_cargas` |

### Configuración del DAG
| Parámetro | Valor |
|---|---|
| Frecuencia | `schedule="0 * * * *"` (cada hora, minuto 00) |
| Recuperación de intervalos | `catchup=False` |
| Concurrencia | `max_active_runs=1` |
| Fecha de inicio | `start_date=datetime(2026, 10, 1)` |
| Reintentos | `retries=2`, `retry_delay=5 minutos` |
| Zona horaria | UTC (`default_timezone = utc` en `airflow-medallon/config/airflow.cfg`). Bogotá es UTC-5, así que el minuto 00 UTC también es el minuto 00 de la hora de Bogotá. |

### Comportamiento horario y control de versión del Excel
El Excel es estático, pero se vuelve a leer en cada corrida y la API se consulta de nuevo. La versión del Excel se controla con su huella SHA-256, registrada en `data/bronze/trazabilidad_excel.json` y en el `manifiesto_excel.json` de cada corrida: si el archivo cambia, la huella cambia. El Excel completo (10 MB) no se copia cada hora; por corrida se conserva la hoja leída.

### Bronze por corrida
Cada corrida guarda su Bronze original en `data/bronze/corridas/<identificador de la corrida>/`:

| Archivo | Contenido |
|---|---|
| `matricula_departamental_original.json` | Respuesta original de la API en esa corrida |
| `manifiesto_api.json` | Hora (UTC), procedencia, recurso y cantidad de registros recibidos |
| `td_departamento.csv` | Hoja del Excel leída en esa corrida, sin modificar |
| `manifiesto_excel.json` | Hora (UTC), procedencia, hoja, registros extraídos y SHA-256 del Excel |

El identificador es el `run_id` de Airflow (por ejemplo `scheduled__2026-11-06T20_00_00_00_00` o `manual__...`). Si una tarea se reintenta, reescribe los mismos archivos de su corrida.

### Persistencia e idempotencia
- **Bronze:** el original de cada corrida se conserva en `data/bronze/corridas/`; los archivos base de Bronze se sobrescriben con la última lectura.
- **Silver y Gold:** se regeneran completos en cada corrida y el resultado anterior se respalda en `respaldos/`. Se conservan los 10 respaldos más recientes (`RESPALDOS_A_CONSERVAR` en `src/orquestacion.py`).
- **PostgreSQL:** cada tabla se vacía y se vuelve a cargar dentro de una transacción (`TRUNCATE` + `COPY`, carga en lote). Las llaves primarias impiden filas duplicadas, las llaves foráneas garantizan la integridad referencial y, si algo falla, se revierte todo y la base queda como estaba.
- **Historial:** `gold.historial_cargas` no se vacía nunca; guarda por corrida y por tabla las filas cargadas, la huella SHA-256 del CSV y la fecha UTC.
- **Concurrencia:** `max_active_runs=1` evita que dos corridas escriban a la vez los mismos archivos.
- Con las mismas entradas, repetir una corrida produce los mismos archivos y los mismos recuentos (1.950 filas en `gold_final`).

### Errores y observabilidad
- Cada etapa lanza una excepción ante archivos ausentes, API caída o con respuesta inválida, esquemas distintos, claves duplicadas o inconsistencias entre capas. Airflow reintenta dos veces y, si no se recupera, las tareas siguientes quedan en `upstream_failed` y no se ejecutan.
- Cada tarea registra intentos, errores, duración, cantidad de registros y rutas de salida. Se consultan en la interfaz de Airflow (DAG → Ejecuciones → tarea → Logs) y en `logs/etl.log`.

## Instalación y ejecución con Docker (Airflow + PostgreSQL)
Requisitos: Docker Desktop con Docker Compose v2 y al menos 4 GB de RAM asignados, y los puertos `8080` (Airflow) y `5433` (PostgreSQL de Gold) libres. No hace falta instalar Python ni Airflow: todo corre en contenedores.

1. Entra a la carpeta de Airflow (desde la raíz del proyecto):
   ```powershell
   cd airflow-medallon
   ```
2. Crea el archivo `.env` a partir del ejemplo:
   ```powershell
   Copy-Item .env.example .env
   ```
3. Genera una clave Fernet y pégala en `.env` como `FERNET_KEY=<clave>` (sin espacios ni comillas):
   ```powershell
   docker run --rm apache/airflow:3.3.2 python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
4. En `.env`, cambia `DW_PASSWORD` por una contraseña propia (letras y números). Esa es la contraseña de la base de datos de Gold.
5. Construye la imagen y levanta los servicios (la primera vez tarda unos minutos):
   ```powershell
   docker compose up --build -d
   ```
6. Comprueba que todos los servicios estén `healthy`:
   ```powershell
   docker compose ps
   ```
7. Abre `http://localhost:8080`. Usuario `airflow`, contraseña `airflow` (valores por defecto del `docker-compose.yaml`; se cambian con `_AIRFLOW_WWW_USER_USERNAME` y `_AIRFLOW_WWW_USER_PASSWORD`).
8. Busca el DAG `etl_desercion_hourly`. Se crea pausado: activa el interruptor y, para probarlo de inmediato, pulsa **Trigger**. Después corre solo al minuto 00 de cada hora.
9. Revisa el resultado en el Graph (las seis tareas en verde), en los logs de cada tarea y en `data/gold/`.
10. Para detener los servicios: `docker compose down` (con `-v` también se borran las bases de datos de Airflow y de Gold). Los archivos de `data/` se conservan.

### Consultar Gold en PostgreSQL
Las tablas quedan en el esquema `gold`:

| Tabla | Filas | Llave primaria |
|---|---:|---|
| `gold.gold_final` | 1.950 | `codigo_departamento`, `nivel_formacion`, `anio` |
| `gold.gold_variaciones_anuales` | 1.762 | `codigo_departamento`, `nivel_formacion`, `anio` |
| `gold.gold_top20_departamentos` | 407 | `codigo_departamento`, `nivel_formacion`, `anio` |
| `gold.gold_indicadores_por_nivel_anio` | 60 | `nivel_formacion`, `anio` |
| `gold.gold_resumen_calidad` | 8 | `metrica` |
| `gold.dim_departamento` | 33 | `codigo_departamento` (código → nombre; 32 departamentos y Bogotá D.C.) |
| `gold.historial_cargas` | +6 por corrida | `id` (no se borra; una fila por tabla en cada carga) |

**Integridad referencial.** `gold_final.codigo_departamento` → `dim_departamento`; y `gold_variaciones_anuales` y `gold_top20_departamentos` (`codigo_departamento`, `nivel_formacion`, `anio`) → `gold_final`. Una fila huérfana hace fallar la carga completa y no queda nada a medias. Hay además un índice `ix_gold_final_nivel_anio` para las consultas por nivel y año.

**Persistencia histórica.** Las tablas de Gold siempre reflejan la última carga; la historia de las cargas queda en `gold.historial_cargas`. Para verla:
```powershell
docker compose exec postgres-dw psql -U desercion -d desercion_dw -c "SELECT corrida, tabla, filas, cargado_utc FROM gold.historial_cargas ORDER BY id DESC LIMIT 12;"
```

Desde la terminal (la primera vez que se carga debe devolver 1950, y sigue en 1950 tras cada nueva corrida):
```powershell
docker compose exec postgres-dw psql -U desercion -d desercion_dw -c "SELECT count(*) FROM gold.gold_final;"
```
Desde un cliente como DBeaver o pgAdmin: servidor `localhost`, puerto `5433`, base `desercion_dw`, usuario `desercion` y la contraseña de `DW_PASSWORD`.

## API (FastAPI)
La API está en `api/main.py` y lee los CSV de `data/gold/`. Desde la raíz del proyecto, con el entorno virtual creado en *Ejecución como script*:
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn api.main:app --reload
```
Se abre en `http://127.0.0.1:8000`. FastAPI genera sola la documentación interactiva en **`http://127.0.0.1:8000/docs`**, donde se prueban los endpoints directamente en el navegador.

| Endpoint | Qué devuelve |
|---|---|
| `GET /` | Mensaje de bienvenida y rutas disponibles. |
| `GET /gold` | `total_registros`, `total_columnas`, `Nombre_columnas` y `Data` (todas las filas de `gold_final`). |
| `GET /gold/data` | Solo `Data`, las filas de `gold_final`. |
| `GET /gold/indicadores` | `Data` con los indicadores por nivel de formación y año. |
| `GET /health` | `{"api": "OK", "Archivo": true}`; `Archivo` indica si existe `gold_final.csv`. |

Códigos de respuesta: 200 correcto; 404 si `gold_final.csv` no existe (se ejecuta primero el pipeline) o si la ruta no existe (por ejemplo, `/healt`).

**Datos.** Los nulos de pandas salen como `null` en el JSON y `codigo_departamento` se lee como texto para no perder el cero inicial (`05`). La API es de solo lectura, no se conecta a PostgreSQL y no maneja contraseñas. Para publicarla fuera del equipo (AWS, Azure o Google Cloud, con dominio y hosting propios) deben sumarse HTTPS y el control de acceso correspondiente; eso no está incluido.

## Dashboard (Streamlit)
Consume la API (no lee archivos ni la base). Con la API encendida, en otra terminal:
```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard/app_dashboard.py
```
Se abre en `http://localhost:8501`. Variable opcional: `API_URL` (por defecto `http://127.0.0.1:8000`). El dashboard llama a `/health`, `/gold/data` y `/gold/indicadores`.

Contenido: un recuadro «¿Cómo leer este tablero?» y cuatro secciones, cada una con un resumen en palabras bajo la gráfica: 1. Resumen del nivel y año elegidos (promedio, tasa más alta y más baja), 2. ¿Cómo ha cambiado con los años? (evolución del promedio), 3. ¿Dónde hay más deserción? (los 10 departamentos con mayor tasa) y 4. Mira un departamento en particular (su serie anual y su comparación con el promedio). Las gráficas muestran el valor exacto al pasar el mouse. Filtros en la barra lateral: nivel de formación y año. La fuente solo publica porcentajes, por eso el tablero habla de «de cada 100 estudiantes» y no de cantidad de personas. Bogotá D.C. aparece junto a los 32 departamentos porque la fuente la cuenta aparte de Cundinamarca; el tablero lo explica en el recuadro «¿Cómo leer este tablero?».

## Parametrización de la API, el Excel y la base de datos
- **API de matrícula departamental:** `src/bronze_matricula_departamental.py`. `RECURSO` identifica el conjunto de datos en datos.gov.co (`4hrb-y62g`); de él salen `URL_DATOS` y `URL_METADATA`. `LIMITE` (50.000) es el máximo de registros por consulta; si se supera, la extracción se detiene.
- **Excel de deserción:** `src/bronze.py`. `RUTA_EXCEL` (`data/raw/articles-415244_recurso_19.xlsx`) y `HOJA_EXCEL` (`TD - departamento`). Si lo reemplazas, mantén los bloques por nivel de formación y los años esperados.
- **API FastAPI:** `api/main.py`. `RUTA_GOLD` y `RUTA_INDICADORES` apuntan a los CSV de `data/gold/`.
- **Niveles, años y rutas:** `src/config.py` (`NIVELES_ESPERADOS`, `ANIOS_ESPERADOS` y rutas de raw, bronze, silver y gold).
- **Frecuencia y reintentos:** `airflow-medallon/dags/etl_desercion_hourly.py`.
- **Base de datos de Gold:** variables de entorno `DW_NAME`, `DW_USER` y `DW_PASSWORD` en `airflow-medallon/.env`. `docker-compose.yaml` define `DW_HOST` (`postgres-dw`) y `DW_PORT` (`5432`) para los contenedores.

## Ejecución como script (sin Airflow)
Desde la raíz:
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Primera descarga o actualización de matrícula:
```powershell
.\.venv\Scripts\python.exe main.py --actualizar-api
```

Reproducción con el bronze departamental local:
```powershell
.\.venv\Scripts\python.exe main.py
```
Esta opción reutiliza bronze, no reconstruye matrícula desde el JSON raw. Para demostrar el consumo de la API se utiliza `--actualizar-api`.

Las siete etapas son: Excel/bronze, API o bronze local, silver deserción, silver matrícula, integración, gold e indicadores. Si falla una etapa, se devuelve un código distinto de cero. Pueden permanecer salidas anteriores: el pipeline no es una transacción atómica.

Carga a PostgreSQL desde el script (valida Gold y lo carga, igual que las tareas `validate_gold` y `load_gold_postgres` del DAG). Requiere `postgres-dw` encendido:
```powershell
$env:DW_PASSWORD = (Select-String -Path airflow-medallon\.env -Pattern '^DW_PASSWORD=').Line.Split('=',2)[1]
.\.venv\Scripts\python.exe main.py --cargar
```
La primera línea lee `DW_PASSWORD` de `airflow-medallon/.env` y la guarda solo en esa terminal (hay que ejecutarla desde la raíz del proyecto). Sin `--cargar`, el script no valida ni carga a la base de datos. `DW_HOST` (`localhost`), `DW_PORT` (`5433`), `DW_NAME` (`desercion_dw`) y `DW_USER` (`desercion`) tienen esos valores por defecto en el equipo local.

## Salidas principales
### Bronze
- bronze_desercion_departamento.csv
- excel_extraido/td_departamento.csv
- notas_desercion_departamento.json
- trazabilidad_excel.json
- bronze_matricula_departamental.csv
- diagnostico_matricula_departamental.json
- corridas/<corrida>/ (Airflow): respuesta original de la API, hoja del Excel y manifiestos de cada corrida

### Silver
- silver_desercion_departamento.csv
- calidad_desercion_departamento.json
- silver_matricula_departamental.csv
- matricula_departamental_claves_invalidas.csv
- matricula_departamental_por_revisar.csv
- calidad_matricula_departamental.json
- silver_integrado.csv
- calidad_integracion.json
- desercion_territorios_sin_correspondencia.csv

### Gold
- gold_final.csv
- gold_variaciones_anuales.csv
- gold_top20_departamentos.csv
- gold_indicadores_por_nivel_anio.csv
- gold_resumen_calidad.csv
- calidad_gold.json

Las salidas se regeneran. Silver de deserción y gold_final conservan respaldos; no todos los archivos tienen versionado automático.

## Interpretación de indicadores
- tasa_media_simple_pct: promedio no ponderado de tasas departamentales; no tasa nacional.
- tasa_mediana_pct, tasa_minima_pct, tasa_maxima_pct: distribución disponible por nivel y año.
- cambio_anual_medio_pp: promedio de cambios de departamentos comparables. No necesariamente coincide con restar medias de años con distinta cobertura.
- disponibilidad_tasa_pct: proporción con tasa dentro de las filas presentes.
- cobertura_cruce_pct: coincidencia de claves, no validación metodológica.

No se usan cifras de matrícula para ponderar tasas ni estimar desertores.

### Tabla de KPI (capa Gold)
Archivo: `data/gold/gold_indicadores_por_nivel_anio.csv` (una fila por nivel de formación y año; 60 filas). Los valores de ejemplo corresponden a Universitario en 2020.

| KPI (columna) | Definición | Fórmula | Columnas utilizadas | Valor de ejemplo |
|---|---|---|---|---|
| Tasa media simple (`tasa_media_simple_pct`) | Promedio no ponderado de las tasas de deserción de los departamentos | `mean(tasa_desercion_porcentaje)` | `tasa_desercion_porcentaje` | 8,89 % |
| Tasa mediana (`tasa_mediana_pct`) | Mediana de las tasas departamentales | `median(tasa_desercion_porcentaje)` | `tasa_desercion_porcentaje` | 8,29 % |
| Tasa mínima y máxima (`tasa_minima_pct`, `tasa_maxima_pct`) | Menor y mayor tasa departamental | `min()` y `max()` | `tasa_desercion_porcentaje` | 3,13 % y 20,91 % |
| Cambio anual medio (`cambio_anual_medio_pp`) | Promedio de la variación en puntos porcentuales respecto al año anterior, solo en departamentos con ambas tasas | `mean(variacion_desercion_pp)`, con `variacion_desercion_pp = (tasa_t − tasa_t−1) × 100` | `variacion_desercion_pp` | −0,62 pp |
| Disponibilidad de tasa (`disponibilidad_tasa_pct`) | Proporción de departamentos con tasa dentro de los presentes | `departamentos_con_tasa / departamentos_presentes × 100` | `departamentos_con_tasa`, `departamentos_presentes` | 100 % |
| Cobertura del cruce (`cobertura_cruce_pct`) | Proporción de departamentos cuya clave coincide con la matrícula | `coincidencias_matricula / departamentos_presentes × 100` | `coincidencias_matricula`, `departamentos_presentes` | 100 % |

## Ejecución local verificada
Resultados compartidos del 17 de octubre de 2026, 15:43:

| Resultado | Cantidad |
|---|---:|
| Filas bronze de deserción | 130 |
| Observaciones gold | 1.950 |
| Tasas disponibles | 1.901 |
| No aplicables | 49 |
| Sin dato | 0 |
| Registros originales API departamental | 1.134 |
| Copias eliminadas | 567 |
| Claves inválidas separadas tras deduplicar | 6 |
| Filas departamento × año de matrícula | 561 |
| Filas silver de matrícula por nivel | 1.683 |
| Filas silver de matrícula con decimales | 3 |
| Coincidencias de matrícula | 1.164 |
| Coincidencias técnicas | 1.161 |
| Coincidencias con matrícula por revisar | 3 |
| Filas TyT sin equivalencia | 495 |
| Filas fuera de cobertura según estado exclusivo | 291 |
| Pares con tasa y matrícula sin alertas técnicas | 1.131 |
| Variaciones anuales | 1.762 |
| Selecciones top 20 % departamental | 407 |
| Indicadores por nivel y año | 60 |

Las 407 selecciones no son departamentos únicos. Los conteos pueden cambiar al actualizar las fuentes.

## Notebook y evidencias
Abrir `notebooks/analisis_gold.ipynb`, seleccionar `.venv`, ejecutar todas las celdas y guardar. El notebook muestra reportes, trazabilidad, validaciones, indicadores, faltantes, gráficas y conclusiones. No ejecuta el pipeline ni modifica los datos.

Las figuras se muestran dentro del notebook, sin carpeta figures. Después de regenerar gold, el notebook debe ejecutarse nuevamente.

Evidencias para la entrega:
1. Las siete etapas y finalización de main.py.
2. Lectura del Excel, trazabilidad y descarga de API.
3. Validaciones e indicadores del notebook.
4. Cobertura del cruce y alertas.
5. Gráficas, rankings, variaciones y conclusiones.

Las advertencias de openpyxl sobre áreas de impresión no impidieron leer la hoja ni finalizar la ejecución verificada.

## Pruebas técnicas
Las pruebas están en `test/` (pytest) y registran caso, resultado esperado y resultado obtenido en `docs/PRUEBAS.md`.

| Archivo | Qué prueba |
|---|---|
| `test_transformaciones.py` | Limpieza y normalización (nombres, booleanos, números): datos correctos, incorrectos y casos límite. |
| `test_validacion.py` | Validación de calidad de Gold con copias alteradas: duplicados, tasas fuera de rango, columnas o archivos ausentes, Gold vacío. |
| `test_carga.py` | Tipos SQL y carga a PostgreSQL en un esquema temporal: llaves foráneas, repetición sin duplicados, historial, rollback ante errores e integración base de datos y API (mismo número de filas). |
| `test_api.py` | Endpoints de `api/main.py`: `/health`, `/gold`, `/gold/data`, `/gold/indicadores`, código con cero inicial, JSON sin NaN, 404 con Gold ausente y, si está `httpx`, `/docs` y ruta inexistente. |
| `test_orquestacion.py` | Configuración y tareas del DAG (frecuencia, reintentos, `catchup`, `max_active_runs`) e identificador de corrida. |

Las pruebas trabajan sobre copias de `data/gold`, nunca sobre los datos reales, y las de base de datos usan el esquema temporal `gold_prueba`, que se borra solo. Ejecución desde la raíz:
```powershell
.\.venv\Scripts\python.exe -m pytest -v
```
Sin PostgreSQL disponible, las pruebas de carga se omiten. Para ejecutarlas todas: `$env:DW_PASSWORD = (Select-String -Path airflow-medallon\.env -Pattern '^DW_PASSWORD=').Line.Split('=',2)[1]` (con `postgres-dw` activo en el puerto 5433) y volver a ejecutar `pytest`.

La orquestación real (Trigger, ejecución programada, falla y reintentos) se prueba en la interfaz de Airflow; los casos manuales están en `docs/PRUEBAS.md`.

## Feedback de usuarios y cambios
El 2026-11-11 le mostré el dashboard a dos personas que no son técnicas: mi mamá, que se dedica a la odontología, y un amigo que estudia en la universidad. Los dos me dieron casi los mismos comentarios: que mejorara la manera de poner los títulos para que se entendieran mejor las gráficas y que pusiera un resumen de lo que quiere decir cada una, para las personas que no entienden. También me dijeron que la última gráfica no se entendía bien.

Con eso reorganicé el dashboard (secciones con títulos en forma de pregunta, un recuadro «¿Cómo leer este tablero?» y un resumen en palabras debajo de cada gráfica). Cuando se lo volví a mostrar dijeron que estaba mejor, pero tenían seguro que son 32 departamentos y yo había puesto 33, y que en los resúmenes se repetían muchas palabras. Revisé los datos: el 33 estaba bien porque la fuente cuenta aparte a Bogotá D.C., así que cambié el nombre a «32 departamentos y Bogotá D.C.» y reescribí los resúmenes con mejores conectores.

Todo lo que me dijeron, lo que cambié y cómo lo comprobé está en `docs/FEEDBACK_USUARIOS.md`.

## Evidencias de la entrega
| Categoría | Dónde está |
|---|---|
| Código ETL | `src/`, `main.py` |
| Pruebas técnicas y orquestación | `test/`, `docs/PRUEBAS.md`, `airflow-medallon/dags/etl_desercion_hourly.py`, capturas de Airflow |
| Carga y almacenamiento | PostgreSQL (esquema `gold`), `gold.historial_cargas`, capturas de las consultas de *Consultar Gold en PostgreSQL* |
| Dashboard y API | `dashboard/app_dashboard.py`, `api/main.py`, capturas de `/docs` y del dashboard |
| Documentación y demo | Este README, `docs/`, `requirements.txt`, repositorio en GitHub (https://github.com/juangrueso24/etl_desercion), demostración con el guion de `docs/CHECKLIST_EVIDENCIAS.md` |

El checklist del docente, punto por punto y con su evidencia, está en `docs/CHECKLIST_EVIDENCIAS.md`. Las capturas de las pruebas, la base de datos, la API y el dashboard están en `docs/EVIDENCIAS.md`.

## Conclusión
Con este proyecto pude juntar en un solo lugar dos fuentes públicas de datos sobre la deserción y la matrícula en la educación superior de Colombia, que antes estaban separadas. Al final quedó una tabla con 1.950 datos (por departamento, nivel de formación y año, de 2010 a 2024) que se revisa antes de guardarse y queda en una base de datos.

Con esos datos se puede ver cuánta deserción hay (por ejemplo, en el nivel universitario en 2020 dejaron de estudiar en promedio 8,9 de cada 100 estudiantes), en qué departamentos es mayor y cómo ha cambiado con los años.

Lo que más me sirvió fue ver todo el proceso funcionando solo: Airflow lo ejecuta cada hora y, cuando le quité el Excel a propósito, falló, volvió a intentarlo y se recuperó apenas lo devolví. También aprendí que un dato bien calculado no sirve de mucho si la gente no entiende qué está viendo. Mi mamá y un amigo me dijeron que las gráficas no se entendían del todo y que hacía falta un resumen de lo que quiere decir cada una. Con eso cambié los títulos, agregué un resumen en palabras debajo de cada gráfica y expliqué por qué salen 33 lugares (32 departamentos y Bogotá). Después me dijeron que estaba mejor, y a mí también me gustó más cómo quedó.

Lo que no se puede saber con estos datos: la matrícula solo llega hasta 2021, para TyT no hay matrícula comparable, los promedios no son la tasa de todo el país y la fuente da porcentajes, no cantidad de personas. Tampoco dice por qué dejan de estudiar.

## Limitaciones y alcance académico
- No hay datos institucionales ni un indicador de permanencia procesado.
- No se estima permanencia como 100 menos deserción.
- No se calculan cantidades de desertores ni riesgo individual.
- La visualización conjunta es exploratoria, no causal.
- Matrícula observada termina en 2021. TyT no tiene equivalencia definida.
- Según la nota de la hoja, desde 2019 se excluye al SENA de deserción tecnológica; no se supone igual ajuste en matrícula.
- Guaviare y Vaupés no tienen filas de Técnico Profesional según la nota de la fuente.
- Los promedios simples no son tasas nacionales ponderadas.
- El notebook evalúa las diez preguntas originales y no declara alcanzado el 90 % cuando faltan datos.

La directriz técnica Excel + API, transformación, JOIN, gold e indicadores está implementada en código. La evidencia final requiere ejecutar y guardar el notebook. Esto no equivale a cumplir todos los objetivos amplios del Avance 1: los que requieren otras fuentes siguen pendientes o necesitan reformulación aprobada por el docente.

## Entrega y control de versiones
Incluir código activo, requirements, README, notebook ejecutado y las entradas/salidas requeridas para reproducir y evaluar. No incluir `.venv` ni `__pycache__`.

Si `.gitignore` excluye data o logs, esos archivos no se añadirán automáticamente a GitHub. Verificar que las entradas y evidencias necesarias estén publicadas o se proporcionen mediante un mecanismo documentado. Lo visible localmente no necesariamente está en el repositorio.

La carga a PostgreSQL se realiza desde el DAG de Airflow (tarea `load_gold_postgres`) o con `python main.py --cargar`.

Para que el repositorio sea ejecutable al clonarlo, `.gitignore` conserva excluidas las salidas regenerables (`data/bronze`, `data/silver`, `data/gold` y los logs de Airflow) pero incluye el Excel de entrada `data/raw/articles-415244_recurso_19.xlsx`. Quien clone el repositorio regenera Bronze, Silver y Gold con `python main.py --actualizar-api` o con el DAG.

## Seguridad
- `airflow-medallon/.env` contiene secretos locales (clave Fernet y contraseña de la base de datos) y no se entrega ni se sube a GitHub; se entrega `.env.example` con valores de ejemplo.
- `airflow-medallon/config/airflow.cfg` contiene solo valores de ejemplo; los parámetros que aplican a los contenedores se definen en `docker-compose.yaml`.
- `airflow` / `airflow` (interfaz web y base de datos de Airflow) son credenciales de desarrollo local del `docker-compose.yaml`. No las uses fuera del laboratorio.
- La API de datos.gov.co es pública y no requiere credenciales. Ninguna clave está escrita en el código: la conexión a PostgreSQL se lee de variables de entorno.
- La API FastAPI es de solo lectura, lee solo los CSV de Gold y no maneja credenciales. `DW_PASSWORD` se define como variable de entorno, no en el código ni en el repositorio.

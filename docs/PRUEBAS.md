# Pruebas técnicas — registro de casos, resultados esperados y obtenidos

Proyecto: ETL de deserción y matrícula en educación superior (Excel + API → Bronze → Silver → Gold → PostgreSQL; Gold → API → dashboard).

## Cómo se ejecutan

Desde la raíz del proyecto:

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

Las pruebas usan copias de `data/gold` (no tocan los datos reales). Las de PostgreSQL usan el esquema temporal `gold_prueba`, que se borra solo, y se omiten si no hay base disponible: para ejecutarlas, deja activo el contenedor `postgres-dw` y define `$env:DW_PASSWORD = (Select-String -Path airflow-medallon\.env -Pattern '^DW_PASSWORD=').Line.Split('=',2)[1]` antes de `pytest`.

## Resultado de la ejecución registrada

- Fecha: 11/11/2026.
- Entorno: Windows, Python 3.13.13, pytest 9.2.0, con la base PostgreSQL del contenedor `postgres-dw` activa. La salida completa de `pytest -v` está en `docs/capturas/27-pytest-53-passed.txt`.
- Casos automatizados: **53**; pasaron **53**; omitidos 0; fallidos 0.
- Hubo 1 aviso de `httpx` con `starlette.testclient` (un aviso de obsolescencia de las librerías) que no afecta los resultados.

Formato de cada caso: **tipo** (válido, incorrecto, límite, integración), **caso** (entrada o situación) y **resultado esperado**.

## Limpieza y transformación (Silver / Gold) (`test/test_transformaciones.py`)

| ID | Tipo | Función | Caso | Resultado esperado | Resultado obtenido |
|---|---|---|---|---|---|
| T01 | válido | `normalizar_texto` | '  Bogotá,  D.C. ' | 'BOGOTA, D.C.' | PASÓ |
| T02 | válido | `normalizar_texto` | 'Nariño' | 'NARINO' (sin tilde ni ñ) | PASÓ |
| T03 | incorrecto | `normalizar_texto` | None | valor nulo (pd.NA), sin error | PASÓ |
| T04 | límite | `normalizar_texto` | '   ' | cadena vacía | PASÓ |
| T05 | válido | `normalizar_departamento` | ' Norte de Santander ' | 'NORTE DE SANTANDER' | PASÓ |
| T06 | válido | `nombre_canonico` | 'Guajira' | 'LA GUAJIRA' (alias unificado) | PASÓ |
| T07 | válido | `nombre_canonico` | 'Bogotá D.C' | 'BOGOTA D.C.' | PASÓ |
| T08 | incorrecto | `nombre_canonico` | None | valor nulo, sin error | PASÓ |
| T09 | válido/límite | `convertir_booleano` | ['True',' false ','TRUE',''] | True, False, True, nulo | PASÓ |
| T10 | incorrecto | `convertir_booleano` | ['talvez'] | ValueError | PASÓ |
| T11 | límite | `leer_booleano (integración)` | ['True',''] | ValueError (aquí no se admiten vacíos) | PASÓ |
| T12 | válido/límite | `convertir_numero` | ['1.5',' 2 ',''] | 1.5, 2.0, nulo | PASÓ |
| T13 | incorrecto | `convertir_numero` | ['abc'] | ValueError | PASÓ |

## Validación de calidad de Gold (`test/test_validacion.py`)

| ID | Tipo | Función | Caso | Resultado esperado | Resultado obtenido |
|---|---|---|---|---|---|
| V01 | válido | `validar_gold` | Gold real sin modificar | pasa y devuelve el reporte (0 duplicados) | PASÓ |
| V02 | incorrecto | `validar_gold` | una fila repetida en gold_final | ValueError (Validación de Gold fallida) | PASÓ |
| V03 | límite | `validar_gold` | tasa_desercion = 1.5 (máximo permitido 1) | ValueError 'fuera del rango' | PASÓ |
| V04 | incorrecto | `validar_gold` | matricula_reportada = -5 | ValueError 'matrículas negativas' | PASÓ |
| V05 | incorrecto | `validar_gold` | gold_final sin la columna tasa_desercion | ValueError 'Faltan columnas' | PASÓ |
| V06 | incorrecto | `validar_gold` | se borra gold_variaciones_anuales.csv | FileNotFoundError | PASÓ |
| V07 | límite | `validar_gold` | gold_final solo con encabezado | ValueError 'vacío' | PASÓ |

## Carga y almacenamiento (PostgreSQL) (`test/test_carga.py`)

| ID | Tipo | Función | Caso | Resultado esperado | Resultado obtenido |
|---|---|---|---|---|---|
| C01 | válido | `tipo_sql` | columna codigo_departamento ['05','11'] | TEXT (no pierde el cero inicial) | PASÓ |
| C02 | válido | `tipo_sql` | anio ['2010','2024'] | INTEGER | PASÓ |
| C03 | límite | `tipo_sql` | ['1234567890'] (10 dígitos) | BIGINT | PASÓ |
| C04 | válido | `tipo_sql` | ['0.5','-1','2e-3'] | DOUBLE PRECISION | PASÓ |
| C05 | válido | `tipo_sql` | ['True','False',''] | BOOLEAN (los vacíos se ignoran) | PASÓ |
| C06 | límite | `tipo_sql` | ['',''] | TEXT | PASÓ |
| C07 | límite | `tipo_sql` | ['01','02'] en columna normal | TEXT (no se trata como número) | PASÓ |
| C08 | incorrecto | `tipo_sql` | ['1','a'] | TEXT | PASÓ |
| C09 | incorrecto | `_literal` | "o'brien" (comilla simple) | "'o''brien'" (evita inyección SQL) | PASÓ |
| C10 | válido | `sha256_archivo` | archivo con el texto 'abc' | huella SHA-256 conocida | PASÓ |
| C11 | válido | `cargar_gold` | Gold real en esquema de prueba | cada tabla con las filas de su CSV; dim_departamento; 3 llaves foráneas; 6 filas de historial | PASÓ |
| C12 | límite | `cargar_gold` | código de departamento '05' | queda como texto '05' en la base | PASÓ |
| C13 | válido | `cargar_gold` | se carga dos veces | mismas filas en las tablas; el historial crece a 12 filas | PASÓ |
| C14 | incorrecto | `cargar_gold` | una fila de variaciones con llave que no existe en gold_final | error de llave foránea y no queda nada cargado (rollback) | PASÓ |
| C15 | incorrecto | `cargar_gold` | segunda carga con llave huérfana tras una carga buena | la carga falla y los datos de la primera siguen intactos | PASÓ |
| C16 | límite | `cargar_gold` | gold_indicadores_por_nivel_anio.csv solo con encabezado | ValueError 'vacío' y nada queda cargado | PASÓ |
| C17 | integración | `API y cargar_gold()` | Se carga Gold en PostgreSQL y se consulta /gold | Filas de /gold = filas de gold.gold_final = filas del CSV | PASÓ |

## API FastAPI (`test/test_api.py`)

| ID | Tipo | Función | Caso | Resultado esperado | Resultado obtenido |
|---|---|---|---|---|---|
| A01 | válido | `health()  (GET /health)` | Gold disponible | `{"api": "OK", "Archivo": true}` | PASÓ |
| A02 | incorrecto | `health()  (GET /health)` | gold_final.csv no existe | `{"api": "OK", "Archivo": false}`: la API sigue arriba y avisa que falta el archivo | PASÓ |
| A03 | válido | `consultar_gold_completo()  (GET /gold)` | Gold completo | total_registros, total_columnas, Nombre_columnas y Data coinciden con el CSV | PASÓ |
| A04 | válido | `consultar_solo_data()  (GET /gold/data)` | Gold completo | Solo la llave Data, con todas las filas de gold_final | PASÓ |
| A05 | válido | `consultar_indicadores()  (GET /gold/indicadores)` | Indicadores por nivel y año | Data con las filas de gold_indicadores_por_nivel_anio.csv | PASÓ |
| A06 | límite | `consultar_solo_data()  (GET /gold/data)` | Código de departamento con cero inicial | El código sigue como texto de 2 dígitos ('05' no pasa a 5) | PASÓ |
| A07 | límite | `GET /gold y GET /gold/indicadores` | Tasas vacías (NaN) en los datos | JSON válido: los nulos salen como null y json.dumps(allow_nan=False) no falla | PASÓ |
| A08 | incorrecto | `consultar_gold_completo()  (GET /gold)` | No existe gold_final.csv | HTTPException 404 con el mensaje de ejecutar primero el pipeline | PASÓ |
| A09 | límite | `preparar_dataframe_json()` | DataFrame con NaN y None | Esas celdas quedan en None y el DataFrame original no se modifica | PASÓ |
| A10 | integración | `app de api/main.py (TestClient)` | /health, /docs y una ruta inexistente (/healt) | 200, 200 y 404 | PASÓ |

## Orquestación (Airflow) (`test/test_orquestacion.py`)

| ID | Tipo | Función | Caso | Resultado esperado | Resultado obtenido |
|---|---|---|---|---|---|
| O01 | válido | `DAG etl_desercion_hourly` | lectura del archivo | schedule '0 * * * *', catchup=False, max_active_runs=1, retries=2 y retry_delay de 5 minutos | PASÓ |
| O02 | válido | `DAG etl_desercion_hourly` | lectura del archivo | las 6 tareas en orden: extract_api_bronze, extract_excel_bronze, transform_silver, build_gold, validate_gold, load_gold_postgres | PASÓ |
| O03 | límite | `_identificador_corrida` | fuera de Airflow (sin run_id) | usa la fecha y hora UTC (AAAAMMDD_HHMMSS) | PASÓ |
| O04 | válido | `_identificador_corrida` | run_id de Airflow 'manual__2026-11-06T23:07:44+00:00' | 'manual__2026-11-06T23_07_44_00_00' (sin caracteres inválidos para carpetas) | PASÓ |
| O05 | límite | `_limpiar_respaldos` | 15 respaldos en la carpeta | quedan solo los 10 más recientes | PASÓ |
| O06 | incorrecto | `_limpiar_respaldos` | la carpeta no existe | no lanza error | PASÓ |

## Pruebas manuales de orquestación, API y dashboard

Se hacen en el entorno real (Docker, navegador). Cada una debe quedar con su captura en la carpeta de evidencias de la entrega. Marca el resultado cuando la ejecutes.

| ID | Prueba | Pasos | Resultado esperado | Evidencia | Resultado obtenido |
|---|---|---|---|---|---|
| M01 | Ejecución manual del DAG | Airflow → `etl_desercion_hourly` → Trigger. | Las 6 tareas en verde en la vista Graph. | Captura del Graph | Hecha (11-nov-2026): las 6 tareas en verde. Capturas 01 y 03. |
| M02 | Ejecución programada | Dejar el DAG activo y esperar a la hora en punto (UTC). | Aparece una corrida `scheduled__...` en verde sin intervención. | Captura de la lista de ejecuciones | Hecha: las corridas programadas de las 16:00, 17:00 y 18:00 (hora de Colombia) quedaron en verde sin intervención. Captura 02. |
| M03 | Falla inducida y reintentos | Renombrar temporalmente `data/raw/articles-415244_recurso_19.xlsx`, ejecutar el DAG (para verlo más rápido, bajar `retry_delay` en el DAG). | `extract_excel_bronze` falla, se reintenta 2 veces y `transform_silver`, `build_gold`, `validate_gold` y `load_gold_postgres` quedan en `upstream_failed`. | Capturas del Graph y del log de la tarea fallida | Hecha: `extract_excel_bronze` falló en sus 3 intentos (el original y 2 reintentos) con «No se encontró el Excel original»; la corrida quedó en Fallido, las 4 tareas siguientes en `upstream_failed` y `extract_api_bronze` en verde. Capturas 04, 05, 06 y 06b. |
| M04 | Recuperación tras la falla | Restaurar el nombre del Excel y volver a ejecutar el DAG. | Las 6 tareas en verde; no quedan datos a medias en PostgreSQL. | Captura del Graph | Hecha: con el Excel de vuelta (misma huella SHA-256) la corrida terminó con las 6 tareas en verde. Captura 07. |
| M05 | Carga en PostgreSQL | `docker compose exec postgres-dw psql -U desercion -d desercion_dw -c "SELECT count(*) FROM gold.gold_final;"` tras la corrida; repetir tras una segunda corrida. | 1950 filas en ambas consultas (no se duplican); `gold.historial_cargas` suma 6 filas por corrida. | Captura de las consultas | Hecha: `gold.gold_final` con 1950 filas después de la primera corrida y otra vez en una corrida programada posterior, sin duplicar (capturas 09 y 08). `gold.historial_cargas` suma 6 filas por corrida: 12 filas para las dos últimas corridas (captura 29). |
| M06 | Carga desde el script | Con `postgres-dw` encendido y `DW_PASSWORD` definida: `python main.py --cargar`. | Termina con el mensaje `Gold cargado en PostgreSQL.` y `gold.gold_final` sigue con 1950 filas. | Salida de la terminal | Hecha: el primer intento se detuvo con «Falta la variable de entorno DW_PASSWORD» porque la terminal no la tenía (corrección 6; captura 28a). Con la clave cargada, el script validó Gold, cargó las seis tablas (`gold.gold_final`: 1950 filas) y terminó con «Gold cargado en PostgreSQL.» en 4,42 segundos. Captura 28. |
| M07 | API en el navegador | `uvicorn api.main:app --reload`, abrir `http://127.0.0.1:8000/docs` y probar `/health`, `/gold`, `/gold/data` y `/gold/indicadores`. | 200 con los datos; `/health` devuelve `{"api": "OK", "Archivo": true}`; `/healt` devuelve 404. | Capturas de `/docs` y de cada respuesta | Hecha: `/docs`, `/health` (200), `/gold` (1950 registros, 31 columnas), `/gold/data`, `/gold/indicadores` y `/healt` (404). Capturas 12 a 18. |
| M08 | API sin Gold | Renombrar temporalmente `data/gold/gold_final.csv` y consultar `/gold` y `/health`; devolver el nombre después. | `/gold` responde 404 con el mensaje de ejecutar primero el pipeline y `/health` muestra `"Archivo": false`. | Capturas de las dos respuestas | Hecha: `/gold` responde 404 con «El archivo no existe, ejecuta primero el pipeline» y `/health` muestra `Archivo: false`. Después se devolvió el archivo (misma huella SHA-256). Capturas 19 y 20. |
| M09 | Dashboard | Con la API encendida, `streamlit run dashboard/app_dashboard.py`; cambiar nivel y año. | Los KPI, la evolución y el ranking cambian con los filtros y coinciden con la API. | Capturas del dashboard con dos combinaciones de filtros | Hecha: Universitario 2020 y Tecnológico 2024; los valores y los resúmenes cambian con los filtros y coinciden con los de la API. Capturas 21 a 25. |
| M10 | Dashboard sin API | Apagar la API y recargar el dashboard. | Mensaje de error claro indicando que la API no está encendida; sin pantalla en blanco. | Captura del mensaje | Hecha: mensaje claro con la API apagada, sin pantalla en blanco. Captura 26 (versión anterior del tablero, mismo mensaje). |

## Registro de correcciones

Errores encontrados al probar la orquestación y la carga, su corrección y la prueba que los verifica. Agrega aquí los que aparezcan en las pruebas manuales y con usuarios.

| # | Error encontrado | Corrección | Prueba que lo verifica |
|---|---|---|---|
| 1 | Al cargar a PostgreSQL, un código de departamento como `05` podía inferirse como entero y perder el cero inicial. | Las columnas `codigo_*` se cargan siempre como texto y los números con ceros a la izquierda no se tratan como numéricos. | C01, C07, C12 |
| 2 | La carpeta de Bronze por corrida no podía calcularse con la hora porque las dos extracciones corren en paralelo y obtenían carpetas distintas. | La carpeta y la corrida se identifican con el `run_id` de Airflow (la fecha y hora es solo el respaldo fuera de Airflow). | O03, O04 |
| 3 | Con llaves foráneas, `TRUNCATE` y `DROP TABLE` fallan sobre una tabla referenciada. | La carga usa `TRUNCATE ... CASCADE` y `DROP ... CASCADE` dentro de la misma transacción y vuelve a crear las llaves faltantes. | C11, C13 |
| 4 | Los valores vacíos (NaN) de las tasas hacían inválido el JSON de la API. | `preparar_dataframe_json` pasa los nulos de pandas a `None`, que salen como `null`. | A07, A09 |
| 5 | Las personas que vieron el dashboard tenían seguro que son 32 departamentos y decía 33. | Colombia tiene 32 departamentos y la fuente cuenta aparte a Bogotá D.C., así que el dato de 33 era correcto pero estaba mal nombrado. El dashboard ahora dice «32 departamentos y Bogotá D.C.» y lo explica en «¿Cómo leer este tablero?». | M09 (capturas 21 a 25) y `FEEDBACK_USUARIOS.md` sección 4 |
| 6 | Al ejecutar `python main.py --cargar` sin `DW_PASSWORD`, el script se detenía con «Falta la variable de entorno DW_PASSWORD», y el README solo traía un texto de relleno para esa línea. | El README ahora trae el comando de PowerShell que lee `DW_PASSWORD` de `airflow-medallon/.env` y la guarda solo en esa terminal. | M06 |

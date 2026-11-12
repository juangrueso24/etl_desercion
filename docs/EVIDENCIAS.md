# Evidencias del proyecto

Capturas del proyecto corriendo el 11 de noviembre de 2026: Airflow en `http://localhost:8080`, la API en `http://127.0.0.1:8000`, el dashboard en `http://localhost:8501` y PostgreSQL en el contenedor `postgres-dw`. Las imágenes están en `docs/capturas/` y siguen las evidencias mínimas del checklist: código ETL, pruebas, base de datos, dashboard y API, y demostración.

Cada prueba manual se describe en `docs/PRUEBAS.md` (M01 a M10) y cada punto del checklist en `docs/CHECKLIST_EVIDENCIAS.md`.

## 1. Código ETL

| Etapa | Dónde está |
|---|---|
| Bronze (extracción) | `src/bronze.py`, `src/bronze_matricula_departamental.py` |
| Silver (limpieza) | `src/silver*.py` |
| Integración y Gold | `src/integracion.py`, `src/gold.py`, `src/indicadores.py` |
| Validación | `src/validacion.py` |
| Carga a PostgreSQL | `src/carga_dw.py` |
| Orquestación | `airflow-medallon/dags/etl_desercion_hourly.py`, `src/orquestacion.py` |
| API | `api/main.py` |
| Dashboard | `dashboard/app_dashboard.py` |

## 2. Pruebas técnicas y orquestación

### 2.1 Pruebas automáticas (pytest)
Los 53 casos pasan. La salida completa de `pytest -v` está en [`27-pytest-53-passed.txt`](capturas/27-pytest-53-passed.txt) y termina así:

```
===================== 53 passed, 1 warning in 13.66s ======================
```

El aviso es de `httpx` con `starlette.testclient` y no afecta los resultados.

### 2.2 DAG en Airflow

**M01. Ejecución manual.** Las 6 tareas terminan en verde.

![Corrida manual exitosa](capturas/01-airflow-corrida-manual-exitosa.png)

![Vista Graph con las 6 tareas en verde](capturas/03-airflow-graph-corrida-exitosa.jpg)

**M02. Ejecución programada.** El DAG corre cada hora sin intervención: las corridas `scheduled__` de las 16:00, 17:00 y 18:00 (hora de Colombia) quedaron en verde, junto a la corrida manual.

![Corridas programadas en verde](capturas/02-airflow-corridas-programadas.jpg)

**M03. Falla inducida y reintentos.** Se renombró temporalmente `data/raw/articles-415244_recurso_19.xlsx`. La tarea `extract_excel_bronze` falla, Airflow la reintenta 2 veces (con 5 minutos entre cada reintento) y las tareas siguientes no se ejecutan. La rama de la API (`extract_api_bronze`) termina bien y la carga a PostgreSQL no se toca.

![Primer fallo: la tarea queda en «up_for_retry»](capturas/04-airflow-falla-reintento-graph.jpg)

![Log de la falla: no se encontró el Excel](capturas/05-airflow-falla-log-excel-no-encontrado.jpg)

![Resultado final: la corrida queda en «Fallido»; `extract_excel_bronze` falla y las 4 tareas siguientes quedan en «upstream_failed»](capturas/06-airflow-falla-final-graph.jpg)

![Los 3 intentos de la tarea (el original y 2 reintentos) fallan](capturas/06b-airflow-falla-tres-intentos.jpg)

**M04. Recuperación.** Se devolvió el nombre al Excel (el archivo quedó idéntico, con la misma huella SHA-256) y se volvió a ejecutar el DAG: las 6 tareas quedan en verde.

![Recuperación: las 6 tareas en verde](capturas/07-airflow-recuperacion-graph.jpg)

### 2.3 Pruebas de la API

**M07. Endpoints en el navegador.**

![Documentación /docs](capturas/12-api-docs.jpg)

![/health devuelve 200 desde /docs](capturas/13-api-health-docs-200.jpg)

![/health](capturas/14-api-health-raw.jpg)

![/gold: 1950 registros y 31 columnas](capturas/15-api-gold-completo.jpg)

![/gold/data](capturas/16-api-gold-data.jpg)

![/gold/indicadores](capturas/17-api-gold-indicadores.jpg)

![Una ruta que no existe (/healt) devuelve 404](capturas/18-api-ruta-inexistente-404.jpg)

**M08. API sin el archivo Gold.** Con `data/gold/gold_final.csv` renombrado temporalmente, `/gold` responde 404 con el mensaje de ejecutar primero el pipeline y `/health` muestra `"Archivo": false`. Después se devolvió el nombre al archivo.

![/gold sin archivo: 404](capturas/19-api-sin-gold-404.jpg)

![/health sin archivo](capturas/20-api-sin-gold-health-false.jpg)

## 3. Carga y almacenamiento (PostgreSQL)

**M05. Carga y conteo.** `gold.gold_final` tiene 1950 filas.

![Conteo de gold.gold_final](capturas/09-psql-count-gold-final.png)

Las 7 tablas del esquema `gold`:

![Tablas del esquema gold](capturas/10-psql-tablas-gold.png)

Las 3 llaves foráneas (integridad referencial):

![Llaves foráneas](capturas/11-psql-llaves-foraneas.png)

Carga repetida. En una corrida programada posterior, `load_gold_postgres` vuelve a cargar y `gold.gold_final` sigue en 1950 filas, es decir, no se duplican. Airflow pinta de naranja la palabra «ERROR» en las líneas que la tarea escribe por la salida de errores. El nivel real va dentro del texto (`| INFO |`) y la tarea terminó en verde.

![Log de load_gold_postgres](capturas/08-airflow-load-gold-log.jpg)

**M06. Carga desde el script.** Primero ejecuté `python main.py --cargar` sin definir `DW_PASSWORD`: el script se detuvo con «Falta la variable de entorno DW_PASSWORD» y no usó ninguna clave escrita en el código ([`28a-carga-sin-clave.txt`](capturas/28a-carga-sin-clave.txt)). Después de cargar la contraseña desde `airflow-medallon/.env`, validó Gold, cargó las seis tablas y terminó bien en 4,42 segundos. La salida completa está en [`28-carga-desde-script.txt`](capturas/28-carga-desde-script.txt) y termina así:

```
Cargada gold.gold_final: 1950 filas (archivo gold_final.csv)
Carga a PostgreSQL finalizada: {'gold.dim_departamento': 33, 'gold.gold_final': 1950, 'gold.gold_variaciones_anuales': 1762, 'gold.gold_top20_departamentos': 407, 'gold.gold_indicadores_por_nivel_anio': 60, 'gold.gold_resumen_calidad': 8}
PIPELINE FINALIZADO CORRECTAMENTE
Gold cargado en PostgreSQL.
```

## 4. Dashboard

El dashboard consume la API (`/health`, `/gold/data` y `/gold/indicadores`) y muestra los cambios hechos tras el feedback de los usuarios (`docs/FEEDBACK_USUARIOS.md`).

**M09. Dos combinaciones de filtros.** Universitario 2020:

![Universitario 2020: guía y resumen](capturas/21-dashboard-universitario-2020-resumen.jpg)

![Universitario 2020: evolución y Top 10](capturas/22-dashboard-universitario-2020-evolucion-ranking.jpg)

![Universitario 2020: un departamento (Vichada)](capturas/23-dashboard-universitario-2020-departamento.jpg)

Tecnológico 2024:

![Tecnológico 2024: guía y resumen](capturas/24-dashboard-tecnologico-2024-resumen.jpg)

![Tecnológico 2024: evolución y Top 10](capturas/25-dashboard-tecnologico-2024-evolucion-ranking.jpg)

**M10. Dashboard sin la API.** Con la API apagada, el dashboard muestra un mensaje claro y no una pantalla en blanco. Esta captura es de una versión anterior del tablero; el mensaje es el mismo.

![Dashboard sin API](capturas/26-dashboard-sin-api.png)

## 5. Feedback de usuarios

Le mostré el dashboard a mi mamá y a un amigo, en dos rondas el mismo día. `docs/FEEDBACK_USUARIOS.md` cuenta qué me dijeron, los siete cambios que hice en `dashboard/app_dashboard.py` por eso y cómo lo comprobé después. Las capturas 21 a 25 son del dashboard ya con los cambios.

## 6. Documentación y demostración

- Documentación: `README.md` (problema, arquitectura, instalación y ejecución), `docs/PRUEBAS.md`, `docs/CHECKLIST_EVIDENCIAS.md`.
- Dependencias: `requirements.txt`.
- Guion de la demostración de extremo a extremo: `docs/CHECKLIST_EVIDENCIAS.md` → *Guion de demostración*.
- Conclusión: `README.md` → *Conclusión*.

## Pendiente
- **M05:** consultar `gold.historial_cargas` (README → *Persistencia histórica*) y guardar la salida como `docs/capturas/29-psql-historial-cargas.txt`.
- **GitHub:** subir el proyecto sin `.env` a https://github.com/juangrueso24/etl_desercion.
- **Demostración:** ensayarla con el guion de `docs/CHECKLIST_EVIDENCIAS.md`.

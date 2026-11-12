# Checklist del docente — estado y evidencia

Este documento responde el checklist del proyecto ETL punto por punto, con la evidencia que está en el repositorio.

- **Listo:** existe en el repositorio (se indica dónde).

## 1. Problema y requisitos de datos
| # | Verificación | Estado | Evidencia / observaciones |
|---|---|---|---|
| 1.1 | Identificamos el problema y definimos los requerimientos de información. | Listo | README → *Problema, usuarios y objetivos*. |
| 1.2 | Consultamos a usuarios o fuentes para comprender sus necesidades. | Listo | Fuentes consultadas: Excel del MEN y datos.gov.co (README → *Fuentes activas*). Usuarios consultados: mi mamá (se dedica a la odontología) y un amigo (estudiante universitario), el 2026-11-11, en `docs/FEEDBACK_USUARIOS.md` (sección 1). |
| 1.3 | Definimos objetivo, alcance y KPIs / OKRs. | Listo | README → *Problema, usuarios y objetivos* y *Tabla de KPI*; estado de los OKR en `notebooks/analisis_gold.ipynb`. |
| 1.4 | Priorizamos las funcionalidades del MVP. | Listo | README → *MVP*. |
| 1.5 | Establecimos criterios verificables de aceptación. | Listo | README → *Criterios de aceptación* (cada uno con su forma de verificación). |

## 2. Extracción y captura de datos (Extract)
| # | Verificación | Estado | Evidencia / observaciones |
|---|---|---|---|
| 2.1 | Validamos integridad, calidad y disponibilidad de los datos de origen antes del procesamiento. | Listo | `main.py` (`validar_entradas`), conteos antes y después de la consulta en `src/bronze.py` y `src/bronze_matricula_departamental.py`, `data/bronze/diagnostico_matricula_departamental.json`, `data/bronze/trazabilidad_excel.json`. |
| 2.2 | Definimos las fuentes de datos y sus metadatos. | Listo | README → *Fuentes activas*; `data/raw/matricula_departamental_metadatos.json`; manifiestos de cada corrida en `data/bronze/corridas/`. |
| 2.3 | Aseguramos la gestión segura de credenciales, claves de API y tokens. | Listo | `.env` fuera de Git (`.gitignore`), `.env.example` sin secretos, conexión por variables de entorno. README → *Seguridad*. La API de datos.gov.co es pública y no usa token. |

## 3. Transformación y limpieza de datos (Transform)
| # | Verificación | Estado | Evidencia / observaciones |
|---|---|---|---|
| 3.1 | Transformaciones avanzadas: filtrado, agregación, enriquecimiento, joins y desnormalización. | Listo | `src/silver*.py` (filtrado, normalización, años a filas), `src/integracion.py` (LEFT JOIN), `src/gold.py` (variaciones, ranking, `gold_final` desnormalizada de 31 columnas), `src/indicadores.py` (agregación). |
| 3.2 | Arquitectura modular (Bronze, Silver, Gold). | Listo | `src/` y `data/bronze`, `data/silver`, `data/gold`. README → *Transformaciones y controles*. |
| 3.3 | Verificamos la coherencia lógica y la calidad de los datos resultantes. | Listo | `src/validacion.py` (tarea `validate_gold`), `data/*/calidad_*.json`, `test/test_validacion.py`. |

## 4. Carga, persistencia y almacenamiento (Load)
| # | Verificación | Estado | Evidencia / observaciones |
|---|---|---|---|
| 4.1 | Cargamos los datos en el sistema de almacenamiento destino. | Listo | PostgreSQL, esquema `gold` (`src/carga_dw.py`, tarea `load_gold_postgres` o `python main.py --cargar`). Capturas en `docs/EVIDENCIAS.md` (M05 y M06: `python main.py --cargar`). |
| 4.2 | Garantizamos la persistencia histórica y la integridad referencial. | Listo | `gold.historial_cargas` (no se borra), llaves primarias y foráneas, `gold.dim_departamento`. Pruebas C11 a C15. README → *Consultar Gold en PostgreSQL*. |
| 4.3 | Optimizamos el rendimiento del cargue. | Listo | `COPY` en lote, una sola transacción por carga e índice `ix_gold_final_nivel_anio`. |

## 5. Pruebas técnicas
| # | Verificación | Estado | Evidencia / observaciones |
|---|---|---|---|
| 5.1 | Casos de prueba para cada función crítica. | Listo | `test/` (53 casos) y `docs/PRUEBAS.md`. |
| 5.2 | Probamos datos correctos, incorrectos y casos límite. | Listo | Cada caso de `docs/PRUEBAS.md` indica su tipo (válido, incorrecto, límite). |
| 5.3 | Probamos la integración entre interfaz, lógica de negocio y almacenamiento. | Listo | Automatizada: C17 (base y API) y A10 (HTTP). Manuales con captura: M06 a M09 (`docs/EVIDENCIAS.md`). |
| 5.4 | Pruebas de orquestación mediante Apache Airflow (DAGs). | Listo | `airflow-medallon/dags/etl_desercion_hourly.py` y `test/test_orquestacion.py`. Capturas de M01 a M04 (Trigger, ejecución programada, falla con reintentos y recuperación) en `docs/EVIDENCIAS.md`. |
| 5.5 | Registramos resultado esperado, obtenido y evidencia por prueba. | Listo | `docs/PRUEBAS.md` (esperado y obtenido de los casos automatizados y de las pruebas manuales M01 a M10, con sus capturas en `docs/EVIDENCIAS.md`). |
| 5.6 | Corregimos errores y repetimos las pruebas. | Listo | `docs/PRUEBAS.md` → *Registro de correcciones* (6 correcciones) y pruebas repetidas en verde (53 casos, captura 27). |

## 6. Visualización de datos, automatismo y dashboards
| # | Verificación | Estado | Evidencia / observaciones |
|---|---|---|---|
| 6.1 | Validamos la usabilidad y la interpretación visual del dashboard con usuarios. | Listo | Se lo mostré a 2 personas que no son técnicas, en dos rondas el mismo día (2026-11-11): `docs/FEEDBACK_USUARIOS.md` (secciones 1 y 2). |
| 6.2 | Confirmamos que la visualización responde al problema inicial. | Listo | El dashboard muestra tasa por nivel y año, evolución y ranking de departamentos (README → *Dashboard*; capturas 21 a 25 de `docs/EVIDENCIAS.md`). Los dos usuarios dijeron que se entiende mejor (`docs/FEEDBACK_USUARIOS.md`, secciones 2 y 4). |
| 6.3 | Construimos y consumimos endpoints de API (FastAPI). | Listo | `api/main.py` (construcción); `dashboard/app_dashboard.py` (consumo). README → *API (FastAPI)*. |
| 6.4 | Recopilamos retroalimentación e implementamos mejoras. | Listo | `docs/FEEDBACK_USUARIOS.md` (sección 3): 7 puntos en dos rondas, con el cambio hecho en `dashboard/app_dashboard.py`. El dashboard ya ajustado está en las capturas 21 a 25 de `docs/EVIDENCIAS.md`. |
| 6.5 | Verificamos nuevamente el dashboard tras los ajustes. | Listo | Les volví a mostrar el dashboard a los dos y dijeron que estaba mejor; la revisión que hice yo en el dashboard en vivo está en `docs/FEEDBACK_USUARIOS.md` (sección 4) y las pruebas pasan (53 casos, captura 27). |

## 7. Documentación y presentación
| # | Verificación | Estado | Evidencia / observaciones |
|---|---|---|---|
| 7.1 | Entregamos el código fuente organizado y ejecutable (GitHub). | Listo | El código está organizado y `.gitignore` incluye el Excel de entrada para que el repositorio se ejecute al clonarlo. Repositorio: https://github.com/juangrueso24/etl_desercion (sin `.env`). |
| 7.2 | README con problema, funcionalidades, instalación y ejecución. | Listo | `README.md`. |
| 7.3 | Documentamos arquitectura, evidencias de pruebas y feedback del usuario. | Listo | Arquitectura: README → *Arquitectura*. Pruebas: `docs/PRUEBAS.md` y `docs/EVIDENCIAS.md`. Feedback de usuarios: `docs/FEEDBACK_USUARIOS.md`. |
| 7.4 | Registramos los cambios realizados después de las pruebas con usuarios. | Listo | `docs/FEEDBACK_USUARIOS.md` (sección 3): siete cambios con su fecha y el archivo modificado. |
| 7.5 | Preparamos una demostración de extremo a extremo. | Listo | Guion abajo; el sistema corre completo con los datos reales (capturas 01 a 28 de `docs/EVIDENCIAS.md`). |

## Evidencias mínimas para la entrega
| Categoría | Detalle | Dónde está |
|---|---|---|
| Código ETL | Scripts de extracción, transformación y carga | Listo: `src/`, `main.py` |
| Pruebas técnicas y orquestación | Casos, resultados, correcciones y DAGs de Airflow | Listo: `test/`, `docs/PRUEBAS.md`, DAG y capturas de Airflow en `docs/EVIDENCIAS.md` |
| Carga y almacenamiento | Base de datos con los datos cargados | Listo: PostgreSQL `gold`, capturas de las consultas (M05), de la carga desde el script (M06) y del historial de cargas (captura 29) |
| Dashboard y API | Interfaz interactiva y endpoints FastAPI | Listo: `dashboard/`, `api/main.py` y capturas de `/docs` y del dashboard en `docs/EVIDENCIAS.md` |
| Documentación y demo | README, repositorio, dependencias y demostración | Listo: README, `requirements.txt`, repositorio en GitHub (https://github.com/juangrueso24/etl_desercion) y guion de demostración |

## Guion de demostración (de extremo a extremo)
Se explican los resultados y se muestra el producto en uso, sin recorrer el código línea por línea.
1. **Problema y KPIs** (1 min): README → *Problema, usuarios y objetivos*.
2. **Airflow:** abrir `etl_desercion_hourly`, mostrar las 6 tareas, pulsar Trigger y ver el Graph en verde; abrir el log de `validate_gold` y el de `load_gold_postgres`.
3. **PostgreSQL:** `SELECT count(*) FROM gold.gold_final;` (1950), `\dt gold.*` y `gold.historial_cargas` (una corrida más).
4. **API:** `uvicorn api.main:app --reload` y `http://127.0.0.1:8000/docs`; probar `/health`, `/gold`, `/gold/data` y `/gold/indicadores`; mostrar un 404 (`/healt`).
5. **Dashboard:** cambiar nivel y año y explicar un hallazgo (por ejemplo, Universitario 2020: tasa media 8,89 %, entre 3,13 % y 20,91 %).
6. **Pruebas:** `pytest -v` y, si hay tiempo, la falla inducida y la recuperación (M03 y M04).
7. **Cierre:** conclusión (README → *Conclusión*), limitaciones y cambios hechos tras el feedback de los usuarios.

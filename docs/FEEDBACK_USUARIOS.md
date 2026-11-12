# Feedback de usuarios y cambios realizados

> Aquí dejo a quién le mostré el dashboard, qué me dijeron, qué cambié por eso y qué opinaron después. Responde los puntos 1.2, 6.1, 6.4, 6.5 y 7.4 del checklist.

## 1. Usuarios consultados (necesidades)
Le mostré el dashboard a dos personas que no son técnicas: mi mamá, que se dedica a la odontología, y un amigo que estudia en la universidad. Me sirvieron justo por eso, porque el dashboard tiene que poder entenderlo alguien que no sabe de datos. Los dos me dieron casi los mismos comentarios.

| # | Usuario (rol) | Fecha | Medio | Qué necesita saber o hacer |
|---|---|---|---|---|
| 1 | Mi mamá, que se dedica a la odontología | 2026-11-11 | Le mostré el dashboard y me dio su opinión | Entender las gráficas sin saber de datos: que los títulos le ayuden a entender cada gráfica y que haya un resumen en palabras de lo que quiere decir. |
| 2 | Un amigo, estudiante universitario | 2026-11-11 | Le mostré el dashboard y me dio su opinión | Lo mismo que mi mamá. |

Lo que me pidieron los dos, casi igual:
- Mejorar la manera de poner los títulos, para que las personas entiendan mejor las gráficas.
- Poner un resumen de lo que quiere decir cada gráfica, para las personas que no entienden.

## 2. Prueba del dashboard con usuarios
Se lo mostré a los dos en dos momentos del mismo día (11 de noviembre de 2026): primero la versión que tenía, y después la versión con los cambios que me pidieron.

| Ronda | Qué vieron | ¿Lo entendieron? | Qué me dijeron |
|---|---|---|---|
| 1 | La primera versión del dashboard | No del todo | La última gráfica no la entendían bien. Querían que mejorara la manera de poner los títulos para entender mejor las gráficas, y que pusiera un resumen de lo que quiere decir cada una, para las personas que no entienden. |
| 2 | La versión con los títulos nuevos, los resúmenes bajo las gráficas y el recuadro «¿Cómo leer este tablero?» | Sí, mejor | Dijeron que estaba mejor y que ya entendían más el dashboard. Pero tenían seguro que son 32 departamentos y el dashboard decía 33. Además me dijeron que en los resúmenes se repetían muchas palabras y que usara mejores conectores. |

De la primera ronda entendí que lo que les faltaba era una explicación: no es que los datos estuvieran mal, sino que cada gráfica tenía que decir de qué trata y qué quiere decir, con palabras sencillas. De la segunda entendí que, aunque ya se entendía mejor, la forma de escribir también importa: una frase correcta pero con las mismas palabras repetidas se vuelve pesada de leer.

## 3. Feedback recibido y cambios realizados
| # | Qué me dijeron | Qué hice (archivo y cambio) | Fecha |
|---|---|---|---|
| 1 | Primera ronda: la última gráfica no se entendía bien. | `dashboard/app_dashboard.py`: rehice la parte de abajo, que ahora es «4. Mira un departamento en particular». Antes de la gráfica puse una frase que explica qué hay que elegir y qué se va a ver, les puse nombres claros a los ejes y debajo agregué un resumen que compara el departamento con el promedio. | 2026-11-11 |
| 2 | Primera ronda: poner un resumen de lo que quiere decir cada gráfica, para las personas que no entienden. | `dashboard/app_dashboard.py`: debajo de cada gráfica agregué un resumen en palabras sencillas (por ejemplo, «por cada 100 estudiantes…»). También hice que al pasar el mouse por la gráfica salga el valor de cada punto. No puse cantidad de personas porque la fuente solo publica porcentajes. | 2026-11-11 |
| 3 | Primera ronda: mejorar la manera de poner los títulos para que las personas entiendan mejor las gráficas. | `dashboard/app_dashboard.py`: ordené el dashboard en secciones numeradas y con el título en forma de pregunta (1. Resumen, 2. ¿Cómo ha cambiado con los años?, 3. ¿Dónde hay más deserción?, 4. Mira un departamento en particular). También agregué el recuadro «¿Cómo leer este tablero?» y el menú «Elige qué quieres ver». | 2026-11-11 |
| 4 | Esto no me lo dijo nadie, lo vi yo: los años salían con coma («2,010») y la tarjeta de cobertura del cruce mostraba 0 % sin explicar por qué. | Los años ahora salen sin coma, y cambié la tarjeta de cobertura por una nota que explica hasta qué año hay datos de matrícula (2021). | 2026-11-11 |
| 5 | Segunda ronda: tienen seguro que son 32 departamentos y el dashboard decía 33 (la tarjeta decía «Departamentos con dato: 33 de 33»). | Revisé los datos y el 33 estaba bien: la fuente cuenta aparte a Bogotá D.C., o sea que son 32 departamentos más Bogotá. Lo que estaba mal era el nombre. En `dashboard/app_dashboard.py` la barra lateral ahora dice «32 departamentos y Bogotá D.C.», la tarjeta se llama «Lugares con dato» y en «¿Cómo leer este tablero?» explico por qué salen 33. También arreglé las mayúsculas de los nombres («Norte de Santander» y «Valle del Cauca», no «Norte De Santander») y ajusté el `README.md`. | 2026-11-11 |
| 6 | Segunda ronda: yo mismo quería que la parte de «¿Cómo leer este tablero?» estuviera mejor escrita. | `dashboard/app_dashboard.py`: reescribí el recuadro en siete puntos (tasa de deserción, nivel de formación, departamentos, promedio, puntos, que son solo porcentajes y cómo leer las gráficas). Quedó con frases más cortas, un ejemplo de qué es una tasa y una explicación de por qué el promedio no es la tasa de todo el país. | 2026-11-11 |
| 7 | Segunda ronda: en los resúmenes de abajo de las gráficas se repetían muchas palabras y había que usar mejores conectores. El ejemplo era: «En 2024, en el nivel Universitario, en promedio 9,3 de cada 100 estudiantes dejaron de estudiar. La tasa más alta fue la de Vichada (19,9 de cada 100) y la más baja la de Archipiélago De San Andrés, Providencia Y Santa Catalina (1,2 de cada 100).» Se repetían el «en» y el «de cada 100» en cada número, y debería sonar más como «En 2024, el nivel universitario, promediado…». | `dashboard/app_dashboard.py`: reescribí los cuatro resúmenes con conectores («mientras que», «es decir», «después vienen», «frente a»). Ahora lo de «por cada 100 estudiantes» se dice una sola vez y no en cada cifra, y el nivel va en minúscula dentro de la frase. Ese mismo ejemplo quedó así: «En 2024, el nivel universitario registró un promedio de 9,3 estudiantes por cada 100 que dejaron de estudiar. La tasa más alta fue la de Vichada, con 19,9, mientras que la más baja correspondió a Archipiélago de San Andrés, Providencia y Santa Catalina, con 1,2.» | 2026-11-11 |

## 4. Verificación del dashboard tras los ajustes
| # | Qué cambié | Cómo lo comprobé | Qué pasó | Evidencia (captura) |
|---|---|---|---|---|
| 1 | Los títulos en forma de pregunta, las secciones numeradas y el recuadro «¿Cómo leer este tablero?» (cambios 1 a 3 de la sección 3) | Les volví a mostrar el dashboard a mi mamá y a mi amigo | Dijeron que estaba mejor y que ya entendían más las gráficas | Capturas 21 y 24 de `docs/EVIDENCIAS.md` |
| 2 | El resumen en palabras bajo cada gráfica (cambio 2 de la sección 3) | Les volví a mostrar el dashboard a mi mamá y a mi amigo | Dijeron que estaba mejor, pero que se repetían muchas palabras; eso lo corregí en el cambio 7 | Capturas 22, 23 y 25 de `docs/EVIDENCIAS.md` |
| 3 | «32 departamentos y Bogotá D.C.», «Lugares con dato» y los resúmenes con conectores (cambios 5 a 7 de la sección 3) | Lo revisé yo en el dashboard en vivo con Universitario 2020 y Tecnológico 2024 (prueba M09) | Sale el texto nuevo y las cifras son las mismas que da la API | Capturas 21 a 25 de `docs/EVIDENCIAS.md` |

Las pruebas automáticas siguen en verde: 53 casos aprobados (`docs/capturas/27-pytest-53-passed.txt`). Las correcciones están en `docs/PRUEBAS.md` (*Registro de correcciones*).

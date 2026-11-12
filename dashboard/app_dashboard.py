# dashboard de streamlit, consume la api de api/main.py
# primero la api:      uvicorn api.main:app --reload
# luego el dashboard:  streamlit run dashboard/app_dashboard.py

import os

import pandas as pd
import requests
import streamlit as st


# direccion de la api, se puede cambiar con la variable API_URL
API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000").rstrip("/")

# nombre que sale en los ejes y al pasar el mouse por las graficas
TASA = "Estudiantes que dejaron de estudiar (de cada 100)"

# orden fijo de los niveles, los que no estén en gold se omiten
ORDEN_NIVELES = ["Universitario", "TyT", "Técnico Profesional", "Tecnológico"]


def coma(valor, decimales=1):
    # numero con coma decimal
    return f"{valor:.{decimales}f}".replace(".", ",")


def cambio_texto(inicio, fin):
    # frase corta para decir si subio o bajo, con los mismos decimales que se muestran
    diferencia = round(fin, 1) - round(inicio, 1)

    if abs(diferencia) < 0.05:
        return "casi no cambió"

    verbo = "subió" if diferencia > 0 else "bajó"
    return f"{verbo} {coma(abs(diferencia))} puntos"


def nombre(texto):
    # la fuente trae "Norte De Santander", aqui queda "Norte de Santander"
    for mal, bien in ((" De ", " de "), (" Del ", " del "), (" Y ", " y ")):
        texto = texto.replace(mal, bien)

    return texto


def nivel_en_frase(nivel):
    # dentro de una frase el nivel va en minuscula, menos TyT
    return nivel if nivel == "TyT" else nivel.lower()


def consultar(ruta):
    # get a la api, si falla avisa y detiene el dashboard
    try:
        respuesta = requests.get(f"{API_URL}{ruta}", timeout=30)
        respuesta.raise_for_status()
    except requests.RequestException as error:
        st.error(
            f"No se pudo consultar la API en {API_URL}{ruta}. "
            "¿Está encendida? (uvicorn api.main:app --reload)\n\n"
            f"Detalle: {error}"
        )
        st.stop()

    return respuesta.json()


@st.cache_data(ttl=60)
def cargar_gold():
    datos = pd.DataFrame(consultar("/gold/data")["Data"])
    datos["departamento"] = datos["departamento"].map(nombre)
    return datos


@st.cache_data(ttl=60)
def cargar_indicadores():
    return pd.DataFrame(consultar("/gold/indicadores")["Data"])


def main():
    st.set_page_config(page_title="Deserción en la educación superior", layout="wide")

    st.title("Deserción en la educación superior en Colombia")
    st.write(
        "¿Qué porcentaje de estudiantes deja de estudiar? Elige un nivel de "
        "formación y un año en el menú de la izquierda y mira cómo cambia."
    )

    with st.expander("¿Cómo leer este tablero?", expanded=True):
        st.markdown(
            "- **Tasa de deserción:** indica cuántos de cada 100 estudiantes dejaron de "
            "estudiar durante el año. Por ejemplo, un 9 % quiere decir que 9 de cada 100 "
            "abandonaron sus estudios.\n"
            "- **Nivel de formación:** es el tipo de programa, según el Ministerio de "
            "Educación. En el menú puedes elegir Universitario, Técnico Profesional, "
            "Tecnológico o TyT.\n"
            "- **Departamentos:** Colombia tiene 32, pero la fuente cuenta aparte a Bogotá D.C. "
            "(no la suma a Cundinamarca). Por eso el tablero muestra hasta 33 lugares y, cuando "
            "dice «departamentos», también incluye a Bogotá.\n"
            "- **Promedio:** es el promedio simple de las tasas de esos lugares. No es la tasa "
            "de todo el país, porque cada lugar pesa igual sin importar cuántos estudiantes tenga.\n"
            "- **Puntos:** miden la diferencia entre dos porcentajes. Pasar de 9 % a 11 % es "
            "subir 2 puntos.\n"
            "- **Solo porcentajes:** la fuente publica el porcentaje, no cuántas personas dejaron "
            "de estudiar. Por lo tanto, el tablero no muestra cantidades de personas.\n"
            "- **Gráficas:** pasa el mouse sobre una línea o una barra para ver su dato exacto."
        )

    estado = consultar("/health")

    if not estado.get("Archivo"):
        st.error("La API está encendida pero no encuentra gold_final.csv, corre primero el pipeline.")
        st.stop()

    gold = cargar_gold()
    indicadores = cargar_indicadores()

    niveles = [n for n in ORDEN_NIVELES if n in set(gold["nivel_formacion"])]
    anios = sorted(gold["anio"].unique())
    con_matricula = gold.dropna(subset=["matricula_reportada"])
    ultimo_anio_matricula = int(con_matricula["anio"].max())

    # Bogota se cuenta aparte de los departamentos
    total_lugares = gold["codigo_departamento"].nunique()
    hay_bogota = gold["departamento"].str.contains("Bogotá").any()
    total_departamentos = total_lugares - 1 if hay_bogota else total_lugares

    # filtros
    st.sidebar.header("Elige qué quieres ver")
    nivel = st.sidebar.selectbox("Nivel de formación", niveles)
    anio = st.sidebar.selectbox("Año", anios, index=max(len(anios) - 5, 0))

    st.sidebar.markdown("---")
    st.sidebar.write(
        f"Datos de {total_departamentos} departamentos y Bogotá D.C., "
        f"de {anios[0]} a {anios[-1]}."
    )

    # datos del nivel y año elegidos
    tabla = gold[(gold["nivel_formacion"] == nivel) & (gold["anio"] == anio)]
    con_tasa = tabla.dropna(subset=["tasa_desercion_porcentaje"])
    serie = indicadores[indicadores["nivel_formacion"] == nivel].sort_values("anio")
    fila = serie[serie["anio"] == anio]
    nivel_texto = nivel_en_frase(nivel)

    # 1. resumen
    st.header(f"1. Resumen: {nivel}, {anio}")

    if fila.empty or con_tasa.empty:
        st.warning("No hay datos de deserción para ese nivel y año.")
    else:
        fila = fila.iloc[0]
        mayor = con_tasa.loc[con_tasa["tasa_desercion_porcentaje"].idxmax()]
        menor = con_tasa.loc[con_tasa["tasa_desercion_porcentaje"].idxmin()]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Promedio de los departamentos", f"{coma(fila['tasa_media_simple_pct'])} %")
        c1.caption("Promedio simple, no es la tasa de todo el país")
        c2.metric("Tasa más alta", f"{coma(mayor['tasa_desercion_porcentaje'])} %")
        c2.caption(mayor["departamento"])
        c3.metric("Tasa más baja", f"{coma(menor['tasa_desercion_porcentaje'])} %")
        c3.caption(menor["departamento"])
        c4.metric(
            "Lugares con dato",
            f"{int(fila['departamentos_con_tasa'])} de {int(fila['departamentos_presentes'])}",
        )

        if int(fila["departamentos_presentes"]) == total_lugares:
            c4.caption(f"Entre los {total_departamentos} departamentos y Bogotá D.C.")
        else:
            c4.caption("Solo los que reportan este nivel")

        st.info(
            f"En {anio}, el nivel {nivel_texto} registró un promedio de "
            f"{coma(fila['tasa_media_simple_pct'])} estudiantes por cada 100 que dejaron de estudiar. "
            f"La tasa más alta fue la de {mayor['departamento']}, con "
            f"{coma(mayor['tasa_desercion_porcentaje'])}, mientras que la más baja correspondió a "
            f"{menor['departamento']}, con {coma(menor['tasa_desercion_porcentaje'])}."
        )

    # 2. evolucion por año
    st.header(f"2. ¿Cómo ha cambiado con los años? ({nivel})")
    st.write(
        "Cada punto de la línea es un año y muestra el promedio de los departamentos. "
        "Pasa el mouse sobre la línea para ver el dato exacto."
    )

    serie = serie.dropna(subset=["tasa_media_simple_pct"])

    if serie.empty:
        st.warning("No hay datos para este nivel.")
    else:
        evolucion = pd.DataFrame(
            {
                "Año": serie["anio"].astype(str).tolist(),
                TASA: serie["tasa_media_simple_pct"].round(1).tolist(),
            }
        )
        st.line_chart(evolucion, x="Año", y=TASA, x_label="Año", y_label=TASA)

        primero = serie.iloc[0]
        ultimo = serie.iloc[-1]
        alto = serie.loc[serie["tasa_media_simple_pct"].idxmax()]
        bajo = serie.loc[serie["tasa_media_simple_pct"].idxmin()]

        st.info(
            f"Entre {int(primero['anio'])} y {int(ultimo['anio'])}, el promedio del nivel "
            f"{nivel_texto} pasó de {coma(primero['tasa_media_simple_pct'])} a "
            f"{coma(ultimo['tasa_media_simple_pct'])} estudiantes por cada 100, es decir, "
            f"{cambio_texto(primero['tasa_media_simple_pct'], ultimo['tasa_media_simple_pct'])}. "
            f"El año más alto fue {int(alto['anio'])}, con {coma(alto['tasa_media_simple_pct'])}, "
            f"y el más bajo, {int(bajo['anio'])}, con {coma(bajo['tasa_media_simple_pct'])}."
        )

        if nivel == "Tecnológico":
            st.caption(
                "Desde 2019 el Ministerio excluye al SENA de los cálculos del nivel "
                "tecnológico, así que los años antes y después de 2019 no son del todo comparables."
            )

    # 3. ranking de departamentos
    st.header(f"3. ¿Dónde hay más deserción? ({nivel}, {anio})")
    st.write(
        "Los 10 lugares con más deserción ese año: cuanto más alta la barra, "
        "más estudiantes de cada 100 dejaron de estudiar."
    )

    if con_tasa.empty:
        st.warning("No hay departamentos con dato para ese nivel y año.")
    else:
        top = con_tasa.sort_values("tasa_desercion_porcentaje", ascending=False).head(10)
        barras = pd.DataFrame(
            {
                "Departamento": top["departamento"].tolist(),
                TASA: top["tasa_desercion_porcentaje"].round(1).tolist(),
            }
        )
        # de mayor a menor, si no streamlit ordena las barras por nombre
        st.bar_chart(barras, x="Departamento", y=TASA, x_label="Departamento", y_label=TASA, sort=f"-{TASA}")

        siguientes = [
            f"{fila_top['departamento']} ({coma(fila_top['tasa_desercion_porcentaje'])})"
            for _, fila_top in top.iloc[1:3].iterrows()
        ]

        texto = (
            f"En {anio}, {top.iloc[0]['departamento']} encabeza la lista del nivel "
            f"{nivel_texto}, con {coma(top.iloc[0]['tasa_desercion_porcentaje'])} estudiantes "
            "por cada 100 que dejaron de estudiar."
        )

        if len(siguientes) == 2:
            texto += f" Después vienen {siguientes[0]} y {siguientes[1]}."
        elif len(siguientes) == 1:
            texto += f" Después viene {siguientes[0]}."

        st.info(texto)

        detalle = pd.DataFrame(
            {
                "Posición": list(range(1, len(top) + 1)),
                "Departamento": top["departamento"].tolist(),
                TASA: top["tasa_desercion_porcentaje"].round(1).tolist(),
                "Cambio frente al año anterior (puntos)": top["variacion_desercion_pp"].round(1).tolist(),
            }
        )

        if top["matricula_reportada"].notna().any():
            detalle["Estudiantes matriculados (reportados)"] = top["matricula_reportada"].tolist()

        st.dataframe(detalle, hide_index=True)

        if not top["matricula_reportada"].notna().any():
            if anio > ultimo_anio_matricula:
                aviso = (
                    f"Los datos de matrícula llegan hasta {ultimo_anio_matricula}, "
                    f"por eso no se muestran para {anio}."
                )
            elif nivel == "TyT":
                aviso = "Para el nivel TyT la fuente de matrícula no tiene un dato equivalente, por eso no se muestra."
            else:
                aviso = "No hay datos de matrícula para estos departamentos en este año."

            st.caption(aviso)

    # 4. un departamento
    st.header("4. Mira un departamento en particular")
    st.write(
        "Elige un departamento (o Bogotá D.C.) para ver, año por año, cuántos de cada 100 "
        f"estudiantes dejaron de estudiar allí (nivel {nivel_texto})."
    )

    por_nivel = gold[gold["nivel_formacion"] == nivel].dropna(subset=["tasa_desercion_porcentaje"])
    nombres = sorted(por_nivel["departamento"].unique())

    if not nombres:
        st.warning("No hay departamentos con dato para este nivel.")
    else:
        elegido = st.selectbox(
            "Departamento",
            nombres,
            index=nombres.index("Antioquia") if "Antioquia" in nombres else 0,
        )
        historia = por_nivel[por_nivel["departamento"] == elegido].sort_values("anio")
        linea = pd.DataFrame(
            {
                "Año": historia["anio"].astype(str).tolist(),
                TASA: historia["tasa_desercion_porcentaje"].round(1).tolist(),
            }
        )
        st.line_chart(linea, x="Año", y=TASA, x_label="Año", y_label=TASA)

        inicio = historia.iloc[0]
        fin = historia.iloc[-1]
        maximo = historia.loc[historia["tasa_desercion_porcentaje"].idxmax()]

        if inicio["anio"] == fin["anio"]:
            texto = (
                f"En {elegido}, en {int(inicio['anio'])}, dejaron de estudiar "
                f"{coma(inicio['tasa_desercion_porcentaje'])} de cada 100 estudiantes."
            )
        else:
            texto = (
                f"En {elegido}, la deserción pasó de {coma(inicio['tasa_desercion_porcentaje'])} "
                f"por cada 100 estudiantes en {int(inicio['anio'])} a "
                f"{coma(fin['tasa_desercion_porcentaje'])} en {int(fin['anio'])}, es decir, "
                f"{cambio_texto(inicio['tasa_desercion_porcentaje'], fin['tasa_desercion_porcentaje'])}. "
                f"Su año más alto fue {int(maximo['anio'])}, con "
                f"{coma(maximo['tasa_desercion_porcentaje'])}."
            )

        # comparacion con el promedio del año elegido arriba
        del_anio = historia[historia["anio"] == anio]
        promedio = indicadores[(indicadores["nivel_formacion"] == nivel) & (indicadores["anio"] == anio)]

        if not del_anio.empty and not promedio.empty:
            valor = del_anio.iloc[0]["tasa_desercion_porcentaje"]
            media = promedio.iloc[0]["tasa_media_simple_pct"]

            if abs(valor - media) < 0.05:
                relacion = "casi igual al promedio de los departamentos"
            elif valor > media:
                relacion = "por encima del promedio de los departamentos"
            else:
                relacion = "por debajo del promedio de los departamentos"

            texto += f" En {anio}, {elegido} quedó {relacion}: {coma(valor)} frente a {coma(media)}."

        st.info(texto)

    st.divider()
    st.caption(
        "Fuente: Ministerio de Educación (SPADIES) para la deserción y datos.gov.co para la "
        "matrícula. El cruce entre las dos fuentes es técnico: no se certifica que midan "
        f"exactamente lo mismo. Datos servidos por la API en {API_URL}."
    )


main()

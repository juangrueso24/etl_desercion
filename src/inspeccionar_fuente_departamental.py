import json

import requests


RECURSO = "4hrb-y62g"

URL_METADATA = (
    f"https://www.datos.gov.co/api/views/{RECURSO}.json"
)

URL_DATOS = (
    f"https://www.datos.gov.co/resource/{RECURSO}.json"
)


def consultar(session, url, parametros=None):
    respuesta = session.get(
        url,
        params=parametros,
        timeout=90,
    )

    respuesta.raise_for_status()
    return respuesta.json()


def mostrar(titulo, contenido):
    print("\n" + "=" * 70)
    print(titulo)
    print("=" * 70)

    if isinstance(contenido, (dict, list)):
        print(
            json.dumps(
                contenido,
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(contenido)


def main():
    with requests.Session() as session:
        metadatos = consultar(
            session,
            URL_METADATA,
        )

        mostrar(
            "IDENTIFICACIÓN DE LA FUENTE",
            {
                "recurso": RECURSO,
                "nombre": metadatos.get("name"),
                "descripcion": metadatos.get("description"),
                "atribucion": metadatos.get("attribution"),
                "enlace_atribucion": metadatos.get(
                    "attributionLink"
                ),
            },
        )

        columnas = [
            {
                "campo": columna.get("fieldName"),
                "nombre": columna.get("name"),
                "tipo": columna.get("dataTypeName"),
                "descripcion": columna.get("description"),
            }
            for columna in metadatos.get("columns", [])
            if not columna.get("fieldName", "").startswith(":")
        ]

        mostrar("COLUMNAS", columnas)

        campos = {
            columna["campo"]
            for columna in columnas
        }

        necesarias = {
            "a_o",
            "c_digo_deldepartamento",
        }

        faltantes = necesarias - campos

        if faltantes:
            raise ValueError(
                "La estructura no coincide con la esperada. "
                f"Faltan campos: {sorted(faltantes)}"
            )

        total = consultar(
            session,
            URL_DATOS,
            {
                "$select": "count(*) AS total",
            },
        )

        mostrar("TOTAL DE REGISTROS", total)

        cobertura = consultar(
            session,
            URL_DATOS,
            {
                "$select": "a_o, count(*) AS registros",
                "$group": "a_o",
                "$order": "a_o",
                "$limit": 1000,
            },
        )

        mostrar("COBERTURA POR AÑO", cobertura)

        repetidas = consultar(
            session,
            URL_DATOS,
            {
                "$select": (
                    "a_o, c_digo_deldepartamento, "
                    "count(*) AS registros"
                ),
                "$group": (
                    "a_o, c_digo_deldepartamento"
                ),
                "$having": "count(*) > 1",
                "$order": "registros DESC",
                "$limit": 20,
            },
        )

        mostrar(
            "MUESTRA DE CLAVES AÑO + DEPARTAMENTO REPETIDAS",
            repetidas,
        )

        muestra = consultar(
            session,
            URL_DATOS,
            {
                "$order": "a_o, c_digo_deldepartamento",
                "$limit": 5,
            },
        )

        mostrar("CINCO REGISTROS COMPLETOS", muestra)

    print(
        "\nInspección terminada. "
        "No se modificaron archivos del proyecto."
    )


if __name__ == "__main__":
    main()
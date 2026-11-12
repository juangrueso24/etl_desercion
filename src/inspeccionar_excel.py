import pandas as pd

from src.config import RAW_DIR


RUTA_EXCEL = (
    RAW_DIR / "articles-415244_recurso_19.xlsx"
)


def main():
    if not RUTA_EXCEL.is_file():
        raise FileNotFoundError(
            f"Copia el Excel original en: {RUTA_EXCEL}"
        )

    with pd.ExcelFile(
        RUTA_EXCEL,
        engine="openpyxl",
    ) as libro:
        print("ARCHIVO:")
        print(RUTA_EXCEL.name)

        print("\nHOJAS DISPONIBLES:")

        for numero, nombre in enumerate(
            libro.sheet_names,
            start=1,
        ):
            print(f"{numero}. {nombre!r}")

        print("\nENCABEZADOS OBSERVADOS POR HOJA:")

        for nombre in libro.sheet_names:
            muestra = pd.read_excel(
                libro,
                sheet_name=nombre,
                header=None,
                nrows=15,
                dtype=object,
            ).fillna("")

            print("\n" + "=" * 70)
            print(f"HOJA: {nombre!r}")
            print("=" * 70)

            for indice, fila in muestra.iterrows():
                valores = [
                    str(valor).strip()
                    for valor in fila
                    if str(valor).strip()
                ]

                if valores:
                    print(
                        f"Fila {indice + 1}: "
                        + " | ".join(valores)
                    )

    print("\nInspección finalizada. El Excel no fue modificado.")


if __name__ == "__main__":
    main()
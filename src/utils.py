import unicodedata

import pandas as pd


def normalizar_texto(valor):
    if pd.isna(valor):
        return pd.NA

    texto = str(valor).strip()

    texto = unicodedata.normalize("NFKD", texto)

    texto = "".join(
        caracter
        for caracter in texto
        if not unicodedata.combining(caracter)
    )

    return " ".join(texto.upper().split())
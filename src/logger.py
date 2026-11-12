import logging

from src.config import LOG_DIR


def obtener_logger():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("etl_desercion")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        formato = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        )

        archivo = logging.FileHandler(
            LOG_DIR / "etl.log",
            encoding="utf-8",
        )
        archivo.setFormatter(formato)

        consola = logging.StreamHandler()
        consola.setFormatter(formato)

        logger.addHandler(archivo)
        logger.addHandler(consola)

    return logger


logger = obtener_logger()
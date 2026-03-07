"""
Sistema de logging centralizado.
Configura loggers por módulo con salida a consola y archivo.
"""

import logging
from pathlib import Path
from config.settings import LOGS_DIR


def get_logger(nombre: str) -> logging.Logger:
    """
    Crea y retorna un logger configurado para el módulo indicado.

    Args:
        nombre: Nombre del módulo (ej: "web_scraper", "email_sender")

    Returns:
        Logger configurado con handlers de consola y archivo.
    """
    logger = logging.getLogger(nombre)

    # Evitar duplicar handlers si ya fue configurado
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s | %(name)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Handler de consola (INFO y superior)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Handler de archivo (DEBUG y superior)
    log_file = LOGS_DIR / f"{nombre}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

"""
Configuración del registro de eventos (logging).

Sustituye los ``print()`` que quedaban dispersos por el código. Escribe a la
consola y a un archivo rotativo dentro de «logs/», de modo que un fallo en el
equipo de la librería deje rastro para diagnosticarlo después.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import RAIZ_PROYECTO, obtener_configuracion

FORMATO = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"
TAMANO_MAXIMO_BYTES = 1_000_000
ARCHIVOS_HISTORICOS = 3


def configurar_registro(directorio_logs: Path | None = None) -> None:
    """
    Deja el registro listo para toda la aplicación.

    Es idempotente: llamarla más de una vez no duplica los mensajes.

    Args:
        directorio_logs: Carpeta donde escribir «aplicacion.log». Si es None se
            usa «logs/» dentro del proyecto.
    """
    raiz = logging.getLogger()
    if getattr(raiz, "_configurado_por_app", False):
        return

    configuracion = obtener_configuracion()
    nivel = getattr(logging, configuracion.nivel_log, logging.INFO)
    raiz.setLevel(nivel)

    formato = logging.Formatter(FORMATO, datefmt=FORMATO_FECHA)

    consola = logging.StreamHandler()
    consola.setFormatter(formato)
    raiz.addHandler(consola)

    archivo = _crear_manejador_archivo(directorio_logs or RAIZ_PROYECTO / "logs", formato)
    if archivo is not None:
        raiz.addHandler(archivo)

    raiz._configurado_por_app = True  # type: ignore[attr-defined]


def _crear_manejador_archivo(
    directorio: Path, formato: logging.Formatter
) -> RotatingFileHandler | None:
    """
    Crea el manejador de archivo rotativo.

    Args:
        directorio: Carpeta destino de los archivos de registro.
        formato: Formateador a aplicar.

    Returns:
        El manejador, o None si la carpeta no se pudo crear (por ejemplo, por
        permisos). En ese caso la aplicación sigue funcionando solo con consola.
    """
    try:
        directorio.mkdir(parents=True, exist_ok=True)
        manejador = RotatingFileHandler(
            directorio / "aplicacion.log",
            maxBytes=TAMANO_MAXIMO_BYTES,
            backupCount=ARCHIVOS_HISTORICOS,
            encoding="utf-8",
        )
        manejador.setFormatter(formato)
        return manejador
    except OSError as error:
        logging.getLogger(__name__).warning(
            "No se pudo abrir el archivo de registro en %s: %s", directorio, error
        )
        return None

"""
Guardado y apertura de documentos con la aplicación del sistema.

Lo usa la factura para abrirse en el navegador, que es desde donde se imprime:
Flet 0.86.5 no ofrece impresión propia, ni control ni servicio que abra el
diálogo del sistema.

Está separado de quien compone el documento para que armar una factura se
pueda comprobar en las pruebas comparando texto, sin escribir en disco ni abrir
ventanas.
"""

from __future__ import annotations

import logging
import webbrowser
from pathlib import Path

from nucleo.errores import ErrorAplicacion

logger = logging.getLogger(__name__)


class ErrorDocumento(ErrorAplicacion):
    """No se pudo guardar o abrir un documento."""


def guardar(contenido: str, carpeta: Path, nombre: str) -> Path:
    """
    Escribe un documento de texto, creando la carpeta si hace falta.

    Args:
        contenido: Texto completo del documento.
        carpeta: Carpeta de destino.
        nombre: Nombre del archivo, sin carpeta.

    Returns:
        La ruta del archivo escrito.

    Raises:
        ErrorDocumento: Si no se pudo escribir, por permisos o falta de espacio.
    """
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
        ruta = carpeta / nombre
        ruta.write_text(contenido, encoding="utf-8")
    except OSError as error:
        raise ErrorDocumento(f"No se pudo guardar «{nombre}»: {error}") from error

    logger.info("Documento guardado: %s", ruta)
    return ruta


def abrir(ruta: Path) -> bool:
    """
    Abre un documento con la aplicación que el sistema tenga asociada.

    No propaga errores: que no se pueda abrir el visor no invalida el documento,
    que ya está guardado y el usuario puede abrir a mano. El motivo queda en el
    registro de eventos.

    Args:
        ruta: Archivo a abrir.

    Returns:
        True si se lanzó la apertura; False si no se pudo.
    """
    try:
        abierto = webbrowser.open(ruta.resolve().as_uri())
    except (OSError, ValueError) as error:
        logger.warning("No se pudo abrir «%s»: %s", ruta, error)
        return False

    if not abierto:
        logger.warning("El sistema no encontró con qué abrir «%s»", ruta)
    return abierto

"""
Avisos al usuario.

En Flet 0.86.5 la página **no** tiene el atributo ``snack_bar``: asignarlo no
da error, simplemente no muestra nada. La versión anterior del proyecto lo
hacía 26 veces, de modo que ningún mensaje de éxito ni de error llegaba nunca
a la pantalla, y los fallos pasaban inadvertidos.

La forma correcta en esta versión es ``page.show_dialog(...)``, y es la única
que se usa aquí.
"""

from __future__ import annotations

import logging

import flet as ft

from tema import AVISO, ERROR, EXITO, RADIO_BORDE, SUPERFICIE, TEXTO

logger = logging.getLogger(__name__)

DURACION_MS = 4000

MENSAJE_INESPERADO = (
    "Ocurrió un problema inesperado. El detalle quedó en el registro de eventos."
)


def avisar(pagina: ft.Page, mensaje: str, color: str = TEXTO) -> None:
    """
    Muestra un aviso flotante en la parte inferior de la pantalla.

    Args:
        pagina: Página sobre la que mostrarlo.
        mensaje: Texto a mostrar.
        color: Color de fondo del aviso; use las constantes de ``tema``.
    """
    pagina.show_dialog(
        ft.SnackBar(
            content=ft.Text(mensaje, color=SUPERFICIE, weight=ft.FontWeight.W_500),
            bgcolor=color,
            duration=DURACION_MS,
            behavior=ft.SnackBarBehavior.FLOATING,
            shape=ft.RoundedRectangleBorder(radius=RADIO_BORDE),
        )
    )


def avisar_exito(pagina: ft.Page, mensaje: str) -> None:
    """
    Confirma al usuario que una operación salió bien.

    Args:
        pagina: Página sobre la que mostrarlo.
        mensaje: Texto de la confirmación.
    """
    avisar(pagina, mensaje, EXITO)


def avisar_error(pagina: ft.Page, mensaje: str) -> None:
    """
    Informa al usuario de un problema y lo deja registrado.

    Args:
        pagina: Página sobre la que mostrarlo.
        mensaje: Texto del error.
    """
    logger.warning("Aviso de error al usuario: %s", mensaje)
    avisar(pagina, mensaje, ERROR)


def avisar_advertencia(pagina: ft.Page, mensaje: str) -> None:
    """
    Llama la atención sobre algo que conviene revisar, sin ser un fallo.

    Se usa, por ejemplo, para las alertas de stock mínimo (RF07).

    Args:
        pagina: Página sobre la que mostrarlo.
        mensaje: Texto de la advertencia.
    """
    avisar(pagina, mensaje, AVISO)


def avisar_fallo_inesperado(pagina: ft.Page, contexto: str, error: Exception) -> None:
    """
    Informa de un fallo imprevisto sin enseñarle sus tripas al usuario.

    El texto de una excepción de base de datos suele traer el servidor, el
    puerto, el nombre de la base y el usuario de conexión. Eso le sirve a quien
    mantiene el sistema, no a quien está cobrando, y en la pantalla de acceso
    se mostraría incluso antes de autenticar a nadie.

    Por eso el detalle y la traza van al registro de eventos, y al usuario le
    llega una frase que puede repetir por teléfono. Los errores de negocio
    —los :class:`~nucleo.errores.ErrorAplicacion`— sí se muestran tal cual,
    porque están escritos para que los lea él.

    Args:
        pagina: Página sobre la que mostrarlo.
        contexto: Qué se estaba intentando, para poder situarlo en el registro.
        error: Excepción capturada.
    """
    logger.exception("Fallo inesperado al %s", contexto, exc_info=error)
    avisar(pagina, MENSAJE_INESPERADO, ERROR)

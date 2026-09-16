"""
Punto de entrada de la aplicación.

Arranca el registro de eventos, configura la ventana y alterna entre la pantalla
de acceso y el panel principal. La reserva de conexiones se cierra al salir para
no dejar sesiones abiertas en la base de datos.
"""

from __future__ import annotations

import logging

import flet as ft

from config import obtener_configuracion
from modulos.personal.modelos import UsuarioAutenticado
from nucleo.base_datos import cerrar_motor
from nucleo.registro import configurar_registro
from tema import FONDO, obtener_tema
from vistas.dashboard import pantalla_dashboard
from vistas.login import pantalla_login

logger = logging.getLogger(__name__)

ANCHO_MINIMO = 1100
ALTO_MINIMO = 680
ANCHO_INICIAL = 1280
ALTO_INICIAL = 760


def principal(pagina: ft.Page) -> None:
    """
    Configura la ventana y arranca en la pantalla de acceso.

    Args:
        pagina: Página que Flet entrega al iniciar.
    """
    configuracion = obtener_configuracion()
    _configurar_ventana(pagina, configuracion.nombre_app)

    def mostrar_login() -> None:
        """Vuelve a la pantalla de acceso, descartando la sesión anterior."""
        pagina.controls.clear()
        pagina.controls.append(pantalla_login(pagina, mostrar_panel))
        pagina.update()

    def mostrar_panel(sesion: UsuarioAutenticado) -> None:
        """
        Abre el panel principal para la sesión recién iniciada.

        Args:
            sesion: Datos del usuario autenticado.
        """
        pagina.controls.clear()
        pagina.controls.append(pantalla_dashboard(pagina, sesion, mostrar_login))
        pagina.update()

    mostrar_login()


def _configurar_ventana(pagina: ft.Page, titulo: str) -> None:
    """
    Aplica el tema, el tamaño y el comportamiento de la ventana.

    Args:
        pagina: Página a configurar.
        titulo: Título de la ventana.
    """
    pagina.title = titulo
    pagina.theme = obtener_tema()
    pagina.theme_mode = ft.ThemeMode.LIGHT
    pagina.bgcolor = FONDO
    pagina.padding = 0
    pagina.spacing = 0

    pagina.window.width = ANCHO_INICIAL
    pagina.window.height = ALTO_INICIAL
    pagina.window.min_width = ANCHO_MINIMO
    pagina.window.min_height = ALTO_MINIMO
    pagina.window.resizable = True
    pagina.window.icon = "logo.png"

    pagina.on_error = _registrar_error_de_interfaz


def _registrar_error_de_interfaz(evento: ft.ControlEvent) -> None:
    """
    Deja constancia de un error surgido dentro de la interfaz.

    Args:
        evento: Evento de error que entrega Flet.
    """
    logger.error("Error en la interfaz: %s", evento.data)


def iniciar() -> None:
    """Arranca la aplicación y libera los recursos al cerrarla."""
    configurar_registro()
    logger.info("Iniciando %s", obtener_configuracion().nombre_app)
    try:
        ft.run(principal, assets_dir="assets")
    finally:
        cerrar_motor()
        logger.info("Aplicación finalizada")


if __name__ == "__main__":
    iniciar()

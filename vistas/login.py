"""
Pantalla de inicio de sesión (RF01).

La pantalla no decide nada sobre la seguridad del acceso: pide las
credenciales, se las pasa a :mod:`modulos.auth.servicios` y muestra lo que ese
le responda, incluido el aviso de bloqueo por demasiados intentos.

Antes llevaba su propio contador de fallos y su propio temporizador. Era una
regla de seguridad viviendo en la interfaz: reiniciar la aplicación la
reiniciaba, y cualquier otro llamador del servicio quedaba fuera de su alcance.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import flet as ft

from modulos.auth.servicios import ServicioAutenticacion
from modulos.personal.modelos import UsuarioAutenticado
from nucleo.errores import ErrorAplicacion, ErrorAutenticacion
from tema import (
    ACENTO,
    ERROR,
    ESPACIO,
    ESPACIO_GRANDE,
    FONDO,
    RADIO_TARJETA,
    SUPERFICIE,
    TEXTO,
    TEXTO_ATENUADO,
    TEXTO_SUBTITULO,
    estilo_boton,
)
from vistas.componentes.campos import campo_contrasena, campo_texto
from vistas.componentes.notificaciones import MENSAJE_INESPERADO

logger = logging.getLogger(__name__)

ANCHO_TARJETA = 420
ANCHO_CAMPO = 340


class PantallaLogin:
    """Formulario de acceso al sistema."""

    def __init__(self, pagina: ft.Page, al_entrar: Callable[[UsuarioAutenticado], None]) -> None:
        """
        Args:
            pagina: Página de Flet sobre la que se dibuja.
            al_entrar: Función a ejecutar con la sesión, tras un acceso correcto.
        """
        self._pagina = pagina
        self._al_entrar = al_entrar
        self._servicio = ServicioAutenticacion()

        self._usuario = campo_texto(
            "Usuario", icono=ft.Icons.PERSON, width=ANCHO_CAMPO, autofocus=True
        )
        self._contrasena = campo_contrasena("Contraseña", obligatorio=False)
        self._contrasena.width = ANCHO_CAMPO
        self._contrasena.on_submit = self._intentar

        self._mensaje = ft.Text("", size=13, color=ERROR, visible=False, text_align=ft.TextAlign.CENTER)
        self._boton = ft.Button(
            "Iniciar sesión",
            icon=ft.Icons.LOGIN,
            bgcolor=ACENTO,
            color=SUPERFICIE,
            width=ANCHO_CAMPO,
            height=46,
            style=estilo_boton(),
            on_click=self._intentar,
        )

    def construir(self) -> ft.Control:
        """
        Arma la pantalla de acceso.

        Returns:
            El control raíz de la pantalla.
        """
        tarjeta = ft.Card(
            elevation=12,
            content=ft.Container(
                width=ANCHO_TARJETA,
                padding=ESPACIO_GRANDE * 2,
                bgcolor=SUPERFICIE,
                border_radius=RADIO_TARJETA,
                content=ft.Column(
                    [
                        ft.Image(
                            src="logo.png", width=140, height=140, fit=ft.BoxFit.CONTAIN
                        ),
                        ft.Text(
                            "Librería Pablo Antonio Cuadra",
                            size=TEXTO_SUBTITULO,
                            weight=ft.FontWeight.BOLD,
                            color=TEXTO,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Text(
                            "Sistema de gestión y facturación",
                            size=13,
                            color=TEXTO_ATENUADO,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Container(height=ESPACIO),
                        self._usuario,
                        self._contrasena,
                        self._mensaje,
                        ft.Container(height=4),
                        self._boton,
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=ESPACIO,
                    tight=True,
                ),
            ),
        )

        return ft.Container(
            content=ft.Row([tarjeta], alignment=ft.MainAxisAlignment.CENTER),
            alignment=ft.Alignment(0, 0),
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1), colors=[ACENTO, FONDO]
            ),
        )

    def _intentar(self, _evento: ft.ControlEvent) -> None:
        """Valida las credenciales y entra al sistema si son correctas (RF01)."""
        try:
            sesion = self._servicio.iniciar_sesion(self._usuario.value, self._contrasena.value)
        except ErrorAutenticacion as error:
            self._contrasena.value = ""
            self._mostrar_mensaje(str(error))
            return
        except ErrorAplicacion as error:
            self._mostrar_mensaje(str(error))
            return
        except Exception:  # noqa: BLE001 - último recurso para no tumbar la interfaz
            logger.exception("Fallo inesperado al iniciar sesión")
            self._mostrar_mensaje(MENSAJE_INESPERADO)
            return

        self._al_entrar(sesion)

    def _mostrar_mensaje(self, texto: str) -> None:
        """
        Muestra un mensaje bajo los campos del formulario.

        Args:
            texto: Mensaje a mostrar.
        """
        self._mensaje.value = texto
        self._mensaje.visible = True
        self._pagina.update()


def pantalla_login(
    pagina: ft.Page, al_entrar: Callable[[UsuarioAutenticado], None]
) -> ft.Control:
    """
    Arma la pantalla de inicio de sesión.

    Args:
        pagina: Página de Flet sobre la que se dibuja.
        al_entrar: Función a ejecutar con la sesión, tras un acceso correcto.

    Returns:
        El control raíz de la pantalla.
    """
    return PantallaLogin(pagina, al_entrar).construir()

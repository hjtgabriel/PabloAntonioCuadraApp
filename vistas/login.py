"""
Pantalla de inicio de sesión (RF01).

Tras varios intentos fallidos el botón se bloquea durante unos segundos. Es una
traba sencilla contra el tanteo de contraseñas: no reemplaza al cifrado (RNF04),
pero encarece probar claves al azar en el equipo de la librería.
"""

from __future__ import annotations

import logging
import threading
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

logger = logging.getLogger(__name__)

INTENTOS_ANTES_DE_BLOQUEAR = 3
SEGUNDOS_BLOQUEO = 30
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
        self._intentos_fallidos = 0

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
            self._registrar_fallo(str(error))
            return
        except ErrorAplicacion as error:
            self._mostrar_mensaje(str(error))
            return
        except Exception as error:  # noqa: BLE001 - último recurso para no tumbar la interfaz
            logger.exception("Fallo inesperado al iniciar sesión")
            self._mostrar_mensaje(f"No se pudo conectar con la base de datos: {error}")
            return

        self._intentos_fallidos = 0
        self._al_entrar(sesion)

    def _registrar_fallo(self, mensaje: str) -> None:
        """
        Cuenta el intento fallido y bloquea el botón si son demasiados.

        Args:
            mensaje: Mensaje de error a mostrar.
        """
        self._intentos_fallidos += 1
        self._contrasena.value = ""

        restantes = INTENTOS_ANTES_DE_BLOQUEAR - self._intentos_fallidos
        if restantes > 0:
            self._mostrar_mensaje(f"{mensaje}. Intentos restantes: {restantes}")
            return

        self._bloquear()

    def _bloquear(self) -> None:
        """Desactiva el botón un rato para frenar el tanteo de contraseñas."""
        self._boton.disabled = True
        self._mostrar_mensaje(
            f"Demasiados intentos fallidos. Espere {SEGUNDOS_BLOQUEO} segundos."
        )
        logger.warning("Acceso bloqueado tras %d intentos fallidos", self._intentos_fallidos)

        temporizador = threading.Timer(SEGUNDOS_BLOQUEO, self._desbloquear)
        temporizador.daemon = True
        temporizador.start()

    def _desbloquear(self) -> None:
        """Vuelve a habilitar el botón y reinicia el contador de intentos."""
        self._intentos_fallidos = 0
        self._boton.disabled = False
        self._mensaje.visible = False
        self._pagina.update()

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

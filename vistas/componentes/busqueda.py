"""
Barra de búsqueda con espera (RF08).

Espera a que el usuario deje de escribir antes de consultar, para no lanzar una
consulta por cada tecla. El temporizador se cancela al destruirse el control, de
modo que no queden hilos vivos al cambiar de pantalla.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

import flet as ft

from tema import ACENTO, BORDE, SUPERFICIE, TEXTO_ATENUADO, TEXTO_NORMAL
from vistas.componentes.refresco import refrescar

ESPERA_MS = 300


class BarraBusqueda(ft.Row):
    """Campo de búsqueda con botón de limpieza y espera entre pulsaciones."""

    def __init__(
        self,
        al_buscar: Callable[[str], None],
        *,
        marcador: str = "Buscar…",
        espera_ms: int = ESPERA_MS,
        ancho: int = 320,
    ) -> None:
        """
        Args:
            al_buscar: Función que recibe el texto cuando el usuario deja de escribir.
            marcador: Texto de ayuda dentro del campo.
            espera_ms: Milisegundos a esperar antes de consultar.
            ancho: Ancho del campo en píxeles.
        """
        self._al_buscar = al_buscar
        self._espera_ms = espera_ms
        self._temporizador: threading.Timer | None = None

        self._campo = ft.TextField(
            label=marcador,
            prefix_icon=ft.Icons.SEARCH,
            border_color=BORDE,
            focused_border_color=ACENTO,
            bgcolor=SUPERFICIE,
            text_size=TEXTO_NORMAL,
            width=ancho,
            on_change=self._al_escribir,
        )
        self._boton_limpiar = ft.IconButton(
            icon=ft.Icons.CLEAR,
            icon_color=TEXTO_ATENUADO,
            tooltip="Limpiar búsqueda",
            visible=False,
            on_click=self._limpiar,
        )

        super().__init__(
            controls=[self._campo, self._boton_limpiar],
            spacing=4,
            alignment=ft.MainAxisAlignment.END,
            tight=True,
        )

    @property
    def texto(self) -> str:
        """Texto escrito actualmente en el campo."""
        return (self._campo.value or "").strip()

    def limpiar(self) -> None:
        """Vacía el campo sin disparar una búsqueda."""
        self._cancelar_temporizador()
        self._campo.value = ""
        self._boton_limpiar.visible = False
        refrescar(self)

    def _al_escribir(self, evento: ft.ControlEvent) -> None:
        """
        Reinicia la espera cada vez que el usuario pulsa una tecla.

        Args:
            evento: Evento de cambio del campo de texto.
        """
        texto = evento.control.value or ""
        self._boton_limpiar.visible = bool(texto.strip())
        self._boton_limpiar.update()

        self._cancelar_temporizador()
        self._temporizador = threading.Timer(
            self._espera_ms / 1000, self._lanzar_busqueda, args=[texto]
        )
        self._temporizador.daemon = True
        self._temporizador.start()

    def _lanzar_busqueda(self, texto: str) -> None:
        """
        Ejecuta la búsqueda tras la espera.

        Args:
            texto: Texto por el que buscar.
        """
        self._al_buscar(texto.strip())

    def _limpiar(self, _evento: ft.ControlEvent) -> None:
        """Vacía el campo y vuelve a listar todo."""
        self._cancelar_temporizador()
        self._campo.value = ""
        self._boton_limpiar.visible = False
        self._campo.update()
        self._boton_limpiar.update()
        self._al_buscar("")

    def _cancelar_temporizador(self) -> None:
        """Detiene la espera pendiente, si la hay."""
        if self._temporizador is not None:
            self._temporizador.cancel()
            self._temporizador = None

    def will_unmount(self) -> None:
        """Cancela la espera pendiente al quitar el control de la pantalla."""
        self._cancelar_temporizador()

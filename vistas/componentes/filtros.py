"""
Filtro de catálogo por marca y por categoría (RF08).

Lo comparten el catálogo de productos, el inventario y los dos historiales.
En las cuatro pantallas se acota por lo mismo —atributos del producto— así que
los desplegables, la opción «todas» y la lectura de los valores viven aquí una
sola vez, y no repetidos en cada vista.

El componente no consulta nada por su cuenta: avisa del cambio y quien lo usa
decide qué recargar. Así sirve igual para una tabla que para un historial.
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from modulos.catalogos.servicios import servicio_categorias, servicio_marcas
from modulos.productos.modelos import FiltroCatalogo

TODAS = ""
"""Valor del desplegable cuando no se acota por ese campo."""

ANCHO_DESPLEGABLE = 170


class BarraFiltros(ft.Row):
    """Par de desplegables que acotan una consulta por marca y por categoría."""

    def __init__(
        self,
        al_cambiar: Callable[[], None] | None = None,
        *,
        ancho: int = ANCHO_DESPLEGABLE,
    ) -> None:
        """
        Args:
            al_cambiar: Función a ejecutar cuando el usuario cambia un filtro.
                Puede conectarse después con :meth:`conectar`, que es lo que
                hace la pantalla CRUD porque aún no existe al construirse.
            ancho: Ancho de cada desplegable en píxeles.
        """
        self._al_cambiar = al_cambiar

        self._categoria = self._desplegable(
            "Categoría", _opciones_categoria(), ft.Icons.CATEGORY, ancho
        )
        self._marca = self._desplegable("Marca", _opciones_marca(), ft.Icons.LABEL, ancho)
        self._boton_limpiar = ft.IconButton(
            icon=ft.Icons.FILTER_ALT_OFF,
            tooltip="Quitar los filtros",
            visible=False,
            on_click=self._limpiar,
        )

        super().__init__(
            controls=[self._categoria, self._marca, self._boton_limpiar],
            spacing=8,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    # ── API pública ─────────────────────────────────────────────

    @property
    def filtro(self) -> FiltroCatalogo:
        """Criterios elegidos ahora mismo, listos para pasar al servicio."""
        return FiltroCatalogo(
            idcategoria=_clave(self._categoria.value),
            idmarca=_clave(self._marca.value),
        )

    @property
    def activo(self) -> bool:
        """Indica si hay algún filtro puesto."""
        return not self.filtro.vacio

    def conectar(self, al_cambiar: Callable[[], None]) -> None:
        """
        Fija a quién avisar cuando cambie un filtro.

        Args:
            al_cambiar: Función a ejecutar tras cada cambio.
        """
        self._al_cambiar = al_cambiar

    def limpiar(self) -> None:
        """Devuelve ambos desplegables a «todas», sin avisar del cambio."""
        self._categoria.value = TODAS
        self._marca.value = TODAS
        self._boton_limpiar.visible = False

    # ── Construcción y eventos ──────────────────────────────────

    def _desplegable(
        self, etiqueta: str, opciones: list[tuple[object, str]], icono: str, ancho: int
    ) -> ft.Dropdown:
        """
        Crea uno de los dos desplegables del filtro.

        Args:
            etiqueta: Rótulo visible.
            opciones: Pares (clave, texto) ya encabezados por «todas».
            icono: Icono a mostrar al inicio.
            ancho: Ancho del control en píxeles.

        Returns:
            El desplegable conectado al aviso de cambio.
        """
        return ft.Dropdown(
            label=etiqueta,
            value=TODAS,
            width=ancho,
            leading_icon=icono,
            options=[ft.DropdownOption(key=str(clave), text=texto) for clave, texto in opciones],
            on_select=self._al_seleccionar,
        )

    def _al_seleccionar(self, _evento: ft.ControlEvent) -> None:
        """
        Avisa del cambio y muestra el botón de quitar filtros si hace falta.

        Args:
            _evento: Evento del desplegable, que no se usa.
        """
        self._boton_limpiar.visible = self.activo
        self._avisar()

    def _limpiar(self, _evento: ft.ControlEvent) -> None:
        """
        Quita ambos filtros y recarga.

        Args:
            _evento: Evento del botón, que no se usa.
        """
        self.limpiar()
        self._avisar()

    def _avisar(self) -> None:
        """Ejecuta la recarga de quien usa el filtro, si hay alguien conectado."""
        if self._al_cambiar is not None:
            self._al_cambiar()


def _clave(valor: object) -> int | None:
    """
    Convierte el valor de un desplegable en la clave a filtrar.

    Args:
        valor: Valor seleccionado; los desplegables de Flet lo dan como texto.

    Returns:
        La clave como entero, o None si está en «todas» o no es un número.
    """
    if valor in (None, TODAS):
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _opciones_categoria() -> list[tuple[object, str]]:
    """
    Trae las categorías disponibles, encabezadas por «Todas».

    El rótulo del desplegable ya dice «Categoría», así que la opción no repite
    la palabra: con el texto largo el nombre no cabía y salía cortado.

    Returns:
        Pares (clave, nombre) para el desplegable.
    """
    opciones: list[tuple[object, str]] = [(TODAS, "Todas")]
    opciones.extend(
        (fila["idcategoria"], fila["nombre"]) for fila in servicio_categorias().listar()
    )
    return opciones


def _opciones_marca() -> list[tuple[object, str]]:
    """
    Trae las marcas disponibles, encabezadas por «Todas».

    Returns:
        Pares (clave, nombre) para el desplegable.
    """
    opciones: list[tuple[object, str]] = [(TODAS, "Todas")]
    opciones.extend(
        (fila["idmarca"], fila["nombremarca"]) for fila in servicio_marcas().listar()
    )
    return opciones

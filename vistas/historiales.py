"""
Pantallas de consulta histórica (RF05, RF06).

El historial de precios y el de movimientos de inventario son la misma pantalla
con distinta consulta y distintas columnas, así que comparten una función. En la
versión anterior eran dos archivos con un 75 % de líneas idénticas, y uno de
ellos ni siquiera llegaba a importarse por un error de nombre.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import flet as ft

from modulos.inventario.modelos import Movimiento
from modulos.inventario.servicios import ServicioInventario
from modulos.productos.modelos import CambioPrecio
from modulos.productos.servicios import ServicioProductos
from nucleo.errores import ErrorAplicacion
from tema import ACENTO, AVISO, ERROR, EXITO, TEXTO
from vistas.componentes.campos import campo_seleccion
from vistas.componentes.layout import pantalla
from vistas.componentes.notificaciones import avisar_error
from vistas.componentes.tablas import Columna, TablaDatos

TODOS = ""
MONEDA = "C$"

COLORES_MOVIMIENTO = {"Entrada": EXITO, "Salida": ERROR, "Venta": ERROR, "Ajuste": AVISO}


class PantallaHistorial:
    """Pantalla de consulta histórica con filtro por producto."""

    def __init__(
        self,
        pagina: ft.Page,
        *,
        titulo: str,
        columnas: list[Columna],
        cargar: Callable[[int | None], list[Any]],
        mensaje_vacio: str,
    ) -> None:
        """
        Args:
            pagina: Página de Flet sobre la que se dibuja.
            titulo: Encabezado de la pantalla.
            columnas: Columnas de la tabla.
            cargar: Función que devuelve las filas; recibe el producto elegido
                o None para traer el historial completo.
            mensaje_vacio: Qué mostrar cuando no hay registros.
        """
        self._pagina = pagina
        self._titulo = titulo
        self._cargar = cargar

        self._tabla = TablaDatos(columnas, mensaje_vacio=mensaje_vacio)
        self._filtro = campo_seleccion(
            "Filtrar por producto",
            self._opciones_producto(),
            valor=TODOS,
            al_seleccionar=lambda _evento: self._refrescar(),
        )

    def construir(self) -> ft.Control:
        """
        Arma la pantalla y carga el historial completo.

        Returns:
            El control raíz de la pantalla.
        """
        self._refrescar()
        return pantalla(
            self._titulo,
            self._tabla,
            self._filtro,
            ft.IconButton(
                icon=ft.Icons.REFRESH,
                icon_color=ACENTO,
                tooltip="Actualizar",
                on_click=lambda _evento: self._refrescar(),
            ),
        )

    def _refrescar(self) -> None:
        """Vuelve a consultar el historial respetando el filtro elegido."""
        try:
            self._tabla.cargar(self._cargar(self._producto_elegido()))
        except ErrorAplicacion as error:
            avisar_error(self._pagina, str(error))

    def _producto_elegido(self) -> int | None:
        """
        Lee el producto seleccionado en el filtro.

        Returns:
            La clave del producto, o None si está en «Todos».
        """
        valor = self._filtro.value
        return int(valor) if valor not in (None, TODOS) else None

    @staticmethod
    def _opciones_producto() -> list[tuple[object, str]]:
        """
        Arma las opciones del filtro con todos los productos del catálogo.

        Returns:
            Pares (clave, descripción), encabezados por la opción «Todos».
        """
        opciones: list[tuple[object, str]] = [(TODOS, "Todos los productos")]
        opciones.extend(
            (producto.idproducto, producto.descripcion)
            for producto in ServicioProductos().listar()
        )
        return opciones


def pantalla_historial_precios(pagina: ft.Page) -> ft.Control:
    """
    Arma la pantalla del historial de precios (RF06).

    Args:
        pagina: Página de Flet sobre la que se dibuja.

    Returns:
        El control raíz de la pantalla.
    """
    return PantallaHistorial(
        pagina,
        titulo="Historial de precios",
        columnas=[
            Columna("fechacambio", "Fecha", formato=_formato_fecha),
            Columna("descripcion", "Producto"),
            Columna("precioanterior", "Precio anterior", formato=_moneda, numerica=True),
            Columna("precionuevo", "Precio nuevo", formato=_moneda, numerica=True),
            Columna("variacion", "Variación", formato=_variacion, color=_color_variacion, numerica=True),
        ],
        cargar=lambda idproducto: ServicioProductos().listar_historial_precios(idproducto),
        mensaje_vacio="Todavía no se ha registrado ningún cambio de precio",
    ).construir()


def pantalla_historial_inventario(pagina: ft.Page) -> ft.Control:
    """
    Arma la pantalla del historial de movimientos de inventario (RF05).

    Args:
        pagina: Página de Flet sobre la que se dibuja.

    Returns:
        El control raíz de la pantalla.
    """
    return PantallaHistorial(
        pagina,
        titulo="Historial de inventario",
        columnas=[
            Columna("fechamovimiento", "Fecha", formato=_formato_fecha),
            Columna("descripcion", "Producto"),
            Columna("tipomovimiento", "Tipo", color=_color_movimiento),
            Columna("cantidad", "Cantidad", numerica=True),
        ],
        cargar=lambda idproducto: ServicioInventario().listar_historial(idproducto),
        mensaje_vacio="Todavía no se ha registrado ningún movimiento",
    ).construir()


# ── Formateadores ───────────────────────────────────────────────────────


def _formato_fecha(valor: object) -> str:
    """
    Da formato legible a una marca de tiempo.

    Args:
        valor: Fecha tal como llegó de la base de datos.

    Returns:
        La fecha en formato «AAAA-MM-DD HH:MM».
    """
    if valor is None:
        return "—"
    if hasattr(valor, "strftime"):
        return valor.strftime("%Y-%m-%d %H:%M")
    return str(valor)[:16]


def _moneda(valor: object) -> str:
    """
    Da formato de córdobas a un importe.

    Args:
        valor: Importe a formatear.

    Returns:
        El importe con símbolo y dos decimales.
    """
    return f"{MONEDA} {Decimal(str(valor or 0)):,.2f}"


def _variacion(valor: object) -> str:
    """
    Muestra una variación de precio con su flecha y su signo.

    Args:
        valor: Diferencia entre el precio nuevo y el anterior.

    Returns:
        La variación con flecha ascendente, descendente o guion.
    """
    diferencia = Decimal(str(valor or 0))
    if diferencia > 0:
        return f"▲ {MONEDA} {diferencia:,.2f}"
    if diferencia < 0:
        return f"▼ {MONEDA} {abs(diferencia):,.2f}"
    return "—"


def _color_variacion(cambio: CambioPrecio) -> str:
    """
    Elige el color de la variación de precio.

    Args:
        cambio: Registro histórico de la fila.

    Returns:
        Verde si el precio subió, rojo si bajó, neutro si no cambió.
    """
    if cambio.variacion > 0:
        return EXITO
    if cambio.variacion < 0:
        return ERROR
    return TEXTO


def _color_movimiento(movimiento: Movimiento) -> str:
    """
    Elige el color del tipo de movimiento.

    Args:
        movimiento: Movimiento de la fila.

    Returns:
        Color asociado al tipo de movimiento.
    """
    return COLORES_MOVIMIENTO.get(movimiento.tipomovimiento, TEXTO)

"""
Pantalla de movimientos de inventario (RF04, RF05, RF07).

La pantalla se divide en dos: a la izquierda el catálogo, a la derecha el panel
del producto elegido con su historial y el formulario de movimiento.

La selección de producto sí funciona: en la versión anterior la tabla recibía
la devolución de llamada pero nunca la conectaba a ningún control, así que el
panel derecho era inalcanzable.
"""

from __future__ import annotations

import flet as ft

from modulos.inventario.modelos import TipoMovimiento
from modulos.inventario.servicios import ServicioInventario
from modulos.productos.modelos import Producto
from modulos.productos.servicios import ServicioProductos
from nucleo.errores import ErrorAplicacion
from tema import (
    ACENTO,
    AVISO,
    BORDE,
    ERROR,
    ESPACIO,
    ESPACIO_GRANDE,
    EXITO,
    SUPERFICIE,
    TEXTO,
    TEXTO_SUBTITULO,
    color_estado_stock,
    estilo_boton,
)
from vistas.componentes.busqueda import BarraBusqueda
from vistas.componentes.campos import campo_entero, campo_seleccion
from vistas.componentes.filtros import BarraFiltros
from vistas.componentes.layout import encabezado, tarjeta
from vistas.componentes.notificaciones import avisar_error, avisar_exito
from vistas.componentes.tablas import Columna, TablaDatos

COLORES_MOVIMIENTO = {
    TipoMovimiento.ENTRADA.value: EXITO,
    TipoMovimiento.SALIDA.value: ERROR,
    TipoMovimiento.VENTA.value: ERROR,
    TipoMovimiento.AJUSTE.value: AVISO,
}

AYUDA_AJUSTE = "En un ajuste, la cantidad es el stock final que debe quedar"


class PantallaInventario:
    """Pantalla de consulta y registro de movimientos de stock."""

    def __init__(self, pagina: ft.Page) -> None:
        """
        Args:
            pagina: Página de Flet sobre la que se dibuja.
        """
        self._pagina = pagina
        self._productos = ServicioProductos()
        self._inventario = ServicioInventario()
        self._seleccionado: Producto | None = None

        self._tabla_productos = TablaDatos(
            [
                Columna("idproducto", "ID", numerica=True),
                Columna("descripcion", "Producto"),
                Columna("stock", "Stock", color=self._color_stock, numerica=True),
                Columna("stockminimo", "Mínimo", numerica=True),
            ],
            al_seleccionar=self._elegir_producto,
            mensaje_vacio="Aún no hay productos en el catálogo",
        )
        self._tabla_movimientos = TablaDatos(
            [
                Columna("fechamovimiento", "Fecha", formato=_formato_fecha),
                Columna("tipomovimiento", "Tipo", color=_color_movimiento),
                Columna("cantidad", "Cantidad", numerica=True),
            ],
            mensaje_vacio="Este producto aún no registra movimientos",
            filas_por_pagina=10,
        )

        self._busqueda = BarraBusqueda(self._buscar, marcador="Buscar producto…")
        self._filtros = BarraFiltros(self._recargar_catalogo)
        self._titulo_producto = ft.Text(size=TEXTO_SUBTITULO, weight=ft.FontWeight.BOLD, color=TEXTO)
        self._detalle_stock = ft.Text(size=14, color=TEXTO)
        self._tipo = campo_seleccion(
            "Tipo de movimiento",
            [(tipo.value, tipo.value) for tipo in TipoMovimiento if tipo is not TipoMovimiento.VENTA],
            obligatorio=True,
            valor=TipoMovimiento.ENTRADA.value,
        )
        self._cantidad = campo_entero("Cantidad", obligatorio=True, valor=1, minimo=0)
        self._panel = self._construir_panel()

    def construir(self) -> ft.Control:
        """
        Arma la pantalla y carga el catálogo.

        Returns:
            El control raíz de la pantalla.
        """
        self._buscar("")
        return ft.Column(
            [
                encabezado(
                    "Inventario · Movimientos de stock", self._filtros, self._busqueda
                ),
                ft.Row(
                    [
                        ft.Container(
                            content=self._tabla_productos,
                            expand=3,
                            padding=ESPACIO_GRANDE,
                            border=ft.Border(right=ft.BorderSide(1, BORDE)),
                        ),
                        ft.Container(content=self._panel, expand=4, padding=ESPACIO_GRANDE),
                    ],
                    expand=True,
                    spacing=0,
                ),
            ],
            expand=True,
            spacing=0,
        )

    # ── Panel derecho ───────────────────────────────────────────

    def _construir_panel(self) -> ft.Column:
        """
        Arma el panel del producto elegido.

        Returns:
            El panel, oculto hasta que se elija un producto.
        """
        formulario = ft.Column(
            [
                ft.Row([self._tipo, self._cantidad], spacing=ESPACIO),
                ft.Text(AYUDA_AJUSTE, size=12, color=TEXTO),
                ft.Button(
                    "Registrar movimiento",
                    icon=ft.Icons.SAVE,
                    bgcolor=ACENTO,
                    color=SUPERFICIE,
                    style=estilo_boton(),
                    on_click=self._registrar,
                ),
            ],
            spacing=ESPACIO,
            tight=True,
        )

        return ft.Column(
            [
                self._titulo_producto,
                self._detalle_stock,
                tarjeta("Registrar movimiento", formulario, ft.Icons.SWAP_HORIZ),
                tarjeta("Historial de movimientos", self._tabla_movimientos, ft.Icons.HISTORY),
            ],
            spacing=ESPACIO_GRANDE,
            expand=True,
            visible=False,
            scroll=ft.ScrollMode.AUTO,
        )

    # ── Acciones ────────────────────────────────────────────────

    def _recargar_catalogo(self) -> None:
        """Vuelve a cargar el catálogo respetando lo que haya escrito el usuario."""
        self._buscar(self._busqueda.texto)

    def _buscar(self, texto: str) -> None:
        """
        Carga el catálogo aplicando la búsqueda y los filtros (RF08).

        Args:
            texto: Término de búsqueda; vacío para listar todo.
        """
        try:
            self._tabla_productos.cargar(
                self._productos.listar(texto, filtro=self._filtros.filtro)
            )
        except ErrorAplicacion as error:
            avisar_error(self._pagina, str(error))

    def _elegir_producto(self, producto: Producto) -> None:
        """
        Muestra el panel del producto elegido y carga su historial.

        Args:
            producto: Producto seleccionado en la tabla.
        """
        self._seleccionado = producto
        self._titulo_producto.value = producto.descripcion
        self._detalle_stock.value = (
            f"Stock actual: {producto.stock}  ·  Stock mínimo: {producto.stockminimo}"
        )
        self._panel.visible = True
        self._cargar_movimientos()
        self._pagina.update()

    def _cargar_movimientos(self) -> None:
        """Refresca el historial del producto elegido (RF05)."""
        if self._seleccionado is None:
            return
        try:
            self._tabla_movimientos.cargar(
                self._inventario.listar_historial(self._seleccionado.idproducto)
            )
        except ErrorAplicacion as error:
            avisar_error(self._pagina, str(error))

    def _registrar(self, _evento: ft.ControlEvent) -> None:
        """Registra el movimiento y refresca catálogo e historial (RF04, RF05)."""
        if self._seleccionado is None:
            avisar_error(self._pagina, "Primero elija un producto del catálogo")
            return

        try:
            stock_final = self._inventario.registrar_movimiento(
                self._seleccionado.idproducto, self._tipo.value, self._cantidad.value
            )
        except ErrorAplicacion as error:
            avisar_error(self._pagina, str(error))
            return
        except Exception as error:  # noqa: BLE001 - último recurso para no tumbar la interfaz
            avisar_error(self._pagina, f"Ocurrió un problema inesperado: {error}")
            return

        avisar_exito(self._pagina, f"Movimiento registrado. Stock actual: {stock_final}")
        self._cantidad.value = "1"
        self._buscar(self._busqueda.texto)
        self._refrescar_seleccionado()

    def _refrescar_seleccionado(self) -> None:
        """Vuelve a leer el producto elegido para reflejar su stock nuevo."""
        if self._seleccionado is None:
            return
        try:
            self._elegir_producto(self._productos.obtener(self._seleccionado.idproducto))
        except ErrorAplicacion:
            self._seleccionado = None
            self._panel.visible = False
            self._pagina.update()

    @staticmethod
    def _color_stock(producto: Producto) -> str:
        """
        Elige el color de la celda de stock según el nivel de existencias (RF07).

        Args:
            producto: Producto de la fila.

        Returns:
            El color correspondiente.
        """
        return color_estado_stock(producto.stock, producto.stockminimo)


def pantalla_inventario(pagina: ft.Page) -> ft.Control:
    """
    Arma la pantalla de inventario.

    Args:
        pagina: Página de Flet sobre la que se dibuja.

    Returns:
        El control raíz de la pantalla.
    """
    return PantallaInventario(pagina).construir()


def _color_movimiento(movimiento: object) -> str:
    """
    Elige el color con que mostrar el tipo de un movimiento.

    Args:
        movimiento: Movimiento de la fila.

    Returns:
        Color asociado al tipo de movimiento.
    """
    tipo = getattr(movimiento, "tipomovimiento", "")
    return COLORES_MOVIMIENTO.get(tipo, TEXTO)


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

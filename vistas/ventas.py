"""
Punto de venta (RF04, RF08, RF09, RF10).

Pantalla dividida: a la izquierda la búsqueda de productos, a la derecha el
carrito con el total, el efectivo y el cambio.

Todos los importes se manejan con ``Decimal``, nunca con ``float``: el total y
el cambio deben cuadrar al centavo. La versión anterior calculaba en coma
flotante y podía desviarse en el vuelto.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

import flet as ft

from modulos.productos.modelos import Producto
from modulos.productos.servicios import ServicioProductos
from modulos.ventas.modelos import CENTAVO, ComprobanteVenta, LineaCarrito
from modulos.ventas.servicios import ServicioVentas
from nucleo.errores import ErrorAplicacion
from tema import (
    ACENTO,
    BORDE,
    ERROR,
    ESPACIO,
    ESPACIO_GRANDE,
    EXITO,
    SUPERFICIE,
    TEXTO,
    TEXTO_ATENUADO,
    TEXTO_SUBTITULO,
    TEXTO_TITULO,
    estilo_boton,
)
from vistas.componentes.busqueda import BarraBusqueda
from vistas.componentes.campos import campo_decimal
from vistas.componentes.dialogos import DialogoInformacion
from vistas.componentes.layout import encabezado, estado_vacio
from vistas.componentes.notificaciones import avisar_advertencia, avisar_error, avisar_exito
from vistas.componentes.refresco import refrescar

RESULTADOS_BUSQUEDA = 30
MONEDA = "C$"


class PuntoDeVenta:
    """Pantalla de cobro: arma el carrito y registra la venta."""

    def __init__(self, pagina: ft.Page, idusuario: int) -> None:
        """
        Args:
            pagina: Página de Flet sobre la que se dibuja.
            idusuario: Usuario que está cobrando; queda registrado en la venta.
        """
        self._pagina = pagina
        self._idusuario = idusuario
        self._productos = ServicioProductos()
        self._ventas = ServicioVentas()
        self._carrito: list[LineaCarrito] = []

        self._resultados = ft.ListView(expand=True, spacing=4)
        self._lineas = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, expand=True)
        self._busqueda = BarraBusqueda(self._buscar, marcador="Buscar producto…", ancho=420)

        self._total = ft.Text(size=TEXTO_TITULO, weight=ft.FontWeight.BOLD, color=TEXTO)
        self._cambio = ft.Text(size=TEXTO_SUBTITULO, color=EXITO)
        self._efectivo = campo_decimal("Efectivo recibido", valor="")
        self._efectivo.on_change = self._al_cambiar_efectivo

    def construir(self) -> ft.Control:
        """
        Arma la pantalla y carga los primeros productos.

        Returns:
            El control raíz de la pantalla.
        """
        self._buscar("")
        self._refrescar_carrito()

        return ft.Column(
            [
                encabezado("Punto de venta", self._busqueda),
                ft.Row(
                    [
                        ft.Container(
                            content=self._resultados,
                            expand=5,
                            padding=ESPACIO_GRANDE,
                            border=ft.Border(right=ft.BorderSide(1, BORDE)),
                        ),
                        ft.Container(content=self._construir_caja(), expand=4, padding=ESPACIO_GRANDE),
                    ],
                    expand=True,
                    spacing=0,
                ),
            ],
            expand=True,
            spacing=0,
        )

    # ── Lado izquierdo: catálogo ────────────────────────────────

    def _buscar(self, texto: str) -> None:
        """
        Busca productos y los muestra como lista pulsable (RF08).

        Args:
            texto: Término de búsqueda; vacío para mostrar los primeros.
        """
        try:
            encontrados = self._productos.listar(texto, limite=RESULTADOS_BUSQUEDA)
        except ErrorAplicacion as error:
            avisar_error(self._pagina, str(error))
            return

        self._resultados.controls = [self._fila_producto(p) for p in encontrados] or [
            estado_vacio(ft.Icons.SEARCH_OFF, "Sin resultados", "Pruebe con otro término.")
        ]
        refrescar(self._resultados)

    def _fila_producto(self, producto: Producto) -> ft.ListTile:
        """
        Arma la fila de un producto en los resultados de búsqueda.

        Args:
            producto: Producto a mostrar.

        Returns:
            La fila con su botón de agregar.
        """
        sin_stock = producto.stock <= 0
        return ft.ListTile(
            title=ft.Text(producto.descripcion, color=TEXTO),
            subtitle=ft.Text(
                f"Stock: {producto.stock}  ·  {MONEDA} {producto.precioventa:,.2f}",
                color=ERROR if sin_stock else TEXTO_ATENUADO,
                size=12,
            ),
            trailing=ft.Button(
                "Agregar",
                icon=ft.Icons.ADD_SHOPPING_CART,
                bgcolor=ACENTO,
                color=SUPERFICIE,
                style=estilo_boton(),
                disabled=sin_stock,
                on_click=lambda _evento, elegido=producto: self._agregar(elegido),
            ),
        )

    # ── Lado derecho: carrito y cobro ───────────────────────────

    def _construir_caja(self) -> ft.Column:
        """
        Arma el panel del carrito, los totales y el botón de cobro.

        Returns:
            El panel de caja.
        """
        return ft.Column(
            [
                ft.Text("Carrito", size=TEXTO_SUBTITULO, weight=ft.FontWeight.BOLD, color=TEXTO),
                ft.Container(content=self._lineas, expand=True),
                ft.Divider(height=1, color=BORDE),
                self._total,
                self._efectivo,
                self._cambio,
                ft.Button(
                    "Cobrar",
                    icon=ft.Icons.POINT_OF_SALE,
                    bgcolor=ACENTO,
                    color=SUPERFICIE,
                    height=48,
                    width=float("inf"),
                    style=estilo_boton(),
                    on_click=self._cobrar,
                ),
            ],
            spacing=ESPACIO,
            expand=True,
        )

    def _agregar(self, producto: Producto) -> None:
        """
        Agrega un producto al carrito o le suma una unidad.

        Args:
            producto: Producto elegido.
        """
        linea = self._buscar_linea(producto.idproducto)
        if linea is None:
            self._carrito.append(
                LineaCarrito(
                    idproducto=producto.idproducto,
                    descripcion=producto.descripcion,
                    precio=producto.precioventa,
                    cantidad=1,
                    stock_disponible=producto.stock,
                )
            )
        elif linea.cantidad >= linea.stock_disponible:
            avisar_advertencia(
                self._pagina, f"Solo hay {linea.stock_disponible} unidades de «{linea.descripcion}»"
            )
            return
        else:
            linea.cantidad += 1

        self._refrescar_carrito()

    def _cambiar_cantidad(self, linea: LineaCarrito, variacion: int) -> None:
        """
        Suma o resta una unidad a una línea del carrito.

        Args:
            linea: Línea a modificar.
            variacion: +1 o -1.
        """
        nueva = linea.cantidad + variacion
        if nueva <= 0:
            self._carrito.remove(linea)
        elif nueva > linea.stock_disponible:
            avisar_advertencia(
                self._pagina, f"Solo hay {linea.stock_disponible} unidades de «{linea.descripcion}»"
            )
            return
        else:
            linea.cantidad = nueva

        self._refrescar_carrito()

    def _quitar(self, linea: LineaCarrito) -> None:
        """
        Saca una línea del carrito.

        Args:
            linea: Línea a quitar.
        """
        self._carrito.remove(linea)
        self._refrescar_carrito()

    def _refrescar_carrito(self) -> None:
        """Redibuja las líneas del carrito y recalcula los totales."""
        if not self._carrito:
            self._lineas.controls = [
                estado_vacio(
                    ft.Icons.SHOPPING_CART,
                    "Carrito vacío",
                    "Busque un producto y pulse «Agregar».",
                )
            ]
        else:
            self._lineas.controls = [self._fila_carrito(linea) for linea in self._carrito]

        self._actualizar_totales()
        self._pagina.update()

    def _fila_carrito(self, linea: LineaCarrito) -> ft.Container:
        """
        Arma la fila de una línea del carrito.

        Args:
            linea: Línea a mostrar.

        Returns:
            La fila con sus controles de cantidad.
        """
        return ft.Container(
            content=ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text(linea.descripcion, color=TEXTO, weight=ft.FontWeight.W_500),
                            ft.Text(
                                f"{MONEDA} {linea.precio:,.2f} c/u",
                                size=12,
                                color=TEXTO_ATENUADO,
                            ),
                        ],
                        spacing=0,
                        tight=True,
                        expand=True,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.REMOVE,
                        icon_size=16,
                        icon_color=ACENTO,
                        tooltip="Quitar una unidad",
                        on_click=lambda _evento, item=linea: self._cambiar_cantidad(item, -1),
                    ),
                    ft.Text(str(linea.cantidad), color=TEXTO, weight=ft.FontWeight.BOLD),
                    ft.IconButton(
                        icon=ft.Icons.ADD,
                        icon_size=16,
                        icon_color=ACENTO,
                        tooltip="Agregar una unidad",
                        on_click=lambda _evento, item=linea: self._cambiar_cantidad(item, 1),
                    ),
                    ft.Text(
                        f"{MONEDA} {linea.subtotal:,.2f}",
                        color=TEXTO,
                        weight=ft.FontWeight.BOLD,
                        width=100,
                        text_align=ft.TextAlign.RIGHT,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE,
                        icon_size=16,
                        icon_color=ERROR,
                        tooltip="Quitar del carrito",
                        on_click=lambda _evento, item=linea: self._quitar(item),
                    ),
                ],
                spacing=4,
            ),
            padding=8,
            bgcolor=SUPERFICIE,
            border_radius=8,
        )

    def _actualizar_totales(self) -> None:
        """Recalcula el total a cobrar y el cambio a entregar (RF09)."""
        total = self._total_carrito()
        self._total.value = f"Total: {MONEDA} {total:,.2f}"

        efectivo = self._efectivo_escrito()
        if efectivo is None:
            self._cambio.value = "Escriba el efectivo recibido"
            self._cambio.color = TEXTO_ATENUADO
        elif efectivo < total:
            faltante = total - efectivo
            self._cambio.value = f"Faltan {MONEDA} {faltante:,.2f}"
            self._cambio.color = ERROR
        else:
            self._cambio.value = f"Cambio: {MONEDA} {efectivo - total:,.2f}"
            self._cambio.color = EXITO

    def _al_cambiar_efectivo(self, _evento: ft.ControlEvent) -> None:
        """Recalcula el cambio mientras el usuario escribe el efectivo."""
        self._actualizar_totales()
        self._total.update()
        self._cambio.update()

    def _cobrar(self, _evento: ft.ControlEvent) -> None:
        """Registra la venta y muestra el comprobante (RF04, RF09, RF10)."""
        if not self._carrito:
            avisar_error(self._pagina, "El carrito está vacío")
            return

        articulos = [
            {"idproducto": linea.idproducto, "cantidad": linea.cantidad}
            for linea in self._carrito
        ]
        try:
            comprobante = self._ventas.registrar(
                self._idusuario, articulos, self._efectivo.value or "0"
            )
        except ErrorAplicacion as error:
            avisar_error(self._pagina, str(error))
            return
        except Exception as error:  # noqa: BLE001 - último recurso para no tumbar la interfaz
            avisar_error(self._pagina, f"Ocurrió un problema inesperado: {error}")
            return

        avisar_exito(self._pagina, f"Venta {comprobante.idventa} registrada")
        self._pagina.show_dialog(_comprobante(self._pagina, comprobante))
        self._vaciar()

    def _vaciar(self) -> None:
        """Deja la pantalla lista para la siguiente venta."""
        self._carrito.clear()
        self._efectivo.value = ""
        self._refrescar_carrito()
        self._buscar(self._busqueda.texto)

    # ── Apoyo interno ───────────────────────────────────────────

    def _buscar_linea(self, idproducto: int) -> LineaCarrito | None:
        """
        Busca una línea del carrito por producto.

        Args:
            idproducto: Producto a buscar.

        Returns:
            La línea, o None si el producto aún no está en el carrito.
        """
        return next((linea for linea in self._carrito if linea.idproducto == idproducto), None)

    def _total_carrito(self) -> Decimal:
        """
        Suma el importe de todas las líneas del carrito.

        Returns:
            El total con dos decimales.
        """
        return sum((linea.subtotal for linea in self._carrito), Decimal("0")).quantize(CENTAVO)

    def _efectivo_escrito(self) -> Decimal | None:
        """
        Lee el efectivo escrito en el campo.

        Returns:
            El importe, o None si el campo está vacío o no es un número.
        """
        texto = (self._efectivo.value or "").strip()
        if not texto:
            return None
        try:
            return Decimal(texto).quantize(CENTAVO)
        except InvalidOperation:
            return None


def pantalla_ventas(pagina: ft.Page, idusuario: int) -> ft.Control:
    """
    Arma la pantalla del punto de venta.

    Args:
        pagina: Página de Flet sobre la que se dibuja.
        idusuario: Usuario que está cobrando.

    Returns:
        El control raíz de la pantalla.
    """
    return PuntoDeVenta(pagina, idusuario).construir()


def _comprobante(pagina: ft.Page, venta: ComprobanteVenta) -> ft.AlertDialog:
    """
    Arma el diálogo con el comprobante de la venta.

    Args:
        pagina: Página sobre la que se muestra el comprobante.
        venta: Datos de la venta recién registrada.

    Returns:
        El diálogo listo para mostrar.
    """
    filas = [
        ("Venta N.º", str(venta.idventa)),
        ("Total", f"{MONEDA} {venta.total:,.2f}"),
        ("Efectivo recibido", f"{MONEDA} {venta.efectivo:,.2f}"),
        ("Cambio a entregar", f"{MONEDA} {venta.cambio:,.2f}"),
    ]
    contenido = ft.Column(
        [
            ft.Row(
                [
                    ft.Text(etiqueta, color=TEXTO),
                    ft.Container(expand=True),
                    ft.Text(
                        valor,
                        color=EXITO if etiqueta.startswith("Cambio") else TEXTO,
                        weight=ft.FontWeight.BOLD,
                    ),
                ]
            )
            for etiqueta, valor in filas
        ],
        tight=True,
        spacing=ESPACIO,
        width=320,
    )
    return DialogoInformacion(pagina, "Venta registrada", contenido)

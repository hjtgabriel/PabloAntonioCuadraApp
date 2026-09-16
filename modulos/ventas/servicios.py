"""
Reglas de negocio del punto de venta (RF04, RF09, RF10, RF11).

Registrar una venta implica cuatro escrituras que deben ser indivisibles: la
cabecera, cada línea de detalle, el descuento de stock y el asiento de
inventario. Todas comparten una sola conexión y una sola transacción, así que
una caída a mitad de camino no deja stock descontado sin venta ni venta sin
stock descontado.

El total se calcula siempre con el precio que la base de datos tiene en ese
instante, no con el que la pantalla mostraba: así el importe no depende de que
el vendedor tuviera la lista actualizada.
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from modulos.inventario.modelos import TipoMovimiento
from modulos.inventario.servicios import ServicioInventario
from modulos.productos.repositorio import ProductoRepositorio
from modulos.ventas.modelos import CENTAVO, ComprobanteVenta, Venta
from modulos.ventas.repositorio import VentaRepositorio
from nucleo.base_datos import Conexion, transaccion
from nucleo.errores import (
    ErrorNoEncontrado,
    ErrorStockInsuficiente,
    ErrorValidacion,
)

logger = logging.getLogger(__name__)

VENTAS_RECIENTES = 10


class ServicioVentas:
    """Registro y consulta de ventas."""

    def __init__(self, conexion: Conexion | None = None) -> None:
        """
        Args:
            conexion: Conexión de una transacción en curso, si la hay.
        """
        self._conexion = conexion
        self._repositorio = VentaRepositorio(conexion)

    def registrar(
        self, idusuario: int, articulos: list[dict], efectivo_recibido: object
    ) -> ComprobanteVenta:
        """
        Registra una venta completa (RF04, RF09, RF10).

        Args:
            idusuario: Usuario que cobra.
            articulos: Lista de diccionarios con «idproducto» y «cantidad».
            efectivo_recibido: Efectivo entregado por el cliente.

        Returns:
            Comprobante con el total cobrado y el cambio a entregar.

        Raises:
            ErrorValidacion: Si el carrito está vacío, una cantidad es inválida
                o el efectivo no alcanza.
            ErrorNoEncontrado: Si algún producto del carrito ya no existe.
            ErrorStockInsuficiente: Si no hay existencias para alguna línea.
        """
        lineas = _validar_articulos(articulos)
        efectivo = _a_importe(efectivo_recibido, "El efectivo recibido")

        with transaccion(self._conexion) as conexion:
            productos = ProductoRepositorio(conexion)
            total = self._calcular_total(productos, lineas)

            if efectivo < total:
                raise ErrorValidacion(
                    f"El efectivo recibido (C$ {efectivo:.2f}) es menor que el "
                    f"total de la venta (C$ {total:.2f})"
                )
            cambio = (efectivo - total).quantize(CENTAVO)

            ventas = VentaRepositorio(conexion)
            inventario = ServicioInventario(conexion)
            idventa = ventas.registrar_cabecera(idusuario, total, efectivo, cambio)

            for idproducto, cantidad in lineas.items():
                ventas.registrar_detalle(idventa, idproducto, cantidad)
                inventario.registrar_movimiento(idproducto, TipoMovimiento.VENTA, cantidad)

            logger.info(
                "Venta %d registrada por el usuario %d: total C$ %s, cambio C$ %s",
                idventa, idusuario, total, cambio,
            )
            return ComprobanteVenta(
                idventa=idventa,
                total=total,
                efectivo=efectivo,
                cambio=cambio,
                lineas=len(lineas),
            )

    def listar_recientes(self, limite: int = VENTAS_RECIENTES) -> list[Venta]:
        """
        Devuelve las últimas ventas registradas.

        Args:
            limite: Cantidad máxima de ventas a traer.

        Returns:
            Ventas de la más reciente a la más antigua.
        """
        return self._repositorio.listar_recientes(limite)

    def obtener_detalle(self, idventa: int) -> Venta:
        """
        Recupera una venta con todas sus líneas.

        Args:
            idventa: Clave de la venta.

        Returns:
            La venta con sus detalles.

        Raises:
            ErrorNoEncontrado: Si la venta no existe.
        """
        venta = self._repositorio.obtener_con_detalle(idventa)
        if venta is None:
            raise ErrorNoEncontrado("No se encontró la venta solicitada")
        return venta

    def anular(self, idventa: int) -> bool:
        """
        Anula una venta y devuelve las unidades al stock.

        La devolución se anota como movimiento de entrada, de modo que el
        historial de inventario explique de dónde salió el stock (RF05).

        Args:
            idventa: Clave de la venta a anular.

        Returns:
            True si se anuló.

        Raises:
            ErrorNoEncontrado: Si la venta no existe.
        """
        with transaccion(self._conexion) as conexion:
            ventas = VentaRepositorio(conexion)
            venta = ventas.obtener_con_detalle(idventa)
            if venta is None:
                raise ErrorNoEncontrado("No se encontró la venta solicitada")

            inventario = ServicioInventario(conexion)
            for detalle in venta.detalles:
                inventario.registrar_movimiento(
                    detalle.idproducto, TipoMovimiento.ENTRADA, detalle.cantidad
                )

            ventas.eliminar_detalles(idventa)
            anulada = ventas.eliminar(idventa)
            logger.info("Venta %d anulada; stock devuelto", idventa)
            return anulada

    @staticmethod
    def _calcular_total(productos: ProductoRepositorio, lineas: dict[int, int]) -> Decimal:
        """
        Suma el importe de la venta leyendo precio y stock de la base de datos (RF09).

        Args:
            productos: Repositorio atado a la transacción en curso.
            lineas: Producto → cantidad.

        Returns:
            Importe total con dos decimales.

        Raises:
            ErrorNoEncontrado: Si algún producto ya no existe.
            ErrorStockInsuficiente: Si no hay existencias para alguna línea.
        """
        total = Decimal("0")
        for idproducto, cantidad in lineas.items():
            datos = productos.obtener_precio_y_stock(idproducto)
            if datos is None:
                raise ErrorNoEncontrado(f"El producto {idproducto} ya no existe en el catálogo")
            if datos["stock"] < cantidad:
                raise ErrorStockInsuficiente(
                    f"Solo quedan {datos['stock']} unidades de «{datos['descripcion']}»"
                )
            total += datos["precioventa"] * cantidad
        return total.quantize(CENTAVO)


def _validar_articulos(articulos: list[dict]) -> dict[int, int]:
    """
    Normaliza el carrito y agrupa las cantidades por producto.

    Si el mismo producto viene en dos líneas, las suma en una sola.

    Args:
        articulos: Lista de diccionarios con «idproducto» y «cantidad».

    Returns:
        Diccionario producto → cantidad total.

    Raises:
        ErrorValidacion: Si el carrito está vacío o alguna cantidad es inválida.
    """
    if not articulos:
        raise ErrorValidacion("El carrito está vacío: agregue al menos un producto")

    lineas: dict[int, int] = {}
    for articulo in articulos:
        try:
            idproducto = int(articulo["idproducto"])
            cantidad = int(articulo["cantidad"])
        except (KeyError, TypeError, ValueError) as error:
            raise ErrorValidacion("Hay una línea del carrito con datos inválidos") from error

        if cantidad <= 0:
            raise ErrorValidacion("Las cantidades del carrito deben ser mayores que cero")
        lineas[idproducto] = lineas.get(idproducto, 0) + cantidad

    return lineas


def _a_importe(valor: object, etiqueta: str) -> Decimal:
    """
    Convierte a importe monetario un valor escrito en la interfaz.

    Args:
        valor: Valor recibido, normalmente como texto.
        etiqueta: Nombre del campo para el mensaje de error.

    Returns:
        El importe como ``Decimal`` con dos decimales.

    Raises:
        ErrorValidacion: Si no es un número o es negativo.
    """
    try:
        importe = Decimal(str(valor).strip() or "0")
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ErrorValidacion(f"{etiqueta} debe ser un número válido") from error
    if importe < 0:
        raise ErrorValidacion(f"{etiqueta} no puede ser negativo")
    return importe.quantize(CENTAVO)

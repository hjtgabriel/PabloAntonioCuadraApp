"""Entidades del módulo de ventas."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

CENTAVO = Decimal("0.01")


@dataclass(slots=True)
class LineaCarrito:
    """
    Producto agregado al carrito antes de cobrar.

    Vive solo en memoria mientras el vendedor arma la venta.

    Attributes:
        idproducto: Producto elegido.
        descripcion: Nombre del producto, para mostrarlo en pantalla.
        precio: Precio unitario vigente al momento de agregarlo.
        cantidad: Unidades a vender.
        stock_disponible: Existencias al momento de agregarlo, para no permitir
            que la interfaz exceda lo que hay.
    """

    idproducto: int
    descripcion: str
    precio: Decimal
    cantidad: int
    stock_disponible: int

    @property
    def subtotal(self) -> Decimal:
        """Importe de la línea: precio unitario por cantidad."""
        return (self.precio * self.cantidad).quantize(CENTAVO)


@dataclass(slots=True)
class DetalleVenta:
    """
    Línea ya registrada de una venta.

    Attributes:
        iddetalleventa: Clave primaria de la línea.
        idventa: Venta a la que pertenece.
        idproducto: Producto vendido.
        cantidad: Unidades vendidas.
        descripcion: Nombre del producto, solo lectura desde un JOIN.
        precioventa: Precio unitario, solo lectura desde un JOIN.
        subtotal: Importe de la línea, calculado por la consulta.
    """

    iddetalleventa: int
    idventa: int
    idproducto: int
    cantidad: int
    descripcion: str | None = None
    precioventa: Decimal | None = None
    subtotal: Decimal | None = None


@dataclass(slots=True)
class Venta:
    """
    Venta registrada (RF09, RF10, RF11).

    El sistema no pide datos del cliente ni aplica descuentos (RF10): basta con
    el total, el efectivo recibido y el cambio entregado.

    Attributes:
        idventa: Clave primaria de la venta.
        idusuario: Usuario que la registró.
        fechaventa: Momento de la venta.
        totalventa: Importe total cobrado.
        efectivorecibido: Efectivo que entregó el cliente.
        cambioentregado: Vuelto devuelto.
        nombreusuario: Identificador del vendedor, solo lectura desde un JOIN.
        detalles: Líneas de la venta, si se solicitaron.
    """

    idventa: int
    idusuario: int
    fechaventa: datetime
    totalventa: Decimal
    efectivorecibido: Decimal
    cambioentregado: Decimal
    nombreusuario: str | None = None
    detalles: list[DetalleVenta] = field(default_factory=list)


@dataclass(slots=True)
class ComprobanteVenta:
    """
    Resultado que se muestra al vendedor tras cobrar.

    Attributes:
        idventa: Clave de la venta registrada.
        total: Importe total cobrado (RF09).
        efectivo: Efectivo recibido.
        cambio: Cambio entregado.
        lineas: Cantidad de productos distintos vendidos.
    """

    idventa: int
    total: Decimal
    efectivo: Decimal
    cambio: Decimal
    lineas: int

"""Entidades del módulo de productos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

STOCK_MINIMO_POR_OMISION = 5


@dataclass(slots=True)
class Producto:
    """
    Artículo del catálogo de la librería (RF03).

    Los precios se guardan como ``Decimal`` y nunca como ``float``: el dinero
    no admite el redondeo binario, y el total de una venta debe cuadrar al
    centavo (RF09, RF11).

    Attributes:
        idproducto: Clave primaria; vale 0 mientras no se haya guardado.
        descripcion: Nombre del artículo.
        idcategoria: Categoría a la que pertenece; obligatoria (RF03).
        idmarca: Marca del artículo; obligatoria (RF03).
        idproveedor: Proveedor que lo surte.
        preciocompra: Costo de adquisición.
        precioventa: Precio al público; obligatorio (RF03).
        stock: Existencias actuales.
        stockminimo: Umbral que dispara la alerta de reabastecimiento (RF07).
        categoria: Nombre de la categoría, solo lectura desde un JOIN.
        marca: Nombre de la marca, solo lectura desde un JOIN.
        proveedor: Nombre del proveedor, solo lectura desde un JOIN.
    """

    idproducto: int
    descripcion: str
    idcategoria: int
    idmarca: int
    idproveedor: int
    preciocompra: Decimal
    precioventa: Decimal
    stock: int
    stockminimo: int = STOCK_MINIMO_POR_OMISION
    categoria: str | None = None
    marca: str | None = None
    proveedor: str | None = None

    @property
    def bajo_minimo(self) -> bool:
        """Indica si el stock llegó o cayó por debajo del mínimo (RF07)."""
        return self.stock <= self.stockminimo


@dataclass(slots=True)
class CambioPrecio:
    """
    Registro histórico de una variación de precio (RF06).

    Attributes:
        idhistorial: Clave primaria del registro.
        idproducto: Producto cuyo precio cambió.
        fechacambio: Momento en que se aplicó el cambio.
        precioanterior: Precio que tenía antes.
        precionuevo: Precio que quedó vigente.
        descripcion: Nombre del producto, solo lectura desde un JOIN.
    """

    idhistorial: int
    idproducto: int
    fechacambio: datetime
    precioanterior: Decimal
    precionuevo: Decimal
    descripcion: str | None = None

    @property
    def variacion(self) -> Decimal:
        """Diferencia entre el precio nuevo y el anterior."""
        return self.precionuevo - self.precioanterior

"""
Pantalla del catálogo de productos (RF03, RF07, RF08).

Usa la pantalla CRUD genérica y solo añade lo propio del dominio: los tres
desplegables de relaciones y el resaltado por color del nivel de existencias.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import flet as ft

from modulos.catalogos.servicios import servicio_categorias, servicio_marcas
from modulos.productos.modelos import Producto
from modulos.productos.servicios import ServicioProductos
from modulos.proveedores.servicios import ServicioProveedores
from tema import color_estado_stock
from vistas.componentes.campos import (
    campo_decimal,
    campo_entero,
    campo_seleccion,
    longitud_minima,
)
from vistas.componentes.dialogos import Campo, definir_campo
from vistas.componentes.filtros import BarraFiltros
from vistas.componentes.registros import lector
from vistas.componentes.tablas import Columna
from vistas.crud import ConfiguracionCrud, construir_pantalla_crud

LONGITUD_MINIMA_DESCRIPCION = 2
STOCK_MINIMO_PREDETERMINADO = 5
STOCK_INICIAL_PREDETERMINADO = 0


def _construir_campos(producto: Producto | None) -> list[Campo]:
    """
    Arma el formulario de producto, precargado si se está editando.

    Args:
        producto: Producto a editar, o None si es un alta.

    Returns:
        Los campos del formulario, en orden de aparición.
    """
    valor = lector(producto)
    return [
        definir_campo(
            "descripcion",
            "Descripción",
            obligatorio=True,
            valor=valor("descripcion"),
            icono=ft.Icons.DESCRIPTION,
            validador=longitud_minima(LONGITUD_MINIMA_DESCRIPCION, "La descripción"),
        ),
        *_campos_de_relacion(valor),
        definir_campo(
            "preciocompra",
            "Precio de compra",
            campo_decimal,
            obligatorio=True,
            valor=valor("preciocompra", "0.00"),
        ),
        definir_campo(
            "precioventa",
            "Precio de venta",
            campo_decimal,
            obligatorio=True,
            valor=valor("precioventa", "0.00"),
            minimo=Decimal("0.01"),
        ),
        definir_campo(
            "stockminimo",
            "Stock mínimo",
            campo_entero,
            obligatorio=True,
            valor=valor("stockminimo", STOCK_MINIMO_PREDETERMINADO),
            icono=ft.Icons.WARNING_AMBER,
        ),
        *_campo_stock_inicial(producto),
    ]


def _campos_de_relacion(valor: Callable[..., object]) -> list[Campo]:
    """
    Arma los tres desplegables que enlazan el producto con sus catálogos.

    Los tres se declaran igual, así que se generan a partir de una tabla en
    lugar de repetir la misma llamada tres veces.

    Args:
        valor: Lector del producto que se está editando.

    Returns:
        Los desplegables de categoría, marca y proveedor.
    """
    return [
        definir_campo(
            clave,
            etiqueta,
            campo_seleccion,
            obligatorio=True,
            opciones=cargar_opciones(),
            valor=valor(clave, None),
        )
        for clave, etiqueta, cargar_opciones in RELACIONES_DEL_PRODUCTO
    ]


def pantalla_productos(pagina: ft.Page) -> ft.Control:
    """
    Arma la pantalla del catálogo de productos.

    Args:
        pagina: Página de Flet sobre la que se dibuja.

    Returns:
        El control raíz de la pantalla.
    """
    servicio = ServicioProductos()
    filtros = BarraFiltros()

    return construir_pantalla_crud(
        pagina,
        ConfiguracionCrud(
            titulo="Catálogo de productos",
            entidad="el producto",
            clave_id="idproducto",
            columnas=[
                Columna("idproducto", "ID", numerica=True),
                Columna("descripcion", "Descripción"),
                Columna("marca", "Marca", formato=lambda valor: valor or "—"),
                Columna("categoria", "Categoría", formato=lambda valor: valor or "—"),
                Columna("preciocompra", "P. compra", formato=_formato_importe, numerica=True),
                Columna("precioventa", "P. venta", formato=_formato_importe, numerica=True),
                Columna("stock", "Stock", color=_color_stock, numerica=True),
                Columna("stockminimo", "Mínimo", numerica=True),
            ],
            construir_campos=_construir_campos,
            listar=lambda texto: servicio.listar(texto, filtro=filtros.filtro),
            filtros=filtros,
            crear=servicio.crear,
            actualizar=servicio.actualizar,
            eliminar=servicio.eliminar,
            marcador_busqueda="Buscar producto…",
            mensaje_vacio="Ningún producto coincide con la búsqueda o los filtros",
            texto_confirmar_borrado=(
                "¿Desea eliminar este producto? Solo es posible si nunca se ha vendido."
            ),
        ),
    )


def _campo_stock_inicial(producto: Producto | None) -> list[Campo]:
    """
    Añade el campo de stock inicial solo en el alta.

    Al editar no aparece a propósito: el stock se mueve por inventario o por una
    venta, nunca escribiéndolo a mano en la ficha del producto (RF05).

    Args:
        producto: Producto a editar, o None si es un alta.

    Returns:
        Lista con el campo, o vacía si se está editando.
    """
    if producto is not None:
        return []
    return [
        definir_campo(
            "stock",
            "Stock inicial",
            campo_entero,
            valor=STOCK_INICIAL_PREDETERMINADO,
            icono=ft.Icons.INVENTORY_2,
        )
    ]


def _opciones_categoria() -> list[tuple[object, str]]:
    """Trae las categorías disponibles para el desplegable."""
    return [(fila["idcategoria"], fila["nombre"]) for fila in servicio_categorias().listar()]


def _opciones_marca() -> list[tuple[object, str]]:
    """Trae las marcas disponibles para el desplegable."""
    return [(fila["idmarca"], fila["nombremarca"]) for fila in servicio_marcas().listar()]


def _opciones_proveedor() -> list[tuple[object, str]]:
    """Trae los proveedores disponibles para el desplegable."""
    return [
        (proveedor.idproveedor, proveedor.nombreproveedor)
        for proveedor in ServicioProveedores().listar()
    ]


def _formato_importe(valor: object) -> str:
    """
    Da formato de moneda a un importe de la tabla.

    Args:
        valor: Importe a mostrar.

    Returns:
        El importe con el símbolo de córdobas y dos decimales.
    """
    return f"C$ {Decimal(str(valor or 0)):,.2f}"


def _color_stock(producto: Producto) -> str:
    """
    Elige el color de la celda de stock según el nivel de existencias (RF07).

    Args:
        producto: Producto de la fila.

    Returns:
        El color correspondiente al nivel de existencias.
    """
    return color_estado_stock(producto.stock, producto.stockminimo)


RELACIONES_DEL_PRODUCTO: tuple[tuple[str, str, Callable[[], list[tuple[object, str]]]], ...] = (
    ("idcategoria", "Categoría", _opciones_categoria),
    ("idmarca", "Marca", _opciones_marca),
    ("idproveedor", "Proveedor", _opciones_proveedor),
)
"""Desplegables que enlazan el producto con sus catálogos: clave, rótulo y origen."""

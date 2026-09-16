"""
Pantalla del catálogo de productos (RF03, RF07, RF08).

Usa la pantalla CRUD genérica y solo añade lo propio del dominio: los tres
desplegables de relaciones y el resaltado por color del nivel de existencias.
"""

from __future__ import annotations

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
    campo_texto,
    longitud_minima,
)
from vistas.componentes.dialogos import Campo
from vistas.componentes.tablas import Columna
from vistas.crud import ConfiguracionCrud, construir_pantalla_crud

LONGITUD_MINIMA_DESCRIPCION = 2


def _construir_campos(producto: Producto | None) -> list[Campo]:
    """
    Arma el formulario de producto, precargado si se está editando.

    Args:
        producto: Producto a editar, o None si es un alta.

    Returns:
        Los campos del formulario, en orden de aparición.
    """
    return [
        Campo(
            "descripcion",
            "Descripción",
            campo_texto(
                "Descripción",
                obligatorio=True,
                valor=producto.descripcion if producto else "",
                icono=ft.Icons.DESCRIPTION,
                validador=longitud_minima(LONGITUD_MINIMA_DESCRIPCION, "La descripción"),
            ),
            obligatorio=True,
        ),
        Campo(
            "idcategoria",
            "Categoría",
            campo_seleccion(
                "Categoría",
                _opciones_categoria(),
                obligatorio=True,
                valor=producto.idcategoria if producto else None,
            ),
            obligatorio=True,
        ),
        Campo(
            "idmarca",
            "Marca",
            campo_seleccion(
                "Marca",
                _opciones_marca(),
                obligatorio=True,
                valor=producto.idmarca if producto else None,
            ),
            obligatorio=True,
        ),
        Campo(
            "idproveedor",
            "Proveedor",
            campo_seleccion(
                "Proveedor",
                _opciones_proveedor(),
                obligatorio=True,
                valor=producto.idproveedor if producto else None,
            ),
            obligatorio=True,
        ),
        Campo(
            "preciocompra",
            "Precio de compra",
            campo_decimal(
                "Precio de compra",
                obligatorio=True,
                valor=producto.preciocompra if producto else "0.00",
            ),
            obligatorio=True,
        ),
        Campo(
            "precioventa",
            "Precio de venta",
            campo_decimal(
                "Precio de venta",
                obligatorio=True,
                valor=producto.precioventa if producto else "0.00",
                minimo=Decimal("0.01"),
            ),
            obligatorio=True,
        ),
        Campo(
            "stockminimo",
            "Stock mínimo",
            campo_entero(
                "Stock mínimo",
                obligatorio=True,
                valor=producto.stockminimo if producto else 5,
                icono=ft.Icons.WARNING_AMBER,
            ),
            obligatorio=True,
        ),
        *_campo_stock_inicial(producto),
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
            listar=servicio.listar,
            crear=servicio.crear,
            actualizar=servicio.actualizar,
            eliminar=servicio.eliminar,
            marcador_busqueda="Buscar producto…",
            mensaje_vacio="Aún no hay productos en el catálogo",
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
        Campo(
            "stock",
            "Stock inicial",
            campo_entero("Stock inicial", valor=0, icono=ft.Icons.INVENTORY_2),
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

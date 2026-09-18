"""
Pruebas de que una venta registrada no se reescribe sola (RF09, RF11).

Una factura es el documento de un momento concreto. Si el precio se leyera del
catálogo al reimprimirla, cambiar la lista de precios reescribiría las ventas
pasadas: era el fallo que tenía el sistema, y estas pruebas existen para que no
vuelva.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from modulos.inventario.servicios import ServicioInventario
from modulos.productos.modelos import Producto
from modulos.productos.servicios import ServicioProductos
from modulos.ventas.servicios import ServicioVentas
from nucleo.errores import ErrorStockInsuficiente

PRECIO_INICIAL = Decimal("100.00")
PRECIO_NUEVO = Decimal("150.00")


@pytest.fixture
def producto(base_datos) -> int:
    """
    Crea un producto con precio conocido y existencias de sobra.

    Returns:
        Clave del producto creado.
    """
    return ServicioProductos().crear(
        {
            "descripcion": "Cuaderno",
            "idcategoria": 1,
            "idmarca": 1,
            "idproveedor": 1,
            "preciocompra": Decimal("20.00"),
            "precioventa": PRECIO_INICIAL,
            "stock": 50,
            "stockminimo": 5,
        }
    )


# ── El precio queda congelado en la venta ───────────────────────────────


def test_la_factura_conserva_el_precio_cobrado(producto, usuario_admin):
    """Subir el precio del producto no puede alterar una venta ya cobrada."""
    ventas = ServicioVentas()
    comprobante = ventas.registrar(usuario_admin, [{"idproducto": producto, "cantidad": 2}], "200.00")

    ServicioProductos().actualizar(producto, {"precioventa": PRECIO_NUEVO})

    detalle = ventas.obtener_detalle(comprobante.idventa).detalles[0]
    assert detalle.precioventa == PRECIO_INICIAL
    assert detalle.subtotal == PRECIO_INICIAL * 2


def test_las_lineas_suman_el_total_guardado(producto, usuario_admin):
    """
    Una factura no puede contradecirse a sí misma.

    Es la comprobación que destapó el fallo: las líneas sumaban C$ 300 y el
    total registrado decía C$ 200.
    """
    ventas = ServicioVentas()
    comprobante = ventas.registrar(usuario_admin, [{"idproducto": producto, "cantidad": 2}], "200.00")

    ServicioProductos().actualizar(producto, {"precioventa": PRECIO_NUEVO})

    venta = ventas.obtener_detalle(comprobante.idventa)
    assert sum(linea.subtotal for linea in venta.detalles) == venta.totalventa


def test_bajar_el_precio_tampoco_altera_lo_cobrado(producto, usuario_admin):
    """La protección vale en los dos sentidos, no solo al subir precios."""
    ventas = ServicioVentas()
    comprobante = ventas.registrar(usuario_admin, [{"idproducto": producto, "cantidad": 1}], "100.00")

    ServicioProductos().actualizar(producto, {"precioventa": Decimal("10.00")})

    venta = ventas.obtener_detalle(comprobante.idventa)
    assert venta.detalles[0].precioventa == PRECIO_INICIAL
    assert sum(linea.subtotal for linea in venta.detalles) == venta.totalventa


def test_dos_ventas_del_mismo_producto_conservan_su_precio(producto, usuario_admin):
    """Cada venta guarda el precio de su día, no el de la última."""
    ventas = ServicioVentas()
    primera = ventas.registrar(usuario_admin, [{"idproducto": producto, "cantidad": 1}], "100.00")

    ServicioProductos().actualizar(producto, {"precioventa": PRECIO_NUEVO})
    segunda = ventas.registrar(usuario_admin, [{"idproducto": producto, "cantidad": 1}], "200.00")

    assert ventas.obtener_detalle(primera.idventa).detalles[0].precioventa == PRECIO_INICIAL
    assert ventas.obtener_detalle(segunda.idventa).detalles[0].precioventa == PRECIO_NUEVO


def test_borrar_el_precio_del_catalogo_no_borra_el_de_la_venta(producto, usuario_admin):
    """Poner el producto a cero deja intacto lo que ya se cobró."""
    ventas = ServicioVentas()
    comprobante = ventas.registrar(usuario_admin, [{"idproducto": producto, "cantidad": 3}], "300.00")

    ServicioProductos().actualizar(producto, {"precioventa": Decimal("0.01")})

    venta = ventas.obtener_detalle(comprobante.idventa)
    assert venta.totalventa == PRECIO_INICIAL * 3
    assert sum(linea.subtotal for linea in venta.detalles) == venta.totalventa


# ── El stock no puede quedar negativo ───────────────────────────────────


def test_no_se_puede_retirar_mas_de_lo_que_hay(base_datos):
    """La comprobación de existencias vive en el UPDATE, no antes."""
    idproducto = ServicioProductos().crear(
        {
            "descripcion": "Último ejemplar",
            "idcategoria": 1,
            "idmarca": 1,
            "idproveedor": 1,
            "preciocompra": Decimal("10.00"),
            "precioventa": Decimal("20.00"),
            "stock": 1,
            "stockminimo": 0,
        }
    )
    inventario = ServicioInventario()

    with pytest.raises(ErrorStockInsuficiente):
        inventario.registrar_movimiento(idproducto, "Salida", 2)

    assert ServicioProductos().obtener(idproducto).stock == 1


def test_el_descuento_condicional_no_toca_nada_si_no_alcanza(base_datos):
    """
    El UPDATE no debe modificar la fila cuando no hay existencias.

    Se comprueba en el repositorio porque es donde está la garantía: la
    condición viaja dentro de la sentencia.
    """
    from modulos.productos.repositorio import ProductoRepositorio

    idproducto = ServicioProductos().crear(
        {
            "descripcion": "Escaso",
            "idcategoria": 1,
            "idmarca": 1,
            "idproveedor": 1,
            "preciocompra": Decimal("10.00"),
            "precioventa": Decimal("20.00"),
            "stock": 2,
            "stockminimo": 0,
        }
    )
    repositorio = ProductoRepositorio()

    assert repositorio.descontar_stock(idproducto, 5) is False
    assert ServicioProductos().obtener(idproducto).stock == 2

    assert repositorio.descontar_stock(idproducto, 2) is True
    assert ServicioProductos().obtener(idproducto).stock == 0


def test_una_venta_no_deja_el_stock_negativo(producto, usuario_admin):
    """
    Vender más de lo que hay debe rechazarse antes de tocar la caja.

    El stock se pone a cero con un ajuste de inventario y no editando el
    producto: la ficha no permite escribirlo a mano a propósito (RF05).
    """
    servicio = ServicioProductos()
    ServicioInventario().registrar_movimiento(producto, "Ajuste", 0)
    stock_antes = servicio.obtener(producto).stock
    assert stock_antes == 0

    with pytest.raises(ErrorStockInsuficiente):
        ServicioVentas().registrar(usuario_admin, [{"idproducto": producto, "cantidad": 1}], "500.00")

    assert servicio.obtener(producto).stock == stock_antes


def test_el_producto_del_catalogo_sigue_siendo_el_mismo(producto):
    """Comprobación de tipo: el servicio devuelve entidades, no diccionarios."""
    assert isinstance(ServicioProductos().obtener(producto), Producto)

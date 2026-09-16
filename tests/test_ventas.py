"""
Pruebas del punto de venta (RF04, RF09, RF10, RF11).

Cubren el cálculo del total, el descuento automático de stock, la atomicidad de
la operación y el manejo del efectivo y el cambio.
"""

from __future__ import annotations

import time
from decimal import Decimal

import pytest

from modulos.inventario.servicios import ServicioInventario
from modulos.productos.servicios import ServicioProductos
from modulos.ventas.servicios import ServicioVentas
from nucleo.errores import (
    ErrorNoEncontrado,
    ErrorStockInsuficiente,
    ErrorValidacion,
)

LIMITE_SEGUNDOS_VENTA = 3.0


def test_el_total_se_calcula_automaticamente(usuario_admin, producto_demo):
    """El total debe salir del precio en base de datos por la cantidad (RF09)."""
    comprobante = ServicioVentas().registrar(
        usuario_admin, [{"idproducto": producto_demo, "cantidad": 2}], Decimal("100.00")
    )
    assert comprobante.total == Decimal("71.00")


def test_el_cambio_se_calcula_automaticamente(usuario_admin, producto_demo):
    """El cambio debe ser el efectivo menos el total (RF09, RF11)."""
    comprobante = ServicioVentas().registrar(
        usuario_admin, [{"idproducto": producto_demo, "cantidad": 2}], Decimal("100.00")
    )
    assert comprobante.cambio == Decimal("29.00")


def test_el_importe_no_arrastra_error_de_redondeo(usuario_admin):
    """
    Los importes deben cuadrar al centavo.

    Con ``float``, 0.10 × 3 da 0.30000000000000004; con ``Decimal`` da 0.30.
    """
    idproducto = ServicioProductos().crear(
        {
            "descripcion": "Borrador",
            "idcategoria": 1,
            "idmarca": 1,
            "idproveedor": 1,
            "preciocompra": "0.05",
            "precioventa": "0.10",
            "stock": 10,
            "stockminimo": 1,
        }
    )
    comprobante = ServicioVentas().registrar(
        usuario_admin, [{"idproducto": idproducto, "cantidad": 3}], "1.00"
    )
    assert comprobante.total == Decimal("0.30")
    assert comprobante.cambio == Decimal("0.70")


def test_la_venta_descuenta_el_stock(usuario_admin, producto_demo):
    """Tras vender, las existencias deben bajar por la cantidad vendida (RF04)."""
    ServicioVentas().registrar(
        usuario_admin, [{"idproducto": producto_demo, "cantidad": 5}], Decimal("200.00")
    )
    assert ServicioProductos().obtener(producto_demo).stock == 15


def test_la_venta_deja_asiento_en_el_inventario(usuario_admin, producto_demo):
    """Cada venta debe generar un movimiento de tipo «Venta» (RF05)."""
    ServicioVentas().registrar(
        usuario_admin, [{"idproducto": producto_demo, "cantidad": 3}], Decimal("200.00")
    )
    movimientos = ServicioInventario().listar_historial(producto_demo)
    tipos = [movimiento.tipomovimiento for movimiento in movimientos]
    assert "Venta" in tipos


def test_no_se_vende_mas_de_lo_que_hay(usuario_admin, producto_demo):
    """Intentar vender por encima del stock debe rechazarse."""
    with pytest.raises(ErrorStockInsuficiente):
        ServicioVentas().registrar(
            usuario_admin, [{"idproducto": producto_demo, "cantidad": 999}], Decimal("99999.00")
        )


def test_una_venta_rechazada_no_toca_el_stock(usuario_admin, producto_demo):
    """Si la venta falla, las existencias deben quedar intactas (atomicidad)."""
    stock_inicial = ServicioProductos().obtener(producto_demo).stock
    with pytest.raises(ErrorStockInsuficiente):
        ServicioVentas().registrar(
            usuario_admin, [{"idproducto": producto_demo, "cantidad": 999}], Decimal("99999.00")
        )
    assert ServicioProductos().obtener(producto_demo).stock == stock_inicial


def test_una_venta_rechazada_no_deja_cabecera(usuario_admin, producto_demo):
    """Si la venta falla, no debe quedar registrada a medias."""
    with pytest.raises(ErrorStockInsuficiente):
        ServicioVentas().registrar(
            usuario_admin, [{"idproducto": producto_demo, "cantidad": 999}], Decimal("99999.00")
        )
    assert ServicioVentas().listar_recientes() == []


def test_el_efectivo_insuficiente_se_rechaza(usuario_admin, producto_demo):
    """Cobrar con menos efectivo que el total debe rechazarse."""
    with pytest.raises(ErrorValidacion, match="menor que el total"):
        ServicioVentas().registrar(
            usuario_admin, [{"idproducto": producto_demo, "cantidad": 2}], Decimal("10.00")
        )


def test_el_carrito_vacio_se_rechaza(usuario_admin):
    """No debe poder cobrarse una venta sin productos."""
    with pytest.raises(ErrorValidacion, match="carrito está vacío"):
        ServicioVentas().registrar(usuario_admin, [], Decimal("100.00"))


@pytest.mark.parametrize("cantidad", [0, -3])
def test_se_rechazan_cantidades_no_positivas(usuario_admin, producto_demo, cantidad: int):
    """Las cantidades del carrito deben ser mayores que cero."""
    with pytest.raises(ErrorValidacion):
        ServicioVentas().registrar(
            usuario_admin, [{"idproducto": producto_demo, "cantidad": cantidad}], Decimal("100.00")
        )


def test_se_rechaza_un_producto_inexistente(usuario_admin, base_datos):
    """Vender algo que no está en el catálogo debe avisar con claridad."""
    with pytest.raises(ErrorNoEncontrado):
        ServicioVentas().registrar(
            usuario_admin, [{"idproducto": 4321, "cantidad": 1}], Decimal("100.00")
        )


def test_el_mismo_producto_repetido_se_agrupa(usuario_admin, producto_demo):
    """Dos líneas del mismo producto deben sumarse en una sola."""
    comprobante = ServicioVentas().registrar(
        usuario_admin,
        [
            {"idproducto": producto_demo, "cantidad": 2},
            {"idproducto": producto_demo, "cantidad": 3},
        ],
        Decimal("500.00"),
    )
    assert comprobante.lineas == 1
    assert comprobante.total == Decimal("177.50")
    assert ServicioProductos().obtener(producto_demo).stock == 15


def test_la_venta_no_exige_datos_del_cliente(usuario_admin, producto_demo):
    """Debe poder cobrarse solo con productos y efectivo (RF10)."""
    comprobante = ServicioVentas().registrar(
        usuario_admin, [{"idproducto": producto_demo, "cantidad": 1}], Decimal("50.00")
    )
    assert comprobante.idventa > 0


def test_el_detalle_guarda_las_lineas(usuario_admin, producto_demo):
    """La venta debe poder consultarse con sus líneas."""
    comprobante = ServicioVentas().registrar(
        usuario_admin, [{"idproducto": producto_demo, "cantidad": 4}], Decimal("200.00")
    )
    venta = ServicioVentas().obtener_detalle(comprobante.idventa)
    assert len(venta.detalles) == 1
    assert venta.detalles[0].cantidad == 4
    assert venta.detalles[0].subtotal == Decimal("142.00")


def test_anular_una_venta_devuelve_el_stock(usuario_admin, producto_demo):
    """Anular debe reponer las existencias vendidas."""
    comprobante = ServicioVentas().registrar(
        usuario_admin, [{"idproducto": producto_demo, "cantidad": 6}], Decimal("300.00")
    )
    assert ServicioProductos().obtener(producto_demo).stock == 14

    ServicioVentas().anular(comprobante.idventa)
    assert ServicioProductos().obtener(producto_demo).stock == 20


def test_anular_una_venta_inexistente_falla(base_datos):
    """Anular algo que no existe debe avisar con claridad."""
    with pytest.raises(ErrorNoEncontrado):
        ServicioVentas().anular(777)


def test_la_venta_se_registra_en_menos_de_tres_segundos(usuario_admin, producto_demo):
    """Una venta debe procesarse en menos de 3 segundos (RNF06)."""
    inicio = time.perf_counter()
    ServicioVentas().registrar(
        usuario_admin, [{"idproducto": producto_demo, "cantidad": 1}], Decimal("50.00")
    )
    assert time.perf_counter() - inicio < LIMITE_SEGUNDOS_VENTA

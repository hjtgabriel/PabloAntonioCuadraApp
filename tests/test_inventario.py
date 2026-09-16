"""
Pruebas de los movimientos de inventario (RF04, RF05, RF07).

Vigilan en particular que registrar un movimiento **sí** mueva el stock: en la
versión anterior la vista llamaba a una función que solo anotaba el asiento y
dejaba las existencias sin tocar.
"""

from __future__ import annotations

import pytest

from modulos.inventario.modelos import TipoMovimiento
from modulos.inventario.servicios import ServicioInventario
from modulos.productos.servicios import ServicioProductos
from nucleo.errores import ErrorNoEncontrado, ErrorStockInsuficiente, ErrorValidacion


def test_una_entrada_aumenta_el_stock(producto_demo):
    """Registrar una entrada debe sumar unidades a las existencias (RF05)."""
    stock_final = ServicioInventario().registrar_movimiento(producto_demo, "Entrada", 10)
    assert stock_final == 30
    assert ServicioProductos().obtener(producto_demo).stock == 30


def test_una_salida_disminuye_el_stock(producto_demo):
    """Registrar una salida debe restar unidades a las existencias (RF05)."""
    stock_final = ServicioInventario().registrar_movimiento(producto_demo, "Salida", 8)
    assert stock_final == 12
    assert ServicioProductos().obtener(producto_demo).stock == 12


def test_un_ajuste_fija_el_stock_exacto(producto_demo):
    """En un ajuste, la cantidad indicada es el stock final deseado."""
    stock_final = ServicioInventario().registrar_movimiento(producto_demo, "Ajuste", 7)
    assert stock_final == 7
    assert ServicioProductos().obtener(producto_demo).stock == 7


def test_un_ajuste_puede_dejar_el_stock_en_cero(producto_demo):
    """Un ajuste a cero es válido; sirve para dar de baja mercadería."""
    assert ServicioInventario().registrar_movimiento(producto_demo, "Ajuste", 0) == 0


def test_cada_movimiento_queda_registrado(producto_demo):
    """Todo movimiento debe dejar un asiento con su tipo y cantidad (RF05)."""
    servicio = ServicioInventario()
    servicio.registrar_movimiento(producto_demo, "Entrada", 5)
    servicio.registrar_movimiento(producto_demo, "Salida", 2)

    historial = servicio.listar_historial(producto_demo)
    tipos = [movimiento.tipomovimiento for movimiento in historial]
    assert "Entrada" in tipos
    assert "Salida" in tipos


def test_el_alta_del_producto_genera_su_entrada_inicial(producto_demo):
    """El stock inicial de un producto nuevo debe quedar explicado en el historial."""
    historial = ServicioInventario().listar_historial(producto_demo)
    assert len(historial) == 1
    assert historial[0].tipomovimiento == "Entrada"
    assert historial[0].cantidad == 20


def test_no_se_puede_dejar_el_stock_negativo(producto_demo):
    """Una salida mayor que las existencias debe rechazarse."""
    with pytest.raises(ErrorStockInsuficiente):
        ServicioInventario().registrar_movimiento(producto_demo, "Salida", 999)


def test_un_movimiento_rechazado_no_deja_asiento(producto_demo):
    """Si el movimiento falla, tampoco debe quedar el asiento (atomicidad)."""
    servicio = ServicioInventario()
    asientos_antes = len(servicio.listar_historial(producto_demo))

    with pytest.raises(ErrorStockInsuficiente):
        servicio.registrar_movimiento(producto_demo, "Salida", 999)

    assert len(servicio.listar_historial(producto_demo)) == asientos_antes


@pytest.mark.parametrize("tipo_invalido", ["Devolución", "", "entrada-masiva"])
def test_se_rechazan_tipos_de_movimiento_desconocidos(producto_demo, tipo_invalido: str):
    """Solo se admiten los cuatro tipos previstos."""
    with pytest.raises(ErrorValidacion):
        ServicioInventario().registrar_movimiento(producto_demo, tipo_invalido, 1)


@pytest.mark.parametrize("cantidad", [0, -5])
def test_se_rechazan_cantidades_invalidas(producto_demo, cantidad: int):
    """Entradas y salidas exigen al menos una unidad."""
    with pytest.raises(ErrorValidacion):
        ServicioInventario().registrar_movimiento(producto_demo, "Entrada", cantidad)


def test_se_rechaza_un_producto_inexistente(base_datos):
    """Mover stock de algo que no existe debe avisar con claridad."""
    with pytest.raises(ErrorNoEncontrado):
        ServicioInventario().registrar_movimiento(8888, "Entrada", 1)


def test_el_producto_bajo_minimo_dispara_alerta(base_datos):
    """Un producto en su stock mínimo debe aparecer en las alertas (RF07)."""
    idproducto = ServicioProductos().crear(
        {
            "descripcion": "Regla 30 cm",
            "idcategoria": 1,
            "idmarca": 1,
            "idproveedor": 1,
            "precioventa": "25.00",
            "stock": 3,
            "stockminimo": 3,
        }
    )
    alertas = ServicioInventario().listar_alertas_stock()
    assert idproducto in [producto.idproducto for producto in alertas]


def test_el_producto_con_stock_holgado_no_alerta(producto_demo):
    """Un producto con existencias por encima del mínimo no debe alertar."""
    alertas = ServicioInventario().listar_alertas_stock()
    assert producto_demo not in [producto.idproducto for producto in alertas]


def test_la_salida_hasta_el_minimo_activa_la_alerta(producto_demo):
    """Al bajar el stock hasta el mínimo, el producto debe entrar en alerta (RF07)."""
    ServicioInventario().registrar_movimiento(producto_demo, "Salida", 15)
    alertas = ServicioInventario().listar_alertas_stock()
    assert producto_demo in [producto.idproducto for producto in alertas]


def test_el_tipo_de_movimiento_acepta_texto_y_enumerado(producto_demo):
    """El servicio debe admitir tanto la cadena como el enumerado."""
    servicio = ServicioInventario()
    assert servicio.registrar_movimiento(producto_demo, "Entrada", 1) == 21
    assert servicio.registrar_movimiento(producto_demo, TipoMovimiento.ENTRADA, 1) == 22

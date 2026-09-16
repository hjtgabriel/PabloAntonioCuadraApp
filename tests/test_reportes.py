"""Pruebas de los reportes de gestión (RF11, RF12, RF13)."""

from __future__ import annotations

from decimal import Decimal

from modulos.productos.servicios import ServicioProductos
from modulos.reportes.servicios import (
    ESTADO_BAJO,
    ESTADO_CRITICO,
    ESTADO_NORMAL,
    ServicioReportes,
)
from modulos.ventas.servicios import ServicioVentas


def test_el_reporte_semanal_suma_efectivo_y_cambio(usuario_admin, producto_demo):
    """El reporte debe informar total, efectivo recibido y cambio (RF11)."""
    ServicioVentas().registrar(
        usuario_admin, [{"idproducto": producto_demo, "cantidad": 2}], Decimal("100.00")
    )
    resumen = ServicioReportes().ventas_semanales()

    assert len(resumen) == 1
    assert resumen[0].cantidad_ventas == 1
    assert resumen[0].total_vendido == Decimal("71.00")
    assert resumen[0].total_efectivo == Decimal("100.00")
    assert resumen[0].total_cambio == Decimal("29.00")


def test_el_reporte_semanal_agrupa_varias_ventas(usuario_admin, producto_demo):
    """Varias ventas del mismo día deben sumarse en una sola fila (RF11)."""
    servicio = ServicioVentas()
    servicio.registrar(usuario_admin, [{"idproducto": producto_demo, "cantidad": 1}], "50.00")
    servicio.registrar(usuario_admin, [{"idproducto": producto_demo, "cantidad": 2}], "100.00")

    resumen = ServicioReportes().ventas_semanales()
    assert len(resumen) == 1
    assert resumen[0].cantidad_ventas == 2
    assert resumen[0].total_vendido == Decimal("106.50")


def test_el_reporte_semanal_sin_ventas_queda_vacio(base_datos):
    """Sin movimientos, el reporte no debe inventar filas."""
    assert ServicioReportes().ventas_semanales() == []


def test_los_articulos_mas_vendidos_se_ordenan(usuario_admin, base_datos):
    """El listado debe encabezarlo el artículo con más unidades vendidas (RF12)."""
    productos = ServicioProductos()
    base = {"idcategoria": 1, "idmarca": 1, "idproveedor": 1, "precioventa": "10.00", "stock": 100}
    poco = productos.crear({**base, "descripcion": "Poco vendido"})
    mucho = productos.crear({**base, "descripcion": "Muy vendido"})

    ventas = ServicioVentas()
    ventas.registrar(usuario_admin, [{"idproducto": poco, "cantidad": 2}], "100.00")
    ventas.registrar(usuario_admin, [{"idproducto": mucho, "cantidad": 9}], "100.00")

    ranking = ServicioReportes().articulos_mas_vendidos()
    assert ranking[0].descripcion == "Muy vendido"
    assert ranking[0].unidades == 9
    assert ranking[0].importe == Decimal("90.00")


def test_los_articulos_mas_vendidos_respetan_el_limite(usuario_admin, producto_demo):
    """El reporte debe poder acotarse a los primeros N artículos (RF12)."""
    ServicioVentas().registrar(
        usuario_admin, [{"idproducto": producto_demo, "cantidad": 1}], "100.00"
    )
    assert len(ServicioReportes().articulos_mas_vendidos(limite=1)) == 1


def test_el_reporte_de_stock_clasifica_los_niveles(base_datos):
    """Cada producto debe clasificarse como Crítico, Bajo o Normal (RF13)."""
    productos = ServicioProductos()
    base = {"idcategoria": 1, "idmarca": 1, "idproveedor": 1, "precioventa": "10.00"}
    productos.crear({**base, "descripcion": "Critico", "stock": 3, "stockminimo": 5})
    productos.crear({**base, "descripcion": "Bajo", "stock": 8, "stockminimo": 5})
    productos.crear({**base, "descripcion": "Normal", "stock": 40, "stockminimo": 5})

    por_nombre = {fila.descripcion: fila.estado for fila in ServicioReportes().niveles_stock()}
    assert por_nombre["Critico"] == ESTADO_CRITICO
    assert por_nombre["Bajo"] == ESTADO_BAJO
    assert por_nombre["Normal"] == ESTADO_NORMAL


def test_el_reporte_de_stock_indica_cuanto_reponer(base_datos):
    """El reporte debe ayudar a decidir la compra sugiriendo unidades (RF13)."""
    ServicioProductos().crear(
        {
            "descripcion": "Marcador",
            "idcategoria": 1,
            "idmarca": 1,
            "idproveedor": 1,
            "precioventa": "10.00",
            "stock": 2,
            "stockminimo": 5,
        }
    )
    nivel = ServicioReportes().niveles_stock()[0]
    assert nivel.unidades_a_reponer == 8


def test_el_producto_con_stock_normal_no_sugiere_reposicion(base_datos):
    """Si hay existencias de sobra, no debe sugerirse comprar (RF13)."""
    ServicioProductos().crear(
        {
            "descripcion": "Resma de papel",
            "idcategoria": 1,
            "idmarca": 1,
            "idproveedor": 1,
            "precioventa": "10.00",
            "stock": 60,
            "stockminimo": 5,
        }
    )
    assert ServicioReportes().niveles_stock()[0].unidades_a_reponer == 0

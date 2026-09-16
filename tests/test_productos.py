"""Pruebas del catálogo de productos y su historial de precios (RF03, RF06, RF08)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from modulos.productos.servicios import ServicioProductos
from modulos.ventas.servicios import ServicioVentas
from nucleo.errores import ErrorEnUso, ErrorNoEncontrado, ErrorValidacion

DATOS_BASE = {
    "descripcion": "Lapicero azul",
    "idcategoria": 1,
    "idmarca": 1,
    "idproveedor": 1,
    "preciocompra": "5.00",
    "precioventa": "12.00",
    "stock": 50,
    "stockminimo": 10,
}


@pytest.mark.parametrize("campo", ["descripcion", "idcategoria", "idmarca", "idproveedor"])
def test_los_campos_obligatorios_se_exigen(base_datos, campo: str):
    """Marca, categoría, proveedor y descripción son obligatorios (RF03)."""
    datos = {**DATOS_BASE, campo: ""}
    with pytest.raises(ErrorValidacion):
        ServicioProductos().crear(datos)


def test_se_rechaza_un_precio_negativo(base_datos):
    """Un precio de venta negativo no tiene sentido comercial."""
    with pytest.raises(ErrorValidacion, match="no puede ser negativo"):
        ServicioProductos().crear({**DATOS_BASE, "precioventa": "-1.00"})


def test_se_rechaza_un_precio_no_numerico(base_datos):
    """Un precio que no es número debe rechazarse con un mensaje claro."""
    with pytest.raises(ErrorValidacion, match="número válido"):
        ServicioProductos().crear({**DATOS_BASE, "precioventa": "doce pesos"})


def test_los_precios_se_guardan_como_decimal(base_datos):
    """Los importes deben conservarse exactos, sin pasar por ``float``."""
    idproducto = ServicioProductos().crear({**DATOS_BASE, "precioventa": "12.35"})
    assert ServicioProductos().obtener(idproducto).precioventa == Decimal("12.35")


def test_el_producto_creado_trae_sus_relaciones(base_datos):
    """El listado debe incluir los nombres de categoría, marca y proveedor."""
    idproducto = ServicioProductos().crear(DATOS_BASE)
    producto = ServicioProductos().obtener(idproducto)
    assert producto.categoria == "Papelería"
    assert producto.marca == "Genérica"
    assert producto.proveedor == "Distribuidora Central"


def test_la_busqueda_filtra_por_descripcion(base_datos):
    """Buscar por nombre debe devolver solo las coincidencias (RF08)."""
    servicio = ServicioProductos()
    servicio.crear(DATOS_BASE)
    servicio.crear({**DATOS_BASE, "descripcion": "Cuaderno rayado"})

    encontrados = servicio.listar("cuaderno")
    assert [producto.descripcion for producto in encontrados] == ["Cuaderno rayado"]


def test_la_busqueda_ignora_mayusculas(base_datos):
    """La búsqueda por nombre no debe distinguir mayúsculas (RF08)."""
    ServicioProductos().crear(DATOS_BASE)
    assert len(ServicioProductos().listar("LAPICERO")) == 1


def test_el_limite_pagina_los_resultados(base_datos):
    """El listado debe poder paginarse para catálogos grandes (RNF07)."""
    servicio = ServicioProductos()
    for numero in range(5):
        servicio.crear({**DATOS_BASE, "descripcion": f"Artículo {numero}"})

    assert len(servicio.listar(limite=2)) == 2
    assert len(servicio.listar(limite=2, desplazamiento=4)) == 1


def test_cambiar_el_precio_deja_rastro_en_el_historial(base_datos):
    """Toda variación de precio debe quedar registrada (RF06)."""
    servicio = ServicioProductos()
    idproducto = servicio.crear(DATOS_BASE)

    servicio.actualizar(idproducto, {**DATOS_BASE, "precioventa": "15.00"})

    historial = servicio.listar_historial_precios(idproducto)
    assert len(historial) == 1
    assert historial[0].precioanterior == Decimal("12.00")
    assert historial[0].precionuevo == Decimal("15.00")


def test_guardar_sin_cambiar_el_precio_no_ensucia_el_historial(base_datos):
    """Si el precio no cambió, no debe anotarse nada (RF06)."""
    servicio = ServicioProductos()
    idproducto = servicio.crear(DATOS_BASE)

    servicio.actualizar(idproducto, {**DATOS_BASE, "descripcion": "Lapicero azul fino"})

    assert servicio.listar_historial_precios(idproducto) == []


def test_la_variacion_del_historial_se_calcula(base_datos):
    """El historial debe poder informar cuánto subió o bajó el precio (RF06)."""
    servicio = ServicioProductos()
    idproducto = servicio.crear(DATOS_BASE)
    servicio.actualizar(idproducto, {**DATOS_BASE, "precioventa": "15.00"})

    assert servicio.listar_historial_precios(idproducto)[0].variacion == Decimal("3.00")


def test_actualizar_no_altera_el_stock(base_datos):
    """El stock solo se mueve por inventario o por una venta, nunca al editar."""
    servicio = ServicioProductos()
    idproducto = servicio.crear(DATOS_BASE)

    servicio.actualizar(idproducto, {**DATOS_BASE, "stock": 9999})

    assert servicio.obtener(idproducto).stock == 50


def test_obtener_un_producto_inexistente_falla(base_datos):
    """Pedir un producto que no existe debe avisar con claridad."""
    with pytest.raises(ErrorNoEncontrado):
        ServicioProductos().obtener(4444)


def test_eliminar_un_producto_sin_ventas_funciona(base_datos):
    """Un producto que nunca se vendió debe poder borrarse."""
    servicio = ServicioProductos()
    idproducto = servicio.crear(DATOS_BASE)
    assert servicio.eliminar(idproducto)


def test_no_se_elimina_un_producto_ya_vendido(usuario_admin, producto_demo):
    """Borrar un producto vendido descuadraría los reportes (RF11, RF12)."""
    ServicioVentas().registrar(
        usuario_admin, [{"idproducto": producto_demo, "cantidad": 1}], Decimal("50.00")
    )
    with pytest.raises(ErrorEnUso):
        ServicioProductos().eliminar(producto_demo)


def test_el_producto_sabe_si_esta_bajo_minimo(base_datos):
    """La entidad debe poder responder por sí misma si necesita reposición (RF07)."""
    servicio = ServicioProductos()
    critico = servicio.obtener(servicio.crear({**DATOS_BASE, "stock": 2, "stockminimo": 5}))
    holgado = servicio.obtener(servicio.crear({**DATOS_BASE, "descripcion": "Otro", "stock": 40}))

    assert critico.bajo_minimo
    assert not holgado.bajo_minimo

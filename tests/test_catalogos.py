"""
Pruebas del servicio genérico de catálogos.

Al ser un único servicio parametrizado, las mismas pruebas cubren rol,
categoría y marca. Esto es lo que se ganó al eliminar los tres servicios
duplicados.
"""

from __future__ import annotations

import pytest

from modulos.catalogos.servicios import servicio_categorias, servicio_marcas, servicio_roles
from nucleo.errores import ErrorDuplicado, ErrorEnUso, ErrorNoEncontrado, ErrorValidacion

CONSTRUCTORES = {
    "roles": servicio_roles,
    "categorias": servicio_categorias,
    "marcas": servicio_marcas,
}


@pytest.fixture(params=list(CONSTRUCTORES))
def catalogo(request, base_datos):
    """Entrega cada uno de los tres catálogos para correr la misma prueba sobre todos."""
    return CONSTRUCTORES[request.param]()


def test_crear_devuelve_la_clave_generada(catalogo):
    """Al crear una entrada debe devolverse su clave primaria."""
    identificador = catalogo.crear("Entrada nueva")
    assert identificador > 0


def test_la_entrada_creada_aparece_en_el_listado(catalogo):
    """Lo que se crea debe poder listarse."""
    catalogo.crear("Entrada visible")
    nombres = [fila[catalogo.columna_nombre] for fila in catalogo.listar()]
    assert "Entrada visible" in nombres


def test_no_se_permiten_nombres_duplicados(catalogo):
    """El nombre de un catálogo debe ser único."""
    catalogo.crear("Repetida")
    with pytest.raises(ErrorDuplicado):
        catalogo.crear("Repetida")


def test_el_duplicado_ignora_mayusculas(catalogo):
    """«REPETIDA» y «repetida» deben considerarse el mismo nombre."""
    catalogo.crear("Repetida")
    with pytest.raises(ErrorDuplicado):
        catalogo.crear("REPETIDA")


@pytest.mark.parametrize("invalido", ["", "   ", "x"])
def test_se_rechazan_nombres_muy_cortos(catalogo, invalido: str):
    """Un nombre por debajo del mínimo debe rechazarse."""
    with pytest.raises(ErrorValidacion):
        catalogo.crear(invalido)


def test_actualizar_cambia_el_nombre(catalogo):
    """Renombrar una entrada debe reflejarse en el listado."""
    identificador = catalogo.crear("Nombre viejo")
    catalogo.actualizar(identificador, "Nombre nuevo")
    nombres = [fila[catalogo.columna_nombre] for fila in catalogo.listar()]
    assert "Nombre nuevo" in nombres
    assert "Nombre viejo" not in nombres


def test_actualizar_permite_conservar_el_propio_nombre(catalogo):
    """Guardar sin cambiar el nombre no debe dispararse como duplicado."""
    identificador = catalogo.crear("Mismo nombre")
    assert catalogo.actualizar(identificador, "Mismo nombre")


def test_actualizar_una_entrada_inexistente_falla(catalogo):
    """Renombrar algo que no existe debe avisar con claridad."""
    with pytest.raises(ErrorNoEncontrado):
        catalogo.actualizar(9999, "Cualquiera")


def test_eliminar_quita_la_entrada(catalogo):
    """Borrar una entrada libre debe funcionar."""
    identificador = catalogo.crear("Descartable")
    assert catalogo.eliminar(identificador)
    assert catalogo.listar() == [] or "Descartable" not in [
        fila[catalogo.columna_nombre] for fila in catalogo.listar()
    ]


def test_eliminar_una_entrada_inexistente_falla(catalogo):
    """Borrar algo que no existe debe avisar con claridad."""
    with pytest.raises(ErrorNoEncontrado):
        catalogo.eliminar(9999)


def test_la_busqueda_filtra_por_texto(catalogo):
    """El listado con texto debe filtrar por coincidencia parcial (RF08)."""
    catalogo.crear("Cuadernos escolares")
    catalogo.crear("Lapiceros finos")
    encontrados = [fila[catalogo.columna_nombre] for fila in catalogo.listar("cuaderno")]
    assert encontrados == ["Cuadernos escolares"]


def test_no_se_elimina_una_categoria_con_productos(producto_demo):
    """Una categoría en uso por un producto no debe poder borrarse."""
    with pytest.raises(ErrorEnUso):
        servicio_categorias().eliminar(1)


def test_no_se_elimina_una_marca_con_productos(producto_demo):
    """Una marca en uso por un producto no debe poder borrarse."""
    with pytest.raises(ErrorEnUso):
        servicio_marcas().eliminar(1)


def test_no_se_elimina_un_rol_con_usuarios(usuario_admin):
    """Un rol asignado a un usuario no debe poder borrarse."""
    with pytest.raises(ErrorEnUso):
        servicio_roles().eliminar(1)

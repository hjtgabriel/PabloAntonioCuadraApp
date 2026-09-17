"""
Pruebas del filtro por marca y categoría (RF08).

Cubren las dos mitades por separado: que la consulta acote de verdad en la base
de datos, y que el componente de interfaz traduzca bien lo que el usuario
elige. Un filtro que se dibuja pero no acota, o que acota por la clave
equivocada, no falla al construirse: devuelve resultados incorrectos en
silencio, que es lo peor que puede hacer una consulta.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from modulos.inventario.modelos import TipoMovimiento
from modulos.inventario.servicios import ServicioInventario
from modulos.productos.modelos import FiltroCatalogo
from modulos.productos.servicios import ServicioProductos
from vistas.componentes.filtros import TODAS, BarraFiltros

# La base de pruebas trae categorías 1=Papelería, 2=Libros y marcas
# 1=Genérica, 2=Norma.
PAPELERIA, LIBROS = 1, 2
GENERICA, NORMA = 1, 2


@pytest.fixture
def catalogo(base_datos) -> dict[str, int]:
    """
    Crea cuatro productos que cubren las cuatro combinaciones posibles.

    Returns:
        Las claves de los productos, por un nombre corto.
    """
    servicio = ServicioProductos()

    def crear(descripcion: str, idcategoria: int, idmarca: int) -> int:
        """
        Da de alta un producto de prueba.

        Args:
            descripcion: Nombre del producto.
            idcategoria: Categoría a la que pertenece.
            idmarca: Marca a la que pertenece.

        Returns:
            La clave del producto creado.
        """
        return servicio.crear(
            {
                "descripcion": descripcion,
                "idcategoria": idcategoria,
                "idmarca": idmarca,
                "idproveedor": 1,
                "preciocompra": Decimal("10.00"),
                "precioventa": Decimal("20.00"),
                "stock": 10,
                "stockminimo": 2,
            }
        )

    return {
        "papeleria_generica": crear("Cuaderno rayado", PAPELERIA, GENERICA),
        "papeleria_norma": crear("Cuaderno Norma", PAPELERIA, NORMA),
        "libros_generica": crear("Diccionario básico", LIBROS, GENERICA),
        "libros_norma": crear("Novela Norma", LIBROS, NORMA),
    }


def descripciones(productos) -> set[str]:
    """
    Reduce una lista de productos a sus descripciones.

    Args:
        productos: Productos devueltos por el servicio.

    Returns:
        Conjunto de descripciones, para comparar sin depender del orden.
    """
    return {producto.descripcion for producto in productos}


# ── El filtro como valor ────────────────────────────────────────────────


def test_un_filtro_sin_criterios_esta_vacio():
    """Sin nada elegido, la consulta no debe acotar nada."""
    assert FiltroCatalogo().vacio is True


@pytest.mark.parametrize(
    "filtro",
    [
        FiltroCatalogo(idcategoria=PAPELERIA),
        FiltroCatalogo(idmarca=NORMA),
        FiltroCatalogo(idcategoria=PAPELERIA, idmarca=NORMA),
    ],
)
def test_un_filtro_con_cualquier_criterio_no_esta_vacio(filtro):
    """Basta un criterio para que la consulta tenga que acotar."""
    assert filtro.vacio is False


# ── Catálogo de productos ───────────────────────────────────────────────


def test_sin_filtro_se_listan_todos_los_productos(catalogo):
    """El filtro vacío no debe dejar fuera nada."""
    assert len(ServicioProductos().listar(filtro=FiltroCatalogo())) == 4


def test_el_catalogo_se_acota_por_categoria(catalogo):
    """Elegir una categoría deja solo sus productos."""
    resultado = ServicioProductos().listar(filtro=FiltroCatalogo(idcategoria=LIBROS))

    assert descripciones(resultado) == {"Diccionario básico", "Novela Norma"}


def test_el_catalogo_se_acota_por_marca(catalogo):
    """Elegir una marca deja solo sus productos."""
    resultado = ServicioProductos().listar(filtro=FiltroCatalogo(idmarca=NORMA))

    assert descripciones(resultado) == {"Cuaderno Norma", "Novela Norma"}


def test_los_dos_criterios_se_combinan(catalogo):
    """Marca y categoría se exigen a la vez, no una u otra."""
    resultado = ServicioProductos().listar(
        filtro=FiltroCatalogo(idcategoria=LIBROS, idmarca=NORMA)
    )

    assert descripciones(resultado) == {"Novela Norma"}


def test_el_filtro_se_suma_a_la_busqueda_por_texto(catalogo):
    """
    Buscar y filtrar a la vez debe estrechar el resultado, no ensancharlo.

    «Cuaderno» encuentra dos productos; acotar a la marca Norma deja uno.
    """
    servicio = ServicioProductos()

    assert len(servicio.listar("Cuaderno")) == 2
    assert descripciones(servicio.listar("Cuaderno", filtro=FiltroCatalogo(idmarca=NORMA))) == {
        "Cuaderno Norma"
    }


def test_una_combinacion_sin_productos_devuelve_vacio(catalogo):
    """Filtrar por algo que no existe devuelve nada, no un error."""
    assert ServicioProductos().listar(filtro=FiltroCatalogo(idcategoria=999)) == []


# ── Historial de inventario ─────────────────────────────────────────────


def test_el_historial_de_inventario_se_acota_por_marca(catalogo):
    """
    Los movimientos se filtran por los atributos de su producto (RF05).

    Cada alta con stock inicial deja ya una entrada anotada, así que los cuatro
    productos tienen historial; lo que comprueba la prueba es que solo queden
    los de la marca elegida.
    """
    inventario = ServicioInventario()
    inventario.registrar_movimiento(catalogo["libros_norma"], TipoMovimiento.ENTRADA, 5)
    inventario.registrar_movimiento(catalogo["papeleria_generica"], TipoMovimiento.ENTRADA, 3)

    movimientos = inventario.listar_historial(filtro=FiltroCatalogo(idmarca=NORMA))

    assert {m.descripcion for m in movimientos} == {"Cuaderno Norma", "Novela Norma"}
    assert len(inventario.listar_historial()) > len(movimientos)


def test_el_historial_de_inventario_combina_marca_y_categoria(catalogo):
    """Los dos criterios se exigen a la vez sobre el producto del movimiento."""
    inventario = ServicioInventario()

    movimientos = inventario.listar_historial(
        filtro=FiltroCatalogo(idcategoria=LIBROS, idmarca=NORMA)
    )

    assert {m.descripcion for m in movimientos} == {"Novela Norma"}


def test_el_historial_de_inventario_combina_producto_y_filtro(catalogo):
    """Si el producto elegido no cumple el filtro, no debe aparecer."""
    inventario = ServicioInventario()
    inventario.registrar_movimiento(catalogo["papeleria_generica"], TipoMovimiento.ENTRADA, 3)

    assert inventario.listar_historial(catalogo["papeleria_generica"]) != []
    assert (
        inventario.listar_historial(
            catalogo["papeleria_generica"], FiltroCatalogo(idmarca=NORMA)
        )
        == []
    )


# ── Historial de precios ────────────────────────────────────────────────


def test_el_historial_de_precios_se_acota_por_categoria(catalogo):
    """Los cambios de precio se filtran por la categoría del producto (RF06)."""
    servicio = ServicioProductos()
    servicio.actualizar(catalogo["libros_norma"], {"precioventa": Decimal("99.00")})
    servicio.actualizar(catalogo["papeleria_generica"], {"precioventa": Decimal("55.00")})

    cambios = servicio.listar_historial_precios(filtro=FiltroCatalogo(idcategoria=LIBROS))

    assert {c.descripcion for c in cambios} == {"Novela Norma"}


def test_sin_filtro_el_historial_de_precios_los_trae_todos(catalogo):
    """El filtro vacío no debe ocultar ningún cambio."""
    servicio = ServicioProductos()
    servicio.actualizar(catalogo["libros_norma"], {"precioventa": Decimal("99.00")})
    servicio.actualizar(catalogo["papeleria_generica"], {"precioventa": Decimal("55.00")})

    assert len(servicio.listar_historial_precios(filtro=FiltroCatalogo())) == 2


# ── El componente de interfaz ───────────────────────────────────────────


def test_la_barra_empieza_sin_acotar_nada(base_datos):
    """Al abrir una pantalla se ve todo: el filtro no se aplica solo."""
    barra = BarraFiltros()

    assert barra.filtro.vacio is True
    assert barra.activo is False


def test_la_barra_ofrece_los_catalogos_existentes(base_datos):
    """Los desplegables se llenan de la base, encabezados por «todas»."""
    barra = BarraFiltros()

    categorias = [opcion.text for opcion in barra._categoria.options]
    marcas = [opcion.text for opcion in barra._marca.options]

    assert categorias[0] == "Todas"
    assert marcas[0] == "Todas"
    assert "Papelería" in categorias
    assert "Norma" in marcas


def test_la_barra_traduce_lo_elegido_a_claves(base_datos):
    """Flet entrega el valor como texto; el servicio necesita enteros."""
    barra = BarraFiltros()
    barra._categoria.value = str(LIBROS)
    barra._marca.value = str(NORMA)

    assert barra.filtro == FiltroCatalogo(idcategoria=LIBROS, idmarca=NORMA)
    assert barra.activo is True


def test_volver_a_todas_deja_de_acotar(base_datos):
    """Elegir «todas» debe quitar ese criterio, no filtrar por una clave falsa."""
    barra = BarraFiltros()
    barra._categoria.value = str(LIBROS)
    barra._categoria.value = TODAS

    assert barra.filtro.idcategoria is None


def test_limpiar_quita_ambos_criterios(base_datos):
    """El botón de quitar filtros devuelve la pantalla a su estado inicial."""
    barra = BarraFiltros()
    barra._categoria.value = str(LIBROS)
    barra._marca.value = str(NORMA)

    barra.limpiar()

    assert barra.filtro.vacio is True


def test_la_barra_avisa_cuando_cambia_un_filtro(base_datos):
    """Sin el aviso, la tabla se quedaría mostrando el resultado anterior."""
    recargas: list[int] = []
    barra = BarraFiltros(lambda: recargas.append(1))

    barra._al_seleccionar(None)

    assert recargas == [1]


def test_el_aviso_puede_conectarse_despues(base_datos):
    """La pantalla CRUD conecta la recarga cuando ya existe, no al construir."""
    recargas: list[int] = []
    barra = BarraFiltros()

    barra.conectar(lambda: recargas.append(1))
    barra._al_seleccionar(None)

    assert recargas == [1]


def test_el_boton_de_quitar_filtros_solo_se_ve_si_hay_alguno(base_datos):
    """Un botón que no hace nada no debe ocupar sitio en la cabecera."""
    barra = BarraFiltros()
    assert barra._boton_limpiar.visible is False

    barra._categoria.value = str(LIBROS)
    barra._al_seleccionar(None)
    assert barra._boton_limpiar.visible is True

    barra._limpiar(None)
    assert barra._boton_limpiar.visible is False

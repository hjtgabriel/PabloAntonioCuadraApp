"""
Pruebas de los constructores de formularios de las pantallas de mantenimiento.

Las pruebas de :mod:`tests.test_interfaz` comprueban que cada pantalla se
construya sin reventar, pero no abren sus formularios. Estas comprueban lo que
falta: que cada campo declare la clave con la que el valor llega al servicio,
que los obligatorios estén marcados como tales y que al editar lleguen
precargados con lo que hay en la base de datos.

Es justo la parte que más se rompe en silencio, porque un campo con la clave
mal escrita no falla al construirse: falla al guardar.
"""

from __future__ import annotations

from decimal import Decimal

from modulos.personal.servicios import ServicioUsuarios
from modulos.productos.servicios import ServicioProductos
from modulos.proveedores.servicios import ServicioProveedores
from vistas.componentes.campos import campo_seleccion
from vistas.componentes.dialogos import Campo, definir_campo
from vistas.componentes.registros import lector, lector_de_texto, leer_valor
from vistas.personal import _campos_persona
from vistas.productos import _construir_campos


def claves(campos: list[Campo]) -> list[str]:
    """
    Extrae las claves de una lista de campos.

    Args:
        campos: Campos del formulario.

    Returns:
        Las claves, en el orden en que aparecen.
    """
    return [campo.clave for campo in campos]


def buscar(campos: list[Campo], clave: str) -> Campo:
    """
    Localiza un campo por su clave.

    Args:
        campos: Campos del formulario.
        clave: Clave a buscar.

    Returns:
        El campo encontrado.

    Raises:
        AssertionError: Si el formulario no declara esa clave.
    """
    for campo in campos:
        if campo.clave == clave:
            return campo
    raise AssertionError(f"El formulario no declara el campo «{clave}»: {claves(campos)}")


# ── definir_campo ───────────────────────────────────────────────────────


def test_definir_campo_usa_la_etiqueta_una_sola_vez():
    """La etiqueta debe llegar al rótulo del control y al propio campo."""
    campo = definir_campo("telefono", "Teléfono", valor="8888-8888")

    assert campo.clave == "telefono"
    assert campo.etiqueta == "Teléfono"
    assert campo.control.value == "8888-8888"
    assert "Teléfono" in campo.control.label


def test_definir_campo_propaga_obligatorio_al_control():
    """Un campo obligatorio se marca en el control y en el campo a la vez."""
    campo = definir_campo("nombres", "Nombres", obligatorio=True)

    assert campo.obligatorio is True
    assert "*" in campo.control.label


def test_definir_campo_admite_otras_fabricas():
    """La fábrica de control es intercambiable, no solo campo_texto."""
    campo = definir_campo(
        "idrol",
        "Rol",
        campo_seleccion,
        obligatorio=True,
        opciones=[(1, "Administrador"), (2, "Vendedor")],
        valor=2,
    )

    assert campo.control.value == "2"
    assert [opcion.text for opcion in campo.control.options] == ["Administrador", "Vendedor"]


# ── Lectura de registros ────────────────────────────────────────────────


def test_lector_devuelve_el_predeterminado_en_un_alta():
    """En un alta no hay registro, así que todo campo sale con su valor inicial."""
    valor = lector(None)

    assert valor("descripcion") == ""
    assert valor("stockminimo", 5) == 5


def test_lector_convierte_los_nulos_en_el_predeterminado():
    """Un teléfono nulo en la base no puede llegar como None a un campo de texto."""
    valor = lector({"telefono": None})

    assert valor("telefono") == ""


def test_lector_de_texto_siempre_devuelve_cadena():
    """Los campos de texto de Flet no admiten números ni None."""
    valor = lector_de_texto({"telefono": 8888, "direccion": None})

    assert valor("telefono") == "8888"
    assert valor("direccion") == ""


def test_leer_valor_funciona_con_objetos_y_diccionarios():
    """Los servicios devuelven unas veces dict y otras objetos de dominio."""

    class Registro:
        nombre = "Ana"

    assert leer_valor({"nombre": "Ana"}, "nombre") == "Ana"
    assert leer_valor(Registro(), "nombre") == "Ana"
    assert leer_valor({}, "nombre", "—") == "—"


# ── Formulario de productos ─────────────────────────────────────────────


def test_formulario_de_producto_en_alta_declara_todas_las_claves(base_datos):
    """El alta incluye el stock inicial; sus claves son las que espera el servicio."""
    campos = _construir_campos(None)

    assert claves(campos) == [
        "descripcion",
        "idcategoria",
        "idmarca",
        "idproveedor",
        "preciocompra",
        "precioventa",
        "stockminimo",
        "stock",
    ]


def test_formulario_de_producto_marca_los_obligatorios(base_datos):
    """Todo es obligatorio salvo el stock inicial, que puede quedarse en cero."""
    campos = _construir_campos(None)

    assert buscar(campos, "descripcion").obligatorio is True
    assert buscar(campos, "idcategoria").obligatorio is True
    assert buscar(campos, "precioventa").obligatorio is True
    assert buscar(campos, "stock").obligatorio is False


def test_formulario_de_producto_carga_las_relaciones_de_la_base(base_datos):
    """Los tres desplegables se llenan con los catálogos existentes."""
    campos = _construir_campos(None)

    categorias = [opcion.text for opcion in buscar(campos, "idcategoria").control.options]
    marcas = [opcion.text for opcion in buscar(campos, "idmarca").control.options]
    proveedores = [opcion.text for opcion in buscar(campos, "idproveedor").control.options]

    assert sorted(categorias) == ["Libros", "Papelería"]
    assert sorted(marcas) == ["Genérica", "Norma"]
    assert proveedores == ["Distribuidora Central"]


def test_formulario_de_producto_en_edicion_viene_precargado(producto_demo):
    """Al editar, cada campo muestra lo que hay guardado."""
    producto = ServicioProductos().obtener(producto_demo)

    campos = _construir_campos(producto)

    assert buscar(campos, "descripcion").control.value == "Cuaderno universitario"
    assert Decimal(buscar(campos, "precioventa").control.value) == Decimal("35.50")
    assert buscar(campos, "stockminimo").control.value == "5"
    assert buscar(campos, "idcategoria").control.value == "1"


def test_el_stock_no_se_edita_desde_la_ficha_del_producto(producto_demo):
    """El stock solo se mueve por inventario o por una venta (RF05)."""
    producto = ServicioProductos().obtener(producto_demo)

    assert "stock" not in claves(_construir_campos(producto))


# ── Formulario de personas ──────────────────────────────────────────────


def test_campos_de_persona_en_alta_salen_vacios():
    """Un alta no precarga nada."""
    campos = _campos_persona(None)

    assert claves(campos) == ["nombres", "apellidos", "direccion", "telefono"]
    assert all(campo.control.value == "" for campo in campos)


def test_campos_de_persona_en_edicion_vienen_precargados():
    """Al editar se muestran los datos guardados, y los nulos como vacío."""
    campos = _campos_persona(
        {"nombres": "Ana", "apellidos": "Martínez", "direccion": None, "telefono": "8888-8888"}
    )

    assert buscar(campos, "nombres").control.value == "Ana"
    assert buscar(campos, "apellidos").control.value == "Martínez"
    assert buscar(campos, "direccion").control.value == ""
    assert buscar(campos, "telefono").control.value == "8888-8888"


def test_solo_los_datos_identificatorios_son_obligatorios():
    """La dirección y el teléfono pueden quedarse en blanco."""
    campos = _campos_persona(None)

    assert buscar(campos, "nombres").obligatorio is True
    assert buscar(campos, "apellidos").obligatorio is True
    assert buscar(campos, "direccion").obligatorio is False
    assert buscar(campos, "telefono").obligatorio is False


# ── Formularios construidos dentro de cada pantalla ─────────────────────


def constructor_de_campos(modulo, pantalla):
    """
    Saca de una pantalla la función que arma su formulario.

    Cada vista importa ``construir_pantalla_crud`` a su propio espacio de
    nombres, así que el sustituto hay que ponerlo en el módulo de la vista y no
    en :mod:`vistas.crud`.

    Args:
        modulo: Módulo de la vista, donde vive el nombre a sustituir.
        pantalla: Función ``pantalla_*`` a inspeccionar.

    Returns:
        La función ``construir_campos`` que la pantalla entregó a su CRUD.
    """
    capturado = {}
    original = modulo.construir_pantalla_crud

    def espia(pag, config):
        capturado["campos"] = config.construir_campos
        return original(pag, config)

    modulo.construir_pantalla_crud = espia
    try:
        pantalla(PaginaMinima())
    finally:
        modulo.construir_pantalla_crud = original
    return capturado["campos"]


def test_formulario_de_usuario_pide_contrasena_solo_al_dar_de_alta(usuario_admin):
    """Al editar, dejar la contraseña en blanco conserva la actual."""
    from vistas import personal

    construir = constructor_de_campos(personal, personal.pantalla_usuarios)

    alta = construir(None)
    assert buscar(alta, "contrasena").obligatorio is True
    assert buscar(alta, "nombreusuario").control.value == ""

    registro = ServicioUsuarios().listar()[0]
    edicion = construir(registro)
    assert buscar(edicion, "contrasena").obligatorio is False
    assert buscar(edicion, "nombreusuario").control.value == "admin"
    assert buscar(edicion, "idrol").control.value == "1"


def test_formulario_de_proveedor_viene_precargado(base_datos):
    """El teléfono nulo de un proveedor no debe llegar como None al campo."""
    from vistas import proveedores

    ServicioProveedores().crear("Librería del Norte")
    construir = constructor_de_campos(proveedores, proveedores.pantalla_proveedores)

    registro = [p for p in ServicioProveedores().listar() if p.nombreproveedor.startswith("Libr")][
        0
    ]
    campos = construir(registro)

    assert buscar(campos, "nombreproveedor").control.value == "Librería del Norte"
    assert buscar(campos, "telefono").control.value == ""
    assert buscar(campos, "direccion").control.value == ""


def test_formulario_de_catalogo_usa_la_columna_del_servicio(base_datos):
    """Cada catálogo nombra su campo como la columna que espera su servicio."""
    from vistas import catalogos

    construir = constructor_de_campos(catalogos, catalogos.pantalla_categorias)

    assert claves(construir(None)) == ["nombre"]
    assert buscar(construir({"nombre": "Papelería"}), "nombre").control.value == "Papelería"

    construir_marcas = constructor_de_campos(catalogos, catalogos.pantalla_marcas)
    assert claves(construir_marcas(None)) == ["nombremarca"]


class PaginaMinima:
    """Página falsa suficiente para construir una pantalla en las pruebas."""

    def __init__(self) -> None:
        self.controls: list = []
        self.dialogos_mostrados: list = []

    def show_dialog(self, dialogo) -> None:
        """Registra el diálogo en lugar de dibujarlo."""
        self.dialogos_mostrados.append(dialogo)

    def pop_dialog(self):
        """Descarta el último diálogo registrado."""
        return self.dialogos_mostrados.pop() if self.dialogos_mostrados else None

    def update(self) -> None:
        """No hay ventana que refrescar."""


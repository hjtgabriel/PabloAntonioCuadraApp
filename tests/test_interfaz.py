"""
Pruebas de la capa de interfaz.

No sustituyen a probar la aplicación a mano, pero sí atrapan la clase de fallo
que arrastraba la versión anterior: pantallas que reventaban al abrirse porque
llamaban a métodos que no existen en Flet 0.86.5.

Cada prueba construye la pantalla de verdad contra la base de datos de prueba.
Si una vista usara una API inexistente, la construcción fallaría aquí.
"""

from __future__ import annotations

from decimal import Decimal

import flet as ft
import pytest

from modulos.ventas.servicios import ServicioVentas
from vistas.catalogos import pantalla_categorias, pantalla_marcas, pantalla_roles
from vistas.componentes.campos import campo_decimal, campo_entero, campo_seleccion, campo_texto
from vistas.componentes.dialogos import Campo, DialogoConfirmacion, DialogoFormulario
from vistas.componentes.tablas import Columna, TablaDatos
from vistas.historiales import pantalla_historial_inventario, pantalla_historial_precios
from vistas.inventario import pantalla_inventario
from vistas.login import pantalla_login
from vistas.personal import pantalla_empleados, pantalla_usuarios
from vistas.productos import pantalla_productos
from vistas.proveedores import pantalla_proveedores
from vistas.reportes import pantalla_reportes
from vistas.ventas import pantalla_ventas


class PaginaFalsa:
    """
    Sustituto de ``ft.Page`` para construir pantallas fuera de una ventana real.

    Registra los diálogos que se le piden mostrar, de modo que las pruebas
    puedan comprobar que una acción abre el diálogo esperado.
    """

    def __init__(self) -> None:
        """Arranca sin controles, sin diálogos y sin refrescos contados."""
        self.controls: list = []
        self.dialogos_mostrados: list = []
        self.actualizaciones = 0

    def show_dialog(self, dialogo) -> None:
        """Registra el diálogo en lugar de dibujarlo."""
        self.dialogos_mostrados.append(dialogo)

    def pop_dialog(self):
        """Descarta el último diálogo registrado."""
        return self.dialogos_mostrados.pop() if self.dialogos_mostrados else None

    def update(self) -> None:
        """Cuenta las peticiones de refresco."""
        self.actualizaciones += 1


@pytest.fixture
def pagina() -> PaginaFalsa:
    """Entrega una página falsa lista para construir pantallas."""
    return PaginaFalsa()


# ── Construcción de pantallas ───────────────────────────────────────────

PANTALLAS_SIMPLES = [
    pantalla_roles,
    pantalla_categorias,
    pantalla_marcas,
    pantalla_proveedores,
    pantalla_empleados,
    pantalla_usuarios,
    pantalla_productos,
    pantalla_inventario,
    pantalla_reportes,
    pantalla_historial_precios,
    pantalla_historial_inventario,
]


@pytest.mark.parametrize("constructor", PANTALLAS_SIMPLES, ids=lambda f: f.__name__)
def test_cada_pantalla_se_construye(pagina, base_datos, constructor):
    """Toda pantalla debe poder armarse sin errores de API."""
    assert isinstance(constructor(pagina), ft.Control)


def test_la_pantalla_de_ventas_se_construye(pagina, usuario_admin, producto_demo):
    """El punto de venta debe armarse con productos disponibles."""
    assert isinstance(pantalla_ventas(pagina, usuario_admin), ft.Control)


def test_la_pantalla_de_acceso_se_construye(pagina, base_datos):
    """La pantalla de inicio de sesión debe armarse."""
    assert isinstance(pantalla_login(pagina, lambda _sesion: None), ft.Control)


def test_las_pantallas_con_datos_se_construyen(pagina, usuario_admin, producto_demo):
    """Las pantallas deben armarse igual cuando ya hay datos cargados."""
    ServicioVentas().registrar(
        usuario_admin, [{"idproducto": producto_demo, "cantidad": 2}], Decimal("100.00")
    )
    for constructor in PANTALLAS_SIMPLES:
        assert isinstance(constructor(pagina), ft.Control)


# ── Componentes ─────────────────────────────────────────────────────────


def test_la_tabla_muestra_los_datos_cargados():
    """La tabla debe generar una fila por registro."""
    tabla = TablaDatos([Columna("nombre", "Nombre")])
    tabla.cargar([{"id": 1, "nombre": "Uno"}, {"id": 2, "nombre": "Dos"}])
    assert tabla.total_registros == 2


def test_la_tabla_vacia_no_revienta():
    """Sin datos, la tabla debe mostrar su mensaje sin fallar."""
    tabla = TablaDatos([Columna("nombre", "Nombre")], mensaje_vacio="Nada aquí")
    tabla.cargar([])
    assert tabla.total_registros == 0


def test_la_tabla_pagina_los_registros():
    """Con más registros que filas por página debe haber varias páginas (RNF07)."""
    tabla = TablaDatos([Columna("n", "N")], filas_por_pagina=10)
    tabla.cargar([{"n": numero} for numero in range(1000)])
    assert tabla.total_registros == 1000
    assert tabla._total_paginas == 100


def test_el_formateador_de_columna_se_aplica():
    """Una columna con formateador debe usarlo para el texto de la celda."""
    columna = Columna("precio", "Precio", formato=lambda valor: f"C$ {valor:.2f}")
    assert columna.texto({"precio": 12.5}) == "C$ 12.50"


def test_la_columna_lee_de_objetos_y_diccionarios():
    """La tabla debe servir tanto para entidades como para filas planas."""
    columna = Columna("nombre", "Nombre")

    class Entidad:
        """Objeto de prueba con un atributo, para leer por getattr."""

        nombre = "Desde objeto"

    assert columna.texto({"nombre": "Desde diccionario"}) == "Desde diccionario"
    assert columna.texto(Entidad()) == "Desde objeto"


def test_los_campos_se_construyen():
    """La fábrica de campos debe producir controles válidos de Flet."""
    assert isinstance(campo_texto("Nombre", obligatorio=True), ft.TextField)
    assert isinstance(campo_decimal("Precio"), ft.TextField)
    assert isinstance(campo_entero("Cantidad"), ft.TextField)
    assert isinstance(campo_seleccion("Rol", [(1, "Admin")]), ft.Dropdown)


def test_el_campo_obligatorio_se_marca_con_asterisco():
    """El rótulo debe indicar visualmente qué campos son obligatorios."""
    assert campo_texto("Nombre", obligatorio=True).label == "Nombre *"
    assert campo_texto("Nombre").label == "Nombre"


def test_los_dialogos_se_construyen():
    """Los diálogos reutilizables deben armarse sin errores de API."""
    formulario = DialogoFormulario(
        "Prueba",
        [Campo("nombre", "Nombre", campo_texto("Nombre"), obligatorio=True)],
        lambda _datos: None,
    )
    confirmacion = DialogoConfirmacion("Título", "¿Seguro?", lambda: None)
    assert isinstance(formulario, ft.AlertDialog)
    assert isinstance(confirmacion, ft.AlertDialog)


def test_el_formulario_exige_los_campos_obligatorios():
    """Un obligatorio vacío debe impedir que se entreguen los datos."""
    recibidos: list[dict] = []
    formulario = DialogoFormulario(
        "Prueba",
        [Campo("nombre", "Nombre", campo_texto("Nombre"), obligatorio=True)],
        recibidos.append,
    )
    assert formulario._recoger_valores() is None
    assert recibidos == []


def test_el_formulario_entrega_los_datos_completos():
    """Con los obligatorios llenos, el formulario debe devolver los valores."""
    formulario = DialogoFormulario(
        "Prueba",
        [Campo("nombre", "Nombre", campo_texto("Nombre", valor="Elena"), obligatorio=True)],
        lambda _datos: None,
    )
    assert formulario._recoger_valores() == {"nombre": "Elena"}


# ── Compatibilidad con Flet 0.86.5 ──────────────────────────────────────


def test_la_pagina_no_tiene_las_apis_antiguas():
    """
    Documenta por qué la interfaz se escribió como está.

    ``page.open``, ``page.close`` y ``page.snack_bar`` no existen en Flet
    0.86.5. Si una versión futura los reintroduce, esta prueba avisará para
    revisar la decisión.
    """
    for atributo in ("open", "close", "snack_bar", "dialog"):
        assert not hasattr(ft.Page, atributo), f"ft.Page.{atributo} volvió a existir"


def test_la_pagina_tiene_las_apis_actuales():
    """Las llamadas que usa la interfaz deben existir en esta versión de Flet."""
    assert hasattr(ft.Page, "show_dialog")
    assert hasattr(ft.Page, "pop_dialog")


def test_no_se_usan_controles_obsoletos():
    """
    La interfaz no debe usar ``ElevatedButton``, obsoleto desde Flet 0.80.

    Se sustituyó por ``ft.Button`` en toda la aplicación.
    """
    import pathlib

    raiz = pathlib.Path(__file__).resolve().parents[1]
    culpables = [
        ruta.relative_to(raiz).as_posix()
        for ruta in (raiz / "vistas").rglob("*.py")
        if "ElevatedButton" in ruta.read_text(encoding="utf-8")
    ]
    assert culpables == [], f"Controles obsoletos en: {culpables}"


def test_ningun_color_esta_escrito_a_mano_en_las_vistas():
    """
    Todos los colores deben venir de ``tema``.

    Es lo que garantiza que la paleta corporativa se respete y que un cambio de
    color se haga en un solo archivo (RNF03).
    """
    import pathlib
    import re

    raiz = pathlib.Path(__file__).resolve().parents[1]
    patron = re.compile(r"#[0-9A-Fa-f]{6}")
    culpables = []
    for ruta in (raiz / "vistas").rglob("*.py"):
        encontrados = patron.findall(ruta.read_text(encoding="utf-8"))
        if encontrados:
            culpables.append(f"{ruta.relative_to(raiz).as_posix()}: {encontrados}")
    assert culpables == [], f"Colores escritos a mano en: {culpables}"

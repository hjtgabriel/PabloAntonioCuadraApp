"""
Pruebas del panel principal (RF02, RF07).

El panel era la única pantalla sin pruebas, justo la que decide qué ve cada
rol. Estas pruebas cubren las dos cosas que no pueden fallar: que un vendedor
no alcance las secciones de administración, y que todas las secciones del menú
se construyan de verdad contra la base de datos, que es como se detecta el uso
de una API que no existe en Flet 0.86.5.
"""

from __future__ import annotations

import flet as ft
import pytest

from modulos.personal.modelos import UsuarioAutenticado
from vistas.dashboard import (
    AYUDA_MOSTRAR_MENU,
    AYUDA_OCULTAR_MENU,
    SECCIONES,
    PanelPrincipal,
    _resumen_alertas,
    pantalla_dashboard,
)


class PaginaFalsa:
    """Sustituto de ``ft.Page`` para construir el panel fuera de una ventana."""

    def __init__(self) -> None:
        """Arranca con las listas que el panel espera encontrar en la página."""
        self.controls: list = []
        self.dialogos_mostrados: list = []
        self.avisos: list = []
        self.overlay: list = []

    def show_dialog(self, dialogo) -> None:
        """Registra el diálogo en lugar de dibujarlo."""
        self.dialogos_mostrados.append(dialogo)

    def pop_dialog(self):
        """Descarta el último diálogo registrado."""
        return self.dialogos_mostrados.pop() if self.dialogos_mostrados else None

    def update(self) -> None:
        """No hay ventana que refrescar."""


def sesion(rol: str, administra: bool | None = None) -> UsuarioAutenticado:
    """
    Arma una sesión de prueba con el rol indicado.

    Args:
        rol: Nombre del rol del usuario.
        administra: Si el rol autoriza la administración. Si se omite, se
            deduce del nombre por comodidad de las pruebas; el sistema real lo
            lee de la columna «administra» del rol.

    Returns:
        La sesión lista para abrir el panel.
    """
    if administra is None:
        administra = rol.strip().lower().startswith("admin")
    return UsuarioAutenticado(
        idusuario=1,
        nombreusuario="ana",
        idempleado=1,
        nombres="Ana",
        apellidos="Martínez",
        idrol=1,
        rol=rol,
        rol_administra=administra,
    )


@pytest.fixture
def pagina() -> PaginaFalsa:
    """Entrega una página falsa lista para construir el panel."""
    return PaginaFalsa()


# ── Control de acceso por rol (RF02) ────────────────────────────────────


def etiquetas_visibles(rol: str, administra: bool | None = None) -> list[str]:
    """
    Lista las secciones que el menú ofrece a un rol.

    Args:
        rol: Nombre del rol a comprobar.
        administra: Si el rol autoriza la administración.

    Returns:
        Las etiquetas de las secciones permitidas.
    """
    panel = PanelPrincipal(PaginaFalsa(), sesion(rol, administra), lambda: None)
    return [seccion.etiqueta for seccion in panel._secciones]


def test_el_administrador_ve_todas_las_secciones():
    """Ninguna sección queda fuera del alcance de un administrador."""
    assert etiquetas_visibles("Administrador") == [seccion.etiqueta for seccion in SECCIONES]


def test_el_vendedor_no_alcanza_las_secciones_de_administracion():
    """Un vendedor no debe ver usuarios, roles, reportes ni respaldos (RF02)."""
    visibles = etiquetas_visibles("Vendedor")

    assert "Punto de venta" in visibles
    assert "Productos" in visibles
    for reservada in ("Usuarios", "Empleados", "Roles", "Reportes", "Respaldos"):
        assert reservada not in visibles


def test_el_menu_del_vendedor_no_queda_vacio():
    """Quitar las secciones reservadas no puede dejar al vendedor sin panel."""
    assert etiquetas_visibles("Vendedor")


@pytest.mark.parametrize("nombre", ["Administrador", "Gerencia", "Dirección", "Jefatura"])
def test_los_permisos_no_dependen_de_como_se_llame_el_rol(nombre):
    """
    El RF02 se decide por la marca del rol, no por su nombre.

    Antes bastaba con que el nombre empezara por «admin»: renombrar el rol a
    «Gerencia» dejaba a esa persona sin permisos y sin ningún aviso.
    """
    assert "Usuarios" in etiquetas_visibles(nombre, administra=True)


@pytest.mark.parametrize("nombre", ["Administrador", "Administración", "admin"])
def test_un_nombre_parecido_no_concede_permisos_por_si_solo(nombre):
    """Llamarse «Administrador» sin tener la marca no abre ninguna puerta."""
    assert "Usuarios" not in etiquetas_visibles(nombre, administra=False)


# ── Construcción del panel y de cada sección ────────────────────────────


def test_el_panel_se_construye_para_un_administrador(producto_demo, pagina):
    """Abrir el panel no debe fallar: construye además su primera sección."""
    assert pantalla_dashboard(pagina, sesion("Administrador"), lambda: None) is not None


def test_el_panel_se_construye_para_un_vendedor(producto_demo, pagina):
    """El panel recortado del vendedor también debe abrirse sin fallar."""
    assert pantalla_dashboard(pagina, sesion("Vendedor"), lambda: None) is not None


@pytest.mark.parametrize("seccion", SECCIONES, ids=lambda s: s.etiqueta)
def test_cada_seccion_del_menu_se_construye(seccion, producto_demo, usuario_admin, pagina):
    """
    Toda sección alcanzable desde el menú tiene que armarse de verdad.

    Es la prueba que atrapa una llamada a una API que Flet 0.86.5 ya no tiene:
    la pantalla no falla al declararse, sino al construirse.
    """
    assert seccion.construir(pagina, sesion("Administrador")) is not None


# ── Aviso de stock mínimo (RF07) ────────────────────────────────────────


class ProductoFalso:
    """Producto mínimo, solo con lo que necesita el texto del aviso."""

    def __init__(self, descripcion: str) -> None:
        """
        Args:
            descripcion: Nombre del producto tal como saldría en el aviso.
        """
        self.descripcion = descripcion


def test_el_aviso_de_stock_nombra_los_productos_afectados():
    """Con pocos productos se nombran todos."""
    texto = _resumen_alertas([ProductoFalso("Cuaderno"), ProductoFalso("Lápiz")])

    assert "Cuaderno" in texto
    assert "Lápiz" in texto
    assert "más" not in texto


def test_el_aviso_de_stock_resume_cuando_son_muchos():
    """Con muchos productos el aviso se recorta para no tapar la pantalla."""
    texto = _resumen_alertas([ProductoFalso(f"Producto {n}") for n in range(10)])

    assert "Producto 0" in texto
    assert "Producto 9" not in texto
    assert "y 6 más" in texto


# ── Menú plegable ───────────────────────────────────────────────────────


def panel_construido(pagina) -> PanelPrincipal:
    """
    Arma un panel ya construido, listo para interactuar.

    Args:
        pagina: Página falsa sobre la que dibujarlo.

    Returns:
        El panel con su primera sección abierta.
    """
    panel = PanelPrincipal(pagina, sesion("Administrador"), lambda: None)
    panel.construir()
    return panel


def test_el_menu_empieza_visible(producto_demo, pagina):
    """Al entrar, el menú lateral se ve: es la forma de navegar."""
    assert panel_construido(pagina)._lateral.visible is True


def test_el_boton_de_hamburguesa_oculta_el_menu(producto_demo, pagina):
    """Pulsarlo deja la sección abierta a lo ancho de toda la ventana."""
    panel = panel_construido(pagina)

    panel._alternar_menu(None)

    assert panel._lateral.visible is False


def test_el_boton_de_hamburguesa_vuelve_a_mostrar_el_menu(producto_demo, pagina):
    """Un segundo clic devuelve el menú: no puede quedarse escondido."""
    panel = panel_construido(pagina)

    panel._alternar_menu(None)
    panel._alternar_menu(None)

    assert panel._lateral.visible is True


def test_el_icono_y_la_ayuda_reflejan_el_estado_del_menu(producto_demo, pagina):
    """El botón debe decir qué hará al pulsarlo, no en qué estado está."""
    panel = panel_construido(pagina)

    assert panel._boton_menu.tooltip == AYUDA_OCULTAR_MENU
    assert panel._boton_menu.icon == ft.Icons.MENU_OPEN

    panel._alternar_menu(None)

    assert panel._boton_menu.tooltip == AYUDA_MOSTRAR_MENU
    assert panel._boton_menu.icon == ft.Icons.MENU


def test_el_boton_de_hamburguesa_esta_en_la_cabecera(producto_demo, pagina):
    """Debe quedar a la vista aunque el menú esté oculto (si no, no hay vuelta)."""
    panel = panel_construido(pagina)
    cabecera = panel._cabecera()

    assert panel._boton_menu in cabecera.content.controls


def test_ocultar_el_menu_no_cierra_la_seccion_abierta(producto_demo, pagina):
    """Plegar el menú es solo visual: el contenido sigue en su sitio."""
    panel = panel_construido(pagina)
    antes = panel._contenido.content

    panel._alternar_menu(None)

    assert panel._contenido.content is antes


# ── Orden del menú ──────────────────────────────────────────────────────

ORDEN_PEDIDO = [
    "Punto de venta",
    "Roles",
    "Empleados",
    "Usuarios",
    "Proveedores",
    "Inventario",
    "Historial de inventario",
    "Categorías",
    "Marcas",
    "Productos",
    "Historial de precios",
    "Respaldos",
    "Reportes",
]


def test_el_menu_sigue_el_orden_acordado():
    """
    El orden del menú es un acuerdo con quien administra la librería.

    Responde al uso diario del local, no a la afinidad técnica de los módulos,
    así que no puede cambiar sin querer al agregar una sección nueva.
    """
    assert [seccion.etiqueta for seccion in SECCIONES] == ORDEN_PEDIDO


def test_el_punto_de_venta_abre_primero():
    """Es la pantalla donde se pasa la jornada, así que abre al entrar."""
    assert SECCIONES[0].etiqueta == "Punto de venta"
    assert SECCIONES[0].solo_administrador is False


def test_el_vendedor_conserva_el_orden_relativo(producto_demo, pagina):
    """Quitar las secciones de administración no debe barajar las que quedan."""
    visibles = etiquetas_visibles("Vendedor")

    assert visibles == [e for e in ORDEN_PEDIDO if e in visibles]

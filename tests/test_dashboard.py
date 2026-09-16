"""
Pruebas del panel principal (RF02, RF07).

El panel era la única pantalla sin pruebas, justo la que decide qué ve cada
rol. Estas pruebas cubren las dos cosas que no pueden fallar: que un vendedor
no alcance las secciones de administración, y que todas las secciones del menú
se construyan de verdad contra la base de datos, que es como se detecta el uso
de una API que no existe en Flet 0.86.5.
"""

from __future__ import annotations

import pytest

from modulos.personal.modelos import UsuarioAutenticado
from vistas.dashboard import (
    SECCIONES,
    PanelPrincipal,
    _resumen_alertas,
    pantalla_dashboard,
)


class PaginaFalsa:
    """Sustituto de ``ft.Page`` para construir el panel fuera de una ventana."""

    def __init__(self) -> None:
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


def sesion(rol: str) -> UsuarioAutenticado:
    """
    Arma una sesión de prueba con el rol indicado.

    Args:
        rol: Nombre del rol del usuario.

    Returns:
        La sesión lista para abrir el panel.
    """
    return UsuarioAutenticado(
        idusuario=1,
        nombreusuario="ana",
        idempleado=1,
        nombres="Ana",
        apellidos="Martínez",
        idrol=1,
        rol=rol,
    )


@pytest.fixture
def pagina() -> PaginaFalsa:
    """Entrega una página falsa lista para construir el panel."""
    return PaginaFalsa()


# ── Control de acceso por rol (RF02) ────────────────────────────────────


def etiquetas_visibles(rol: str) -> list[str]:
    """
    Lista las secciones que el menú ofrece a un rol.

    Args:
        rol: Nombre del rol a comprobar.

    Returns:
        Las etiquetas de las secciones permitidas.
    """
    panel = PanelPrincipal(PaginaFalsa(), sesion(rol), lambda: None)
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


@pytest.mark.parametrize("rol", ["Administrador", "administrador", "Administración", "  ADMIN  "])
def test_el_rol_de_administracion_se_reconoce_sin_importar_como_este_escrito(rol):
    """El RF02 no puede depender de mayúsculas, espacios ni del sufijo del rol."""
    assert "Usuarios" in etiquetas_visibles(rol)


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

"""
Panel principal de la aplicación (RF02, RF07).

El menú lateral se arma a partir de una tabla de secciones en la que cada una
declara si exige rol de administración. Así el control de acceso del RF02 queda
en un solo lugar, y no en una cadena de condicionales por índice numérico como
en la versión anterior, donde agregar una sección obligaba a renumerar todas.

Al entrar se revisan las alertas de stock mínimo y se avisa al usuario (RF07).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

import flet as ft

from modulos.inventario.servicios import ServicioInventario
from modulos.personal.modelos import UsuarioAutenticado
from nucleo.errores import ErrorAplicacion
from tema import ACENTO, ESPACIO, FONDO, NAV_BG, SUPERFICIE, TEXTO, TEXTO_SUBTITULO
from vistas.catalogos import pantalla_categorias, pantalla_marcas, pantalla_roles
from vistas.componentes.notificaciones import avisar_advertencia, avisar_error
from vistas.historiales import pantalla_historial_inventario, pantalla_historial_precios
from vistas.inventario import pantalla_inventario
from vistas.personal import pantalla_empleados, pantalla_usuarios
from vistas.productos import pantalla_productos
from vistas.proveedores import pantalla_proveedores
from vistas.reportes import pantalla_reportes
from vistas.respaldos import pantalla_respaldos
from vistas.ventas import pantalla_ventas

logger = logging.getLogger(__name__)

ANCHO_MENU = 230
MAX_PRODUCTOS_EN_ALERTA = 4
AYUDA_OCULTAR_MENU = "Ocultar el menú"
AYUDA_MOSTRAR_MENU = "Mostrar el menú"


@dataclass(frozen=True, slots=True)
class Seccion:
    """
    Una entrada del menú lateral.

    Attributes:
        etiqueta: Texto visible en el menú.
        icono: Icono de la entrada.
        construir: Función que arma la pantalla; recibe la página y la sesión.
        solo_administrador: Si la sección exige rol de administración (RF02).
    """

    etiqueta: str
    icono: str
    construir: Callable[[ft.Page, UsuarioAutenticado], ft.Control]
    solo_administrador: bool = False


SECCIONES: tuple[Seccion, ...] = (
    Seccion(
        "Punto de venta",
        ft.Icons.POINT_OF_SALE,
        lambda pagina, sesion: pantalla_ventas(pagina, sesion.idusuario),
    ),
    Seccion(
        "Roles",
        ft.Icons.ADMIN_PANEL_SETTINGS,
        lambda pagina, _sesion: pantalla_roles(pagina),
        solo_administrador=True,
    ),
    Seccion(
        "Empleados",
        ft.Icons.BADGE,
        lambda pagina, _sesion: pantalla_empleados(pagina),
        solo_administrador=True,
    ),
    Seccion(
        "Usuarios",
        ft.Icons.PEOPLE,
        lambda pagina, _sesion: pantalla_usuarios(pagina),
        solo_administrador=True,
    ),
    Seccion(
        "Proveedores", ft.Icons.LOCAL_SHIPPING, lambda pagina, _sesion: pantalla_proveedores(pagina)
    ),
    Seccion("Inventario", ft.Icons.SWAP_HORIZ, lambda pagina, _sesion: pantalla_inventario(pagina)),
    Seccion(
        "Historial de inventario",
        ft.Icons.HISTORY,
        lambda pagina, _sesion: pantalla_historial_inventario(pagina),
    ),
    Seccion("Categorías", ft.Icons.CATEGORY, lambda pagina, _sesion: pantalla_categorias(pagina)),
    Seccion("Marcas", ft.Icons.LABEL, lambda pagina, _sesion: pantalla_marcas(pagina)),
    Seccion("Productos", ft.Icons.INVENTORY_2, lambda pagina, _sesion: pantalla_productos(pagina)),
    Seccion(
        "Historial de precios",
        ft.Icons.PRICE_CHANGE,
        lambda pagina, _sesion: pantalla_historial_precios(pagina),
    ),
    Seccion(
        "Respaldos",
        ft.Icons.BACKUP,
        lambda pagina, _sesion: pantalla_respaldos(pagina),
        solo_administrador=True,
    ),
    Seccion(
        "Reportes",
        ft.Icons.BAR_CHART,
        lambda pagina, _sesion: pantalla_reportes(pagina),
        solo_administrador=True,
    ),
)
"""
Entradas del menú lateral, en el orden en que aparecen.

El orden lo fija el uso del local, no la afinidad técnica de los módulos. Por
eso «Proveedores» va antes de «Inventario» y «Reportes» al final: es la
secuencia que pidió quien administra la librería. «Cerrar sesión» no está aquí
porque el menú la añade siempre como última entrada.
"""


class PanelPrincipal:
    """Marco de la aplicación: menú lateral, cabecera y área de contenido."""

    def __init__(
        self, pagina: ft.Page, sesion: UsuarioAutenticado, al_salir: Callable[[], None]
    ) -> None:
        """
        Args:
            pagina: Página de Flet sobre la que se dibuja.
            sesion: Datos del usuario que inició sesión.
            al_salir: Función a ejecutar al cerrar sesión.
        """
        self._pagina = pagina
        self._sesion = sesion
        self._al_salir = al_salir
        self._secciones = self._secciones_permitidas()

        self._contenido = ft.Container(expand=True)
        self._menu = self._construir_menu()
        self._lateral = ft.Container(content=self._menu, bgcolor=NAV_BG, width=ANCHO_MENU)
        self._boton_menu = ft.IconButton(
            icon=ft.Icons.MENU_OPEN,
            icon_color=TEXTO,
            tooltip=AYUDA_OCULTAR_MENU,
            on_click=self._alternar_menu,
        )

    def construir(self) -> ft.Control:
        """
        Arma el panel, abre la primera sección y revisa las alertas de stock.

        Returns:
            El control raíz del panel.
        """
        self._abrir_seccion(0)
        self._revisar_alertas()

        return ft.Container(
            content=ft.Row(
                [
                    self._lateral,
                    ft.Column([self._cabecera(), self._contenido], expand=True, spacing=0),
                ],
                expand=True,
                spacing=0,
            ),
            bgcolor=FONDO,
            expand=True,
        )

    # ── Control de acceso por rol (RF02) ────────────────────────

    def _secciones_permitidas(self) -> tuple[Seccion, ...]:
        """
        Filtra las secciones según el rol de la sesión (RF02).

        Returns:
            Solo las secciones que este usuario puede abrir.
        """
        if self._sesion.es_administrador:
            return SECCIONES
        return tuple(seccion for seccion in SECCIONES if not seccion.solo_administrador)

    # ── Construcción del marco ──────────────────────────────────

    def _construir_menu(self) -> ft.NavigationRail:
        """
        Arma el menú lateral con las secciones permitidas más el cierre de sesión.

        Returns:
            El menú de navegación.
        """
        destinos = [
            ft.NavigationRailDestination(icon=seccion.icono, label=seccion.etiqueta)
            for seccion in self._secciones
        ]
        destinos.append(
            ft.NavigationRailDestination(icon=ft.Icons.LOGOUT, label="Cerrar sesión")
        )

        return ft.NavigationRail(
            selected_index=0,
            extended=True,
            min_extended_width=ANCHO_MENU,
            bgcolor=NAV_BG,
            indicator_color=ACENTO,
            destinations=destinos,
            on_change=self._al_cambiar_seccion,
            expand=True,
        )

    def _cabecera(self) -> ft.Container:
        """
        Arma la barra superior con el saludo y el rol del usuario.

        Returns:
            La cabecera.
        """
        return ft.Container(
            content=ft.Row(
                [
                    self._boton_menu,
                    ft.Text(
                        f"Bienvenido, {self._sesion.nombre_completo}",
                        size=TEXTO_SUBTITULO,
                        weight=ft.FontWeight.BOLD,
                        color=TEXTO,
                    ),
                    ft.Container(expand=True),
                    ft.Chip(
                        label=ft.Text(self._sesion.rol, color=SUPERFICIE, size=12),
                        bgcolor=ACENTO,
                    ),
                ],
                spacing=ESPACIO,
            ),
            padding=ft.Padding.symmetric(horizontal=ESPACIO * 2, vertical=ESPACIO),
            bgcolor=SUPERFICIE,
        )

    # ── Navegación ──────────────────────────────────────────────

    def _alternar_menu(self, _evento: ft.ControlEvent) -> None:
        """
        Muestra u oculta el menú lateral.

        Al ocultarlo, la sección abierta pasa a ocupar el ancho completo de la
        ventana, que es lo que se agradece en las tablas anchas como la del
        catálogo de productos o la de ventas.

        Args:
            _evento: Evento del botón, que no se usa.
        """
        self._lateral.visible = not self._lateral.visible
        self._boton_menu.icon = (
            ft.Icons.MENU_OPEN if self._lateral.visible else ft.Icons.MENU
        )
        self._boton_menu.tooltip = (
            AYUDA_OCULTAR_MENU if self._lateral.visible else AYUDA_MOSTRAR_MENU
        )
        self._pagina.update()

    def _al_cambiar_seccion(self, evento: ft.ControlEvent) -> None:
        """
        Atiende la pulsación de una entrada del menú.

        Args:
            evento: Evento de cambio del menú de navegación.
        """
        indice = evento.control.selected_index
        if indice >= len(self._secciones):
            self._al_salir()
            return
        self._abrir_seccion(indice)

    def _abrir_seccion(self, indice: int) -> None:
        """
        Dibuja la sección elegida en el área de contenido.

        Si la pantalla falla al construirse, se muestra el error en su lugar en
        vez de dejar la ventana en blanco.

        Args:
            indice: Posición de la sección dentro de las permitidas.
        """
        seccion = self._secciones[indice]
        try:
            self._contenido.content = seccion.construir(self._pagina, self._sesion)
        except ErrorAplicacion as error:
            self._contenido.content = self._aviso_error(str(error))
        except Exception as error:  # noqa: BLE001 - último recurso para no tumbar la interfaz
            logger.exception("Fallo al abrir la sección «%s»", seccion.etiqueta)
            self._contenido.content = self._aviso_error(f"No se pudo abrir «{seccion.etiqueta}»: {error}")

        self._pagina.update()

    @staticmethod
    def _aviso_error(mensaje: str) -> ft.Container:
        """
        Arma el aviso que sustituye a una pantalla que no se pudo abrir.

        Args:
            mensaje: Explicación del fallo.

        Returns:
            Contenedor centrado con el aviso.
        """
        from vistas.componentes.layout import estado_vacio

        return estado_vacio(ft.Icons.ERROR_OUTLINE, "No se pudo abrir la sección", mensaje)

    # ── Alertas de stock (RF07) ─────────────────────────────────

    def _revisar_alertas(self) -> None:
        """Avisa al entrar si hay productos en su stock mínimo (RF07)."""
        try:
            alertas = ServicioInventario().listar_alertas_stock()
        except ErrorAplicacion as error:
            avisar_error(self._pagina, f"No se pudieron revisar las alertas de stock: {error}")
            return

        if not alertas:
            return

        avisar_advertencia(self._pagina, _resumen_alertas(alertas))


def pantalla_dashboard(
    pagina: ft.Page, sesion: UsuarioAutenticado, al_salir: Callable[[], None]
) -> ft.Control:
    """
    Arma el panel principal de la aplicación.

    Args:
        pagina: Página de Flet sobre la que se dibuja.
        sesion: Datos del usuario que inició sesión.
        al_salir: Función a ejecutar al cerrar sesión.

    Returns:
        El control raíz del panel.
    """
    return PanelPrincipal(pagina, sesion, al_salir).construir()


def _resumen_alertas(alertas: list) -> str:
    """
    Redacta el aviso de stock mínimo sin llenar la pantalla de nombres (RF07).

    Args:
        alertas: Productos con existencias críticas.

    Returns:
        El texto del aviso.
    """
    nombres = [producto.descripcion for producto in alertas[:MAX_PRODUCTOS_EN_ALERTA]]
    restantes = len(alertas) - len(nombres)
    listado = ", ".join(nombres)
    if restantes > 0:
        listado += f" y {restantes} más"
    return f"Stock mínimo alcanzado en: {listado}"

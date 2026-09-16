"""
Pantallas de los catálogos simples: roles, categorías y marcas (RF02, RF03).

Las tres se arman con la misma función parametrizada. En la versión anterior
esto ocupaba tres archivos de 162 líneas idénticas entre sí; aquí son tres
llamadas de una línea.
"""

from __future__ import annotations

import flet as ft

from modulos.catalogos.servicios import (
    servicio_categorias,
    servicio_marcas,
    servicio_roles,
)
from nucleo.servicio import ServicioCatalogo
from vistas.componentes.campos import longitud_minima
from vistas.componentes.dialogos import Campo, definir_campo
from vistas.componentes.registros import lector_de_texto
from vistas.componentes.tablas import Columna
from vistas.crud import ConfiguracionCrud, construir_pantalla_crud

LONGITUD_MINIMA = 2


def _pantalla_catalogo(
    pagina: ft.Page,
    servicio: ServicioCatalogo,
    *,
    titulo: str,
    entidad: str,
    titulo_columna: str,
    icono: str,
) -> ft.Control:
    """
    Arma la pantalla de mantenimiento de un catálogo.

    Args:
        pagina: Página de Flet sobre la que se dibuja.
        servicio: Servicio del catálogo a administrar.
        titulo: Encabezado de la pantalla.
        entidad: Nombre singular de lo que se administra.
        titulo_columna: Encabezado de la columna de nombre.
        icono: Icono del campo de texto.

    Returns:
        El control raíz de la pantalla.
    """
    columna_nombre = servicio.columna_nombre

    def construir_campos(registro: dict | None) -> list[Campo]:
        """Arma el formulario, precargado si se está editando."""
        return [
            definir_campo(
                columna_nombre,
                titulo_columna,
                obligatorio=True,
                valor=lector_de_texto(registro)(columna_nombre),
                icono=icono,
                validador=longitud_minima(LONGITUD_MINIMA, titulo_columna),
            )
        ]

    return construir_pantalla_crud(
        pagina,
        ConfiguracionCrud(
            titulo=titulo,
            entidad=entidad,
            clave_id=servicio.columna_clave,
            columnas=[
                Columna(servicio.columna_clave, "ID", numerica=True),
                Columna(columna_nombre, titulo_columna),
            ],
            construir_campos=construir_campos,
            listar=servicio.listar,
            crear=lambda datos: servicio.crear(datos[columna_nombre]),
            actualizar=lambda clave, datos: servicio.actualizar(clave, datos[columna_nombre]),
            eliminar=servicio.eliminar,
            marcador_busqueda=f"Buscar {entidad}…",
            mensaje_vacio=f"Aún no hay {titulo.lower()} registrados",
            texto_confirmar_borrado=f"¿Desea eliminar {entidad}? Esta acción no se puede deshacer.",
        ),
    )


def pantalla_roles(pagina: ft.Page) -> ft.Control:
    """
    Pantalla de mantenimiento de roles (RF02).

    Args:
        pagina: Página de Flet sobre la que se dibuja.

    Returns:
        El control raíz de la pantalla.
    """
    return _pantalla_catalogo(
        pagina,
        servicio_roles(),
        titulo="Roles",
        entidad="el rol",
        titulo_columna="Nombre del rol",
        icono=ft.Icons.ADMIN_PANEL_SETTINGS,
    )


def pantalla_categorias(pagina: ft.Page) -> ft.Control:
    """
    Pantalla de mantenimiento de categorías (RF03).

    Args:
        pagina: Página de Flet sobre la que se dibuja.

    Returns:
        El control raíz de la pantalla.
    """
    return _pantalla_catalogo(
        pagina,
        servicio_categorias(),
        titulo="Categorías",
        entidad="la categoría",
        titulo_columna="Nombre de la categoría",
        icono=ft.Icons.CATEGORY,
    )


def pantalla_marcas(pagina: ft.Page) -> ft.Control:
    """
    Pantalla de mantenimiento de marcas (RF03).

    Args:
        pagina: Página de Flet sobre la que se dibuja.

    Returns:
        El control raíz de la pantalla.
    """
    return _pantalla_catalogo(
        pagina,
        servicio_marcas(),
        titulo="Marcas",
        entidad="la marca",
        titulo_columna="Nombre de la marca",
        icono=ft.Icons.LABEL,
    )

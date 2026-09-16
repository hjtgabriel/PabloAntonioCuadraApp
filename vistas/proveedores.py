"""Pantalla de mantenimiento de proveedores."""

from __future__ import annotations

import flet as ft

from modulos.proveedores.servicios import ServicioProveedores
from vistas.componentes.campos import campo_texto, longitud_minima
from vistas.componentes.dialogos import Campo
from vistas.componentes.tablas import Columna, leer_valor
from vistas.crud import ConfiguracionCrud, construir_pantalla_crud

LONGITUD_MINIMA_NOMBRE = 2


def pantalla_proveedores(pagina: ft.Page) -> ft.Control:
    """
    Arma la pantalla de proveedores.

    Args:
        pagina: Página de Flet sobre la que se dibuja.

    Returns:
        El control raíz de la pantalla.
    """
    servicio = ServicioProveedores()

    def construir_campos(registro: object | None) -> list[Campo]:
        """Arma el formulario, precargado si se está editando."""
        return [
            Campo(
                "nombreproveedor",
                "Nombre del proveedor",
                campo_texto(
                    "Nombre del proveedor",
                    obligatorio=True,
                    valor=leer_valor(registro, "nombreproveedor", "") if registro else "",
                    icono=ft.Icons.LOCAL_SHIPPING,
                    validador=longitud_minima(LONGITUD_MINIMA_NOMBRE, "El nombre"),
                ),
                obligatorio=True,
            ),
            Campo(
                "telefono",
                "Teléfono",
                campo_texto(
                    "Teléfono",
                    valor=leer_valor(registro, "telefono", "") or "" if registro else "",
                    icono=ft.Icons.PHONE,
                ),
            ),
            Campo(
                "direccion",
                "Dirección",
                campo_texto(
                    "Dirección",
                    valor=leer_valor(registro, "direccion", "") or "" if registro else "",
                    icono=ft.Icons.LOCATION_ON,
                ),
            ),
        ]

    return construir_pantalla_crud(
        pagina,
        ConfiguracionCrud(
            titulo="Proveedores",
            entidad="el proveedor",
            clave_id="idproveedor",
            columnas=[
                Columna("idproveedor", "ID", numerica=True),
                Columna("nombreproveedor", "Proveedor"),
                Columna("telefono", "Teléfono", formato=lambda valor: valor or "—"),
                Columna("direccion", "Dirección", formato=lambda valor: valor or "—"),
            ],
            construir_campos=construir_campos,
            listar=servicio.listar,
            crear=lambda datos: servicio.crear(
                datos["nombreproveedor"], datos["telefono"], datos["direccion"]
            ),
            actualizar=servicio.actualizar,
            eliminar=servicio.eliminar,
            marcador_busqueda="Buscar proveedor…",
            mensaje_vacio="Aún no hay proveedores registrados",
            texto_confirmar_borrado=(
                "¿Desea eliminar este proveedor? Solo es posible si no surte ningún producto."
            ),
        ),
    )

"""
Pantalla de reportes (RF11, RF12, RF13).

Tres reportes que se alternan con botones. Cada uno se arma con la misma tabla
reutilizable y una fila de indicadores arriba con las cifras de cabecera.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import flet as ft

from modulos.reportes.servicios import (
    ESTADO_BAJO,
    ESTADO_CRITICO,
    ArticuloVendido,
    NivelStock,
    ServicioReportes,
    VentaDiaria,
)
from nucleo.errores import ErrorAplicacion
from nucleo.formato import importe
from tema import (
    ACENTO,
    AVISO,
    ERROR,
    ESPACIO,
    ESPACIO_GRANDE,
    EXITO,
    SUPERFICIE,
    TEXTO,
    estilo_boton,
)
from vistas.componentes.layout import encabezado, indicador
from vistas.componentes.notificaciones import avisar_error, avisar_fallo_inesperado
from vistas.componentes.tablas import Columna, TablaDatos


@dataclass(slots=True)
class _Reporte:
    """
    Definición de uno de los reportes disponibles.

    Attributes:
        clave: Identificador interno del reporte.
        titulo: Rótulo del botón.
        icono: Icono del botón.
        columnas: Columnas de su tabla.
        cargar: Función que devuelve las filas.
        indicadores: Función que arma las cifras de cabecera.
    """

    clave: str
    titulo: str
    icono: str
    columnas: list[Columna]
    cargar: callable
    indicadores: callable


class PantallaReportes:
    """Pantalla que alterna entre los tres reportes de gestión."""

    def __init__(self, pagina: ft.Page) -> None:
        """
        Args:
            pagina: Página de Flet sobre la que se dibuja.
        """
        self._pagina = pagina
        self._servicio = ServicioReportes()
        self._reportes = self._definir_reportes()
        self._activo = self._reportes[0]

        self._indicadores = ft.Row(spacing=ESPACIO)
        self._contenedor_tabla = ft.Container(expand=True)
        self._botones = ft.Row(spacing=ESPACIO)

    def construir(self) -> ft.Control:
        """
        Arma la pantalla y muestra el primer reporte.

        Returns:
            El control raíz de la pantalla.
        """
        self._actualizar_botones()
        self._mostrar(self._activo)

        return ft.Column(
            [
                encabezado(
                    "Reportes",
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        icon_color=ACENTO,
                        tooltip="Actualizar",
                        on_click=lambda _evento: self._mostrar(self._activo),
                    ),
                ),
                ft.Container(
                    content=ft.Column([self._botones, self._indicadores], spacing=ESPACIO),
                    padding=ft.Padding.symmetric(horizontal=ESPACIO_GRANDE),
                ),
                ft.Container(content=self._contenedor_tabla, padding=ESPACIO_GRANDE, expand=True),
            ],
            expand=True,
            spacing=ESPACIO,
        )

    # ── Definición de los reportes ──────────────────────────────

    def _definir_reportes(self) -> list[_Reporte]:
        """
        Describe los tres reportes exigidos por los requerimientos.

        Returns:
            Lista de reportes disponibles.
        """
        return [
            _Reporte(
                clave="ventas",
                titulo="Ventas de la semana",
                icono=ft.Icons.CALENDAR_MONTH,
                columnas=[
                    Columna("fecha", "Fecha", formato=str),
                    Columna("cantidad_ventas", "N.º de ventas", numerica=True),
                    Columna("total_vendido", "Total vendido", formato=importe, numerica=True),
                    Columna("total_efectivo", "Efectivo recibido", formato=importe, numerica=True),
                    Columna("total_cambio", "Cambio entregado", formato=importe, numerica=True),
                ],
                cargar=self._servicio.ventas_semanales,
                indicadores=_indicadores_ventas,
            ),
            _Reporte(
                clave="vendidos",
                titulo="Artículos más vendidos",
                icono=ft.Icons.TRENDING_UP,
                columnas=[
                    Columna("descripcion", "Artículo"),
                    Columna("marca", "Marca"),
                    Columna("categoria", "Categoría"),
                    Columna("unidades", "Unidades", numerica=True),
                    Columna("importe", "Importe", formato=importe, numerica=True),
                ],
                cargar=self._servicio.articulos_mas_vendidos,
                indicadores=_indicadores_vendidos,
            ),
            _Reporte(
                clave="stock",
                titulo="Nivel de stock",
                icono=ft.Icons.INVENTORY,
                columnas=[
                    Columna("descripcion", "Producto"),
                    Columna("marca", "Marca"),
                    Columna("stock", "Stock", numerica=True),
                    Columna("stockminimo", "Mínimo", numerica=True),
                    Columna("estado", "Estado", color=_color_estado),
                    Columna("unidades_a_reponer", "Reponer", numerica=True),
                ],
                cargar=self._servicio.niveles_stock,
                indicadores=_indicadores_stock,
            ),
        ]

    # ── Presentación ────────────────────────────────────────────

    def _mostrar(self, reporte: _Reporte) -> None:
        """
        Carga y dibuja un reporte.

        Args:
            reporte: Reporte a mostrar.
        """
        self._activo = reporte
        self._actualizar_botones()

        try:
            filas = reporte.cargar()
        except ErrorAplicacion as error:
            avisar_error(self._pagina, str(error))
            return
        except Exception as error:  # noqa: BLE001 - último recurso para no tumbar la interfaz
            avisar_fallo_inesperado(self._pagina, "generar el reporte", error)
            return

        tabla = TablaDatos(
            reporte.columnas,
            mensaje_vacio="No hay datos para este reporte",
        )
        self._contenedor_tabla.content = tabla
        self._indicadores.controls = reporte.indicadores(filas)

        self._pagina.update()
        tabla.cargar(filas)

    def _actualizar_botones(self) -> None:
        """Redibuja los botones resaltando el reporte activo."""
        self._botones.controls = [
            ft.Button(
                reporte.titulo,
                icon=reporte.icono,
                bgcolor=ACENTO if reporte.clave == self._activo.clave else SUPERFICIE,
                color=SUPERFICIE if reporte.clave == self._activo.clave else TEXTO,
                style=estilo_boton(),
                on_click=lambda _evento, elegido=reporte: self._mostrar(elegido),
            )
            for reporte in self._reportes
        ]


def pantalla_reportes(pagina: ft.Page) -> ft.Control:
    """
    Arma la pantalla de reportes.

    Args:
        pagina: Página de Flet sobre la que se dibuja.

    Returns:
        El control raíz de la pantalla.
    """
    return PantallaReportes(pagina).construir()


# ── Indicadores de cabecera ─────────────────────────────────────────────


def _indicadores_ventas(filas: list[VentaDiaria]) -> list[ft.Control]:
    """
    Arma las cifras de cabecera del reporte semanal (RF11).

    Args:
        filas: Resumen diario de ventas.

    Returns:
        Indicadores de total facturado, efectivo, cambio y número de ventas.
    """
    total = sum((fila.total_vendido for fila in filas), Decimal("0"))
    efectivo = sum((fila.total_efectivo for fila in filas), Decimal("0"))
    cambio = sum((fila.total_cambio for fila in filas), Decimal("0"))
    ventas = sum(fila.cantidad_ventas for fila in filas)

    return [
        indicador("Ventas registradas", str(ventas), ACENTO, ft.Icons.RECEIPT_LONG),
        indicador("Total facturado", importe(total), EXITO, ft.Icons.PAYMENTS),
        indicador("Efectivo recibido", importe(efectivo), TEXTO, ft.Icons.ACCOUNT_BALANCE_WALLET),
        indicador("Cambio entregado", importe(cambio), AVISO, ft.Icons.CURRENCY_EXCHANGE),
    ]


def _indicadores_vendidos(filas: list[ArticuloVendido]) -> list[ft.Control]:
    """
    Arma las cifras de cabecera del ranking de artículos (RF12).

    Args:
        filas: Artículos ordenados por unidades vendidas.

    Returns:
        Indicadores del artículo líder y del total de unidades.
    """
    if not filas:
        return [indicador("Sin ventas registradas", "—", TEXTO, ft.Icons.INFO)]

    unidades = sum(fila.unidades for fila in filas)
    return [
        indicador("Artículo más vendido", filas[0].descripcion, ACENTO, ft.Icons.STAR),
        indicador("Unidades del líder", str(filas[0].unidades), EXITO, ft.Icons.TRENDING_UP),
        indicador("Unidades en el listado", str(unidades), TEXTO, ft.Icons.INVENTORY_2),
    ]


def _indicadores_stock(filas: list[NivelStock]) -> list[ft.Control]:
    """
    Arma las cifras de cabecera del reporte de existencias (RF13).

    Args:
        filas: Niveles de stock por producto.

    Returns:
        Indicadores de productos críticos, bajos y normales.
    """
    criticos = sum(1 for fila in filas if fila.estado == ESTADO_CRITICO)
    bajos = sum(1 for fila in filas if fila.estado == ESTADO_BAJO)
    reponer = sum(fila.unidades_a_reponer for fila in filas)

    return [
        indicador("Productos en el catálogo", str(len(filas)), TEXTO, ft.Icons.INVENTORY_2),
        indicador("En estado crítico", str(criticos), ERROR, ft.Icons.WARNING),
        indicador("En estado bajo", str(bajos), AVISO, ft.Icons.TRENDING_DOWN),
        indicador("Unidades a reponer", str(reponer), ACENTO, ft.Icons.ADD_SHOPPING_CART),
    ]


# ── Formateadores ───────────────────────────────────────────────────────


def _color_estado(fila: NivelStock) -> str:
    """
    Elige el color del estado de existencias (RF13).

    Args:
        fila: Nivel de stock de la fila.

    Returns:
        Rojo si es crítico, ámbar si es bajo, verde si es normal.
    """
    if fila.estado == ESTADO_CRITICO:
        return ERROR
    if fila.estado == ESTADO_BAJO:
        return AVISO
    return EXITO

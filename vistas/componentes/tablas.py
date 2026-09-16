"""
Tabla de datos reutilizable.

Admite columnas configurables, formateadores por columna, acciones por fila,
selección de fila y paginación. La paginación no es cosmética: es lo que
permite listar 1.000 productos o más sin que la interfaz se vuelva lenta
(RNF07).

A diferencia de la versión anterior, la devolución de llamada de selección sí
está conectada: antes se guardaba en un atributo y no se usaba nunca, así que
el panel de movimientos de inventario era inalcanzable.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import flet as ft

from tema import (
    ACENTO,
    ALTO_FILA,
    BORDE,
    ERROR,
    ESPACIO,
    NAV_BG,
    SUPERFICIE,
    TEXTO,
    TEXTO_ATENUADO,
)
from vistas.componentes.refresco import refrescar

FILAS_POR_PAGINA = 25
MAX_BOTONES_PAGINA = 7


@dataclass(slots=True)
class Columna:
    """
    Definición de una columna de la tabla.

    Attributes:
        clave: Atributo o clave del que sacar el valor de cada fila.
        titulo: Encabezado visible.
        formato: Conversión del valor a texto; por omisión se usa ``str``.
        color: Función que elige el color del texto según la fila completa.
        numerica: Si el contenido se alinea a la derecha.
    """

    clave: str
    titulo: str
    formato: Callable[[Any], str] | None = None
    color: Callable[[Any], str] | None = None
    numerica: bool = False

    def texto(self, fila: Any) -> str:
        """
        Obtiene el texto a mostrar para una fila.

        Args:
            fila: Registro completo, sea diccionario u objeto.

        Returns:
            El valor ya formateado.
        """
        valor = leer_valor(fila, self.clave)
        if self.formato is not None:
            return self.formato(valor)
        return "" if valor is None else str(valor)


def leer_valor(fila: Any, clave: str, por_omision: Any = None) -> Any:
    """
    Lee un campo de una fila, ya sea un diccionario o un objeto.

    Args:
        fila: Registro del que leer.
        clave: Nombre del campo.
        por_omision: Valor a devolver si el campo no existe.

    Returns:
        El valor encontrado, o ``por_omision``.
    """
    if isinstance(fila, dict):
        return fila.get(clave, por_omision)
    return getattr(fila, clave, por_omision)


class TablaDatos(ft.Column):
    """
    Tabla con encabezado, filas, acciones y control de paginación.

    Es un ``Column`` y no un ``DataTable`` para poder incluir la barra de
    paginación debajo de la tabla como parte del mismo componente.
    """

    def __init__(
        self,
        columnas: list[Columna],
        *,
        al_editar: Callable[[Any], None] | None = None,
        al_eliminar: Callable[[Any], None] | None = None,
        al_seleccionar: Callable[[Any], None] | None = None,
        mensaje_vacio: str = "No hay registros",
        filas_por_pagina: int = FILAS_POR_PAGINA,
    ) -> None:
        """
        Args:
            columnas: Columnas a mostrar, en orden.
            al_editar: Acción del botón de edición; si es None no se muestra.
            al_eliminar: Acción del botón de borrado; si es None no se muestra.
            al_seleccionar: Acción al pulsar una fila; si es None no se activa.
            mensaje_vacio: Texto a mostrar cuando no hay datos.
            filas_por_pagina: Cuántos registros mostrar por página.
        """
        self._columnas = columnas
        self._al_editar = al_editar
        self._al_eliminar = al_eliminar
        self._al_seleccionar = al_seleccionar
        self._mensaje_vacio = mensaje_vacio
        self._filas_por_pagina = filas_por_pagina

        self._datos: list[Any] = []
        self._pagina_actual = 0

        self._tabla = self._construir_tabla()
        self._paginacion = ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=4)
        self._resumen = ft.Text("", size=12, color=TEXTO_ATENUADO)

        super().__init__(
            controls=[
                ft.Column([self._tabla], scroll=ft.ScrollMode.AUTO, expand=True),
                ft.Row(
                    [self._resumen, ft.Container(expand=True), self._paginacion],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ],
            expand=True,
            spacing=ESPACIO,
        )

    # ── API pública ─────────────────────────────────────────────

    def cargar(self, datos: list[Any]) -> None:
        """
        Reemplaza el contenido de la tabla y vuelve a la primera página.

        Args:
            datos: Registros a mostrar.
        """
        self._datos = list(datos)
        self._pagina_actual = 0
        self._refrescar()

    @property
    def total_registros(self) -> int:
        """Cantidad de registros cargados, contando todas las páginas."""
        return len(self._datos)

    # ── Construcción ────────────────────────────────────────────

    def _construir_tabla(self) -> ft.DataTable:
        """
        Crea el ``DataTable`` con sus encabezados.

        Returns:
            La tabla vacía, lista para recibir filas.
        """
        encabezados = [
            ft.DataColumn(
                ft.Text(columna.titulo, weight=ft.FontWeight.BOLD, color=TEXTO),
                numeric=columna.numerica,
            )
            for columna in self._columnas
        ]
        if self._tiene_acciones():
            encabezados.append(
                ft.DataColumn(ft.Text("Acciones", weight=ft.FontWeight.BOLD, color=TEXTO))
            )

        return ft.DataTable(
            columns=encabezados,
            rows=[],
            border=ft.Border(bottom=ft.BorderSide(1, BORDE)),
            heading_row_color={ft.ControlState.DEFAULT: NAV_BG},
            heading_row_height=ALTO_FILA,
            data_row_min_height=ALTO_FILA,
            horizontal_margin=ESPACIO,
            column_spacing=16,
            show_checkbox_column=False,
        )

    def _tiene_acciones(self) -> bool:
        """Indica si hay que reservar la columna de botones."""
        return self._al_editar is not None or self._al_eliminar is not None

    def _refrescar(self) -> None:
        """Reconstruye las filas visibles, el resumen y la paginación."""
        visibles = self._filas_de_la_pagina()

        self._tabla.rows = (
            [self._fila_vacia()] if not visibles else [self._construir_fila(f) for f in visibles]
        )
        self._actualizar_resumen()
        self._actualizar_paginacion()

        refrescar(self)

    def _filas_de_la_pagina(self) -> list[Any]:
        """
        Recorta los registros correspondientes a la página actual.

        Returns:
            Los registros visibles ahora mismo.
        """
        inicio = self._pagina_actual * self._filas_por_pagina
        return self._datos[inicio: inicio + self._filas_por_pagina]

    def _construir_fila(self, fila: Any) -> ft.DataRow:
        """
        Arma una fila de la tabla a partir de un registro.

        Args:
            fila: Registro a representar.

        Returns:
            La fila lista para la tabla.
        """
        celdas = [
            ft.DataCell(
                ft.Text(
                    columna.texto(fila),
                    color=columna.color(fila) if columna.color else TEXTO,
                    overflow=ft.TextOverflow.ELLIPSIS,
                )
            )
            for columna in self._columnas
        ]
        if self._tiene_acciones():
            celdas.append(ft.DataCell(self._botones_accion(fila)))

        return ft.DataRow(
            cells=celdas,
            on_select_change=self._crear_manejador_seleccion(fila),
        )

    def _crear_manejador_seleccion(self, fila: Any) -> Callable | None:
        """
        Crea el manejador de pulsación de una fila.

        Args:
            fila: Registro asociado a la fila.

        Returns:
            El manejador, o None si la tabla no admite selección.
        """
        if self._al_seleccionar is None:
            return None
        return lambda _evento: self._al_seleccionar(fila)

    def _botones_accion(self, fila: Any) -> ft.Row:
        """
        Arma los botones de edición y borrado de una fila.

        Args:
            fila: Registro asociado a la fila.

        Returns:
            Fila de botones.
        """
        botones: list[ft.Control] = []
        if self._al_editar is not None:
            botones.append(
                ft.IconButton(
                    icon=ft.Icons.EDIT,
                    icon_color=ACENTO,
                    icon_size=18,
                    tooltip="Editar",
                    on_click=lambda _evento, registro=fila: self._al_editar(registro),
                )
            )
        if self._al_eliminar is not None:
            botones.append(
                ft.IconButton(
                    icon=ft.Icons.DELETE,
                    icon_color=ERROR,
                    icon_size=18,
                    tooltip="Eliminar",
                    on_click=lambda _evento, registro=fila: self._al_eliminar(registro),
                )
            )
        return ft.Row(botones, spacing=4, tight=True)

    def _fila_vacia(self) -> ft.DataRow:
        """
        Crea la fila que se muestra cuando no hay datos.

        Flet exige que toda fila tenga exactamente tantas celdas como columnas,
        así que se rellenan las restantes con texto vacío.

        Returns:
            La fila de estado vacío.
        """
        total = len(self._tabla.columns)
        celdas = [ft.DataCell(ft.Text(self._mensaje_vacio, color=TEXTO_ATENUADO, italic=True))]
        celdas.extend(ft.DataCell(ft.Text("")) for _ in range(total - 1))
        return ft.DataRow(cells=celdas)

    # ── Paginación ──────────────────────────────────────────────

    @property
    def _total_paginas(self) -> int:
        """Cantidad de páginas necesarias para los datos cargados."""
        if not self._datos:
            return 1
        return (len(self._datos) + self._filas_por_pagina - 1) // self._filas_por_pagina

    def _actualizar_resumen(self) -> None:
        """Refresca el texto que indica cuántos registros se están viendo."""
        if not self._datos:
            self._resumen.value = ""
            return

        inicio = self._pagina_actual * self._filas_por_pagina + 1
        fin = min(inicio + self._filas_por_pagina - 1, len(self._datos))
        self._resumen.value = f"Mostrando {inicio}–{fin} de {len(self._datos)} registros"

    def _actualizar_paginacion(self) -> None:
        """Reconstruye la barra de paginación, ocultándola si sobra una sola página."""
        if self._total_paginas <= 1:
            self._paginacion.controls = []
            return

        controles: list[ft.Control] = [
            self._boton_navegacion(ft.Icons.FIRST_PAGE, "Primera", 0, self._pagina_actual == 0),
            self._boton_navegacion(
                ft.Icons.CHEVRON_LEFT, "Anterior", self._pagina_actual - 1, self._pagina_actual == 0
            ),
        ]
        controles.extend(self._botones_de_numero())
        ultima = self._total_paginas - 1
        controles.extend(
            [
                self._boton_navegacion(
                    ft.Icons.CHEVRON_RIGHT,
                    "Siguiente",
                    self._pagina_actual + 1,
                    self._pagina_actual >= ultima,
                ),
                self._boton_navegacion(
                    ft.Icons.LAST_PAGE, "Última", ultima, self._pagina_actual >= ultima
                ),
            ]
        )
        self._paginacion.controls = controles

    def _botones_de_numero(self) -> list[ft.Control]:
        """
        Arma los botones de número, centrados en la página actual.

        Con muchos registros no se dibujan todas las páginas: se muestra una
        ventana alrededor de la actual para no llenar la pantalla de botones.

        Returns:
            Los botones de número a mostrar.
        """
        mitad = MAX_BOTONES_PAGINA // 2
        inicio = max(0, min(self._pagina_actual - mitad, self._total_paginas - MAX_BOTONES_PAGINA))
        fin = min(self._total_paginas, inicio + MAX_BOTONES_PAGINA)

        botones: list[ft.Control] = []
        for numero in range(max(0, inicio), fin):
            if numero == self._pagina_actual:
                botones.append(
                    ft.Container(
                        ft.Text(str(numero + 1), color=SUPERFICIE, weight=ft.FontWeight.BOLD),
                        bgcolor=ACENTO,
                        border_radius=4,
                        padding=8,
                    )
                )
            else:
                botones.append(
                    ft.TextButton(
                        str(numero + 1),
                        style=ft.ButtonStyle(color=TEXTO),
                        on_click=lambda _evento, destino=numero: self._ir_a_pagina(destino),
                    )
                )
        return botones

    def _boton_navegacion(
        self, icono: str, ayuda: str, destino: int, desactivado: bool
    ) -> ft.IconButton:
        """
        Crea un botón de salto de página.

        Args:
            icono: Icono del botón.
            ayuda: Texto de ayuda emergente.
            destino: Página a la que salta.
            desactivado: Si el botón debe mostrarse inactivo.

        Returns:
            El botón listo para la barra de paginación.
        """
        return ft.IconButton(
            icon=icono,
            icon_color=ACENTO,
            tooltip=ayuda,
            disabled=desactivado,
            on_click=lambda _evento: self._ir_a_pagina(destino),
        )

    def _ir_a_pagina(self, numero: int) -> None:
        """
        Cambia la página visible.

        Args:
            numero: Página destino, empezando en cero.
        """
        if 0 <= numero < self._total_paginas:
            self._pagina_actual = numero
            self._refrescar()

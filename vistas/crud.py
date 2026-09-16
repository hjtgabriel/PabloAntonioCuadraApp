"""
Pantalla CRUD genérica.

Esta es la pieza que elimina la mayor duplicación que tenía el proyecto: las
vistas de categorías, marcas, roles, proveedores y empleados eran archivos de
unas 160 líneas idénticas entre sí salvo por el nombre de la entidad, con una
similitud medida de hasta el 78 %.

Aquí están una sola vez el listado, la búsqueda, el alta, la edición, el borrado
con confirmación y el manejo de errores. Cada pantalla concreta se reduce a
describir sus columnas, sus campos de formulario y qué servicio invocar.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import flet as ft

from nucleo.errores import ErrorAplicacion
from vistas.componentes.busqueda import BarraBusqueda
from vistas.componentes.dialogos import Campo, DialogoConfirmacion, DialogoFormulario
from vistas.componentes.layout import pantalla_con_boton
from vistas.componentes.notificaciones import avisar_error, avisar_exito
from vistas.componentes.registros import leer_valor
from vistas.componentes.tablas import Columna, TablaDatos

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ConfiguracionCrud:
    """
    Descripción de una pantalla de mantenimiento.

    Attributes:
        titulo: Encabezado de la pantalla.
        entidad: Nombre singular de lo que se administra («la categoría»).
        clave_id: Campo que contiene la clave primaria de cada registro.
        columnas: Columnas de la tabla.
        construir_campos: Función que arma los campos del formulario. Recibe el
            registro a editar, o None si es un alta.
        listar: Función que devuelve los registros; recibe el texto buscado.
        crear: Función de alta; recibe los valores del formulario.
        actualizar: Función de edición; recibe la clave y los valores.
        eliminar: Función de baja; recibe la clave.
        marcador_busqueda: Texto de ayuda de la barra de búsqueda.
        mensaje_vacio: Qué mostrar cuando no hay registros.
        texto_confirmar_borrado: Pregunta de la confirmación de borrado.
    """

    titulo: str
    entidad: str
    clave_id: str
    columnas: list[Columna]
    construir_campos: Callable[[Any | None], list[Campo]]
    listar: Callable[[str], list[Any]]
    crear: Callable[[dict], Any] | None = None
    actualizar: Callable[[Any, dict], Any] | None = None
    eliminar: Callable[[Any], Any] | None = None
    marcador_busqueda: str = "Buscar…"
    mensaje_vacio: str = "No hay registros"
    texto_confirmar_borrado: str = "¿Está seguro de eliminar este registro?"


class PantallaCrud:
    """
    Pantalla de mantenimiento construida a partir de una configuración.

    Es una clase y no una función para que cada devolución de llamada pueda
    consultar el estado de la pantalla sin recurrir a variables capturadas por
    cierre, que era lo que volvía ilegibles las vistas anteriores.
    """

    def __init__(self, pagina: ft.Page, configuracion: ConfiguracionCrud) -> None:
        """
        Args:
            pagina: Página de Flet sobre la que se dibuja.
            configuracion: Descripción de la pantalla.
        """
        self._pagina = pagina
        self._config = configuracion

        self._tabla = TablaDatos(
            configuracion.columnas,
            al_editar=self._abrir_edicion if configuracion.actualizar else None,
            al_eliminar=self._confirmar_borrado if configuracion.eliminar else None,
            mensaje_vacio=configuracion.mensaje_vacio,
        )
        self._busqueda = BarraBusqueda(
            self._buscar, marcador=configuracion.marcador_busqueda
        )

    def construir(self) -> ft.Control:
        """
        Arma la pantalla y carga los datos iniciales.

        Returns:
            El control raíz de la pantalla.
        """
        self._recargar()
        return pantalla_con_boton(
            self._config.titulo,
            self._tabla,
            f"Agregar {self._config.entidad}",
            self._abrir_alta,
            self._busqueda,
        )

    # ── Carga de datos ──────────────────────────────────────────

    def _recargar(self) -> None:
        """Vuelve a consultar los datos respetando el texto buscado."""
        self._buscar(self._busqueda.texto)

    def _buscar(self, texto: str) -> None:
        """
        Consulta los registros y los vuelca en la tabla (RF08).

        Args:
            texto: Término de búsqueda; vacío para listar todo.
        """
        try:
            self._tabla.cargar(self._config.listar(texto))
        except ErrorAplicacion as error:
            avisar_error(self._pagina, str(error))
        except Exception as error:  # noqa: BLE001 - último recurso para no tumbar la interfaz
            avisar_error(self._pagina, f"No se pudo cargar {self._config.titulo}: {error}")

    # ── Alta ────────────────────────────────────────────────────

    def _abrir_alta(self, _evento: ft.ControlEvent) -> None:
        """Muestra el formulario vacío para dar de alta un registro."""
        if self._config.crear is None:
            return

        self._abrir_dialogo(
            lambda: DialogoFormulario(
                self._pagina,
                f"Nuevo · {self._config.entidad}",
                self._config.construir_campos(None),
                self._guardar_alta,
            )
        )

    def _guardar_alta(self, datos: dict) -> None:
        """
        Da de alta el registro y refresca la tabla.

        Args:
            datos: Valores recogidos del formulario.
        """
        self._ejecutar(
            lambda: self._config.crear(datos),
            f"Se agregó {self._config.entidad} correctamente",
        )

    # ── Edición ─────────────────────────────────────────────────

    def _abrir_edicion(self, registro: Any) -> None:
        """
        Muestra el formulario con los datos del registro elegido.

        Args:
            registro: Registro a editar.
        """
        if self._config.actualizar is None:
            return

        identificador = leer_valor(registro, self._config.clave_id)
        self._abrir_dialogo(
            lambda: DialogoFormulario(
                self._pagina,
                f"Editar · {self._config.entidad}",
                self._config.construir_campos(registro),
                lambda datos: self._guardar_edicion(identificador, datos),
            )
        )

    def _guardar_edicion(self, identificador: Any, datos: dict) -> None:
        """
        Guarda los cambios del registro y refresca la tabla.

        Args:
            identificador: Clave del registro editado.
            datos: Valores recogidos del formulario.
        """
        self._ejecutar(
            lambda: self._config.actualizar(identificador, datos),
            f"Se actualizó {self._config.entidad} correctamente",
        )

    # ── Baja ────────────────────────────────────────────────────

    def _confirmar_borrado(self, registro: Any) -> None:
        """
        Pide confirmación antes de borrar.

        Args:
            registro: Registro a borrar.
        """
        if self._config.eliminar is None:
            return

        identificador = leer_valor(registro, self._config.clave_id)
        self._abrir_dialogo(
            lambda: DialogoConfirmacion(
                self._pagina,
                "Confirmar eliminación",
                self._config.texto_confirmar_borrado,
                lambda: self._borrar(identificador),
            )
        )

    def _borrar(self, identificador: Any) -> None:
        """
        Borra el registro y refresca la tabla.

        Args:
            identificador: Clave del registro a borrar.
        """
        self._ejecutar(
            lambda: self._config.eliminar(identificador),
            f"Se eliminó {self._config.entidad} correctamente",
        )

    # ── Ejecución con manejo de errores ─────────────────────────

    def _abrir_dialogo(self, construir: Callable[[], ft.AlertDialog]) -> None:
        """
        Arma un diálogo y lo muestra, avisando si no se pudo abrir.

        Armar un formulario puede fallar: los desplegables de relaciones
        consultan la base de datos, y un registro con un dato inesperado rompe
        la construcción. Sin esta protección la excepción sube al despacho de
        eventos de Flet, que la descarta: el usuario pulsa el botón y no ocurre
        absolutamente nada, sin diálogo, sin aviso y sin rastro en el registro.

        Args:
            construir: Función que arma el diálogo a mostrar.
        """
        try:
            dialogo = construir()
        except ErrorAplicacion as error:
            avisar_error(self._pagina, str(error))
            return
        except Exception as error:  # noqa: BLE001 - último recurso para no tumbar la interfaz
            logger.exception("No se pudo armar el diálogo de %s", self._config.titulo)
            avisar_error(self._pagina, f"No se pudo abrir el formulario: {error}")
            return

        self._pagina.show_dialog(dialogo)

    def _ejecutar(self, operacion: Callable[[], Any], mensaje_exito: str) -> None:
        """
        Ejecuta una operación de escritura informando del resultado.

        Los errores de negocio se muestran con su propio mensaje, que es
        descriptivo; solo los fallos imprevistos caen en el mensaje genérico.

        Args:
            operacion: Función a ejecutar.
            mensaje_exito: Confirmación a mostrar si todo salió bien.
        """
        try:
            operacion()
        except ErrorAplicacion as error:
            avisar_error(self._pagina, str(error))
            return
        except Exception as error:  # noqa: BLE001 - último recurso para no tumbar la interfaz
            avisar_error(self._pagina, f"Ocurrió un problema inesperado: {error}")
            return

        avisar_exito(self._pagina, mensaje_exito)
        self._recargar()


def construir_pantalla_crud(pagina: ft.Page, configuracion: ConfiguracionCrud) -> ft.Control:
    """
    Atajo para crear y construir una pantalla de mantenimiento.

    Args:
        pagina: Página de Flet sobre la que se dibuja.
        configuracion: Descripción de la pantalla.

    Returns:
        El control raíz de la pantalla.
    """
    return PantallaCrud(pagina, configuracion).construir()

"""
Diálogos reutilizables.

Se abren con ``pagina.show_dialog(...)`` y se cierran con
``pagina.pop_dialog()``, que es la forma correcta en Flet 0.86.5; el
``page.open()`` que usaba la versión anterior no existe en esta versión y
lanzaba ``AttributeError`` en cada alta y cada edición.

Cada apertura construye un diálogo nuevo. Además de ser más simple de razonar,
evita el ``RuntimeError`` que Flet lanza si se intenta mostrar un diálogo que
ya está abierto.

Todo diálogo recibe la página en el constructor y **no** la deduce de
``self.page``. En Flet 0.86.5 ``Control.page`` recorre la cadena de padres
hasta encontrar la página y lanza ``RuntimeError`` si no la alcanza; un diálogo
mostrado con ``show_dialog`` cuelga de ``page._dialogs``, que puede no estar
montado todavía cuando el usuario pulsa un botón. Por eso ``self.page`` fallaba
al confirmar, y con él se caían el guardar de toda alta y edición y el eliminar
de todo módulo: el diálogo se abría, pero el botón no hacía nada.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import flet as ft

from tema import (
    ACENTO,
    ERROR,
    ESPACIO,
    ESPACIO_GRANDE,
    RADIO_TARJETA,
    SUPERFICIE,
    TEXTO,
    TEXTO_SUBTITULO,
    estilo_boton,
)
from vistas.componentes.campos import campo_texto
from vistas.componentes.refresco import refrescar

ANCHO_FORMULARIO = 440


@dataclass(slots=True)
class Campo:
    """
    Campo de un formulario de diálogo.

    Attributes:
        clave: Nombre con el que el valor llega al servicio.
        etiqueta: Rótulo visible, usado en los mensajes de error.
        control: Control de Flet que captura el valor.
        obligatorio: Si no puede quedar vacío.
    """

    clave: str
    etiqueta: str
    control: ft.Control
    obligatorio: bool = False


def definir_campo(
    clave: str,
    etiqueta: str,
    fabrica: Callable[..., ft.Control] = campo_texto,
    *,
    obligatorio: bool = False,
    **opciones: object,
) -> Campo:
    """
    Declara un campo de formulario en una sola llamada.

    Sin esta función cada campo repite tres veces lo mismo: la etiqueta una vez
    para el rótulo y otra para los mensajes de error, y el ``obligatorio`` una
    vez para la validación y otra para el asterisco del rótulo. Al repetirlo a
    mano basta con cambiar solo una de las dos copias para que el diálogo avise
    de un campo con un nombre que ya no es el que ve el usuario.

    Args:
        clave: Nombre con el que el valor llega al servicio.
        etiqueta: Rótulo visible, usado también en los mensajes de error.
        fabrica: Función de :mod:`~vistas.componentes.campos` que crea el
            control. Todas reciben la etiqueta y ``obligatorio``.
        obligatorio: Si el campo no puede quedar vacío.
        **opciones: Resto de parámetros propios de la fábrica elegida, por
            ejemplo ``valor``, ``icono``, ``validador`` u ``opciones``.

    Returns:
        El campo listo para agregar al formulario.
    """
    control = fabrica(etiqueta, obligatorio=obligatorio, **opciones)
    return Campo(clave, etiqueta, control, obligatorio=obligatorio)


class DialogoBase(ft.AlertDialog):
    """
    Base de los diálogos de la aplicación: guarda la página y sabe cerrarse.

    Concentra el cierre en un solo sitio para que ningún diálogo vuelva a
    depender de ``self.page``.
    """

    def _recordar_pagina(self, pagina: ft.Page) -> None:
        """
        Guarda la página con la que el diálogo se abrirá y se cerrará.

        Se llama antes de ``super().__init__()`` porque los manejadores de los
        botones se construyen dentro de esa llamada.

        Args:
            pagina: Página sobre la que se muestra el diálogo.
        """
        self._pagina = pagina

    def cerrar(self, _evento: ft.ControlEvent | None = None) -> None:
        """
        Cierra el diálogo.

        Args:
            _evento: Evento del botón, que no se usa.
        """
        self._pagina.pop_dialog()


class DialogoFormulario(DialogoBase):
    """
    Diálogo de alta o edición construido a partir de una lista de campos.

    La validación de obligatorios se hace aquí una sola vez, en lugar de
    repetirla en cada vista.
    """

    def __init__(
        self,
        pagina: ft.Page,
        titulo: str,
        campos: list[Campo],
        al_guardar: Callable[[dict], None],
        *,
        texto_guardar: str = "Guardar",
    ) -> None:
        """
        Args:
            pagina: Página sobre la que se muestra el diálogo.
            titulo: Encabezado del diálogo.
            campos: Campos del formulario, en orden de aparición.
            al_guardar: Función que recibe los valores ya validados.
            texto_guardar: Rótulo del botón de confirmación.
        """
        self._recordar_pagina(pagina)
        self._campos = campos
        self._al_guardar = al_guardar
        self._error = ft.Text("", size=12, color=ERROR, visible=False)

        contenido = ft.Column(
            [
                ft.Text(titulo, size=TEXTO_SUBTITULO, weight=ft.FontWeight.BOLD, color=TEXTO),
                self._error,
                ft.Column(
                    [campo.control for campo in campos],
                    spacing=ESPACIO,
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                ),
            ],
            tight=True,
            spacing=ESPACIO,
            width=ANCHO_FORMULARIO,
        )

        super().__init__(
            modal=True,
            content=ft.Container(
                contenido,
                padding=ESPACIO_GRANDE,
                bgcolor=SUPERFICIE,
                border_radius=RADIO_TARJETA,
            ),
            actions=[
                ft.TextButton(
                    "Cancelar",
                    icon=ft.Icons.CLOSE,
                    on_click=self.cerrar,
                    style=ft.ButtonStyle(color=TEXTO),
                ),
                ft.Button(
                    texto_guardar,
                    icon=ft.Icons.SAVE,
                    on_click=self._al_confirmar,
                    bgcolor=ACENTO,
                    color=SUPERFICIE,
                    style=estilo_boton(),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    def _al_confirmar(self, _evento: ft.ControlEvent) -> None:
        """Valida el formulario y, si está completo, entrega los datos y cierra."""
        datos = self._recoger_valores()
        if datos is None:
            return

        self.cerrar()
        self._al_guardar(datos)

    def _recoger_valores(self) -> dict | None:
        """
        Reúne los valores del formulario comprobando los obligatorios.

        Returns:
            Los valores por clave, o None si falta algún campo obligatorio.
        """
        datos: dict = {}
        for campo in self._campos:
            valor = getattr(campo.control, "value", None)
            if campo.obligatorio and not str(valor or "").strip():
                self._mostrar_error(f"«{campo.etiqueta}» es obligatorio")
                return None
            datos[campo.clave] = valor.strip() if isinstance(valor, str) else valor

        self._ocultar_error()
        return datos

    def _mostrar_error(self, mensaje: str) -> None:
        """
        Muestra un mensaje de error dentro del diálogo.

        Args:
            mensaje: Texto a mostrar.
        """
        self._error.value = mensaje
        self._error.visible = True
        refrescar(self)

    def _ocultar_error(self) -> None:
        """Quita el mensaje de error si estaba visible."""
        if self._error.visible:
            self._error.visible = False
            refrescar(self)


class DialogoConfirmacion(DialogoBase):
    """Diálogo de sí o no, usado para confirmar borrados y otras acciones."""

    def __init__(
        self,
        pagina: ft.Page,
        titulo: str,
        mensaje: str,
        al_confirmar: Callable[[], None],
        *,
        texto_confirmar: str = "Eliminar",
        destructiva: bool = True,
    ) -> None:
        """
        Args:
            pagina: Página sobre la que se muestra el diálogo.
            titulo: Encabezado del diálogo.
            mensaje: Pregunta que se le hace al usuario.
            al_confirmar: Función a ejecutar si acepta.
            texto_confirmar: Rótulo del botón de aceptación.
            destructiva: Si la acción borra datos; cambia el color y el icono.
        """
        self._recordar_pagina(pagina)
        self._al_confirmar = al_confirmar

        super().__init__(
            modal=True,
            title=ft.Text(titulo, color=TEXTO, weight=ft.FontWeight.BOLD),
            content=ft.Text(mensaje, color=TEXTO),
            actions=[
                ft.TextButton(
                    "Cancelar",
                    icon=ft.Icons.CLOSE,
                    on_click=self.cerrar,
                    style=ft.ButtonStyle(color=TEXTO),
                ),
                ft.Button(
                    texto_confirmar,
                    icon=ft.Icons.DELETE if destructiva else ft.Icons.CHECK,
                    on_click=self._confirmar,
                    bgcolor=ERROR if destructiva else ACENTO,
                    color=SUPERFICIE,
                    style=estilo_boton(),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    def _confirmar(self, _evento: ft.ControlEvent) -> None:
        """Cierra el diálogo y ejecuta la acción confirmada."""
        self.cerrar()
        self._al_confirmar()


class DialogoInformacion(DialogoBase):
    """Diálogo de solo lectura, para mostrar un comprobante o un detalle."""

    def __init__(self, pagina: ft.Page, titulo: str, contenido: ft.Control) -> None:
        """
        Args:
            pagina: Página sobre la que se muestra el diálogo.
            titulo: Encabezado del diálogo.
            contenido: Control con la información a mostrar.
        """
        self._recordar_pagina(pagina)
        super().__init__(
            modal=True,
            title=ft.Text(titulo, color=TEXTO, weight=ft.FontWeight.BOLD),
            content=contenido,
            actions=[
                ft.Button(
                    "Aceptar",
                    icon=ft.Icons.CHECK,
                    on_click=self.cerrar,
                    bgcolor=ACENTO,
                    color=SUPERFICIE,
                    style=estilo_boton(),
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

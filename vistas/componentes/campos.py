"""
Fábrica de campos de formulario.

Todos los campos de la aplicación salen de aquí, de modo que compartan borde,
color y comportamiento. Los colores provienen de :mod:`tema`; ningún campo
define un código hexadecimal propio.

Cada campo lleva su validador incorporado y muestra el error en el propio
control (``TextField.error``, que es el nombre del atributo en Flet 0.86.5).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from decimal import Decimal, InvalidOperation

import flet as ft

from tema import ACENTO, BORDE, SUPERFICIE, TEXTO_NORMAL
from vistas.componentes.refresco import refrescar

Validador = Callable[[str], str | None]
"""Función que recibe el valor y devuelve un mensaje de error, o None si está bien."""

PATRON_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PATRON_TELEFONO = re.compile(r"^\d+(-\d+)*$")
"""
Dígitos, opcionalmente separados por guiones simples.

El guion se admite porque es como se anotan los teléfonos en el local
(«8676-7203»). Lo que no se admite es cualquier otra cosa: letras,
espacios, paréntesis o el signo «+», que harían que el mismo número
quedara guardado de formas distintas según quién lo escriba.
"""

# Los avisos van debajo del campo, que en el punto de venta mide unos 300 px.
# Un texto más largo se corta con puntos suspensivos y deja al usuario sin
# saber qué corregir, así que se redactan cortos a propósito.

MENSAJE_SOLO_NUMEROS_POSITIVOS = "Formato inválido: solo números positivos"
MENSAJE_TELEFONO = "Solo números y guiones, sin letras ni símbolos"
LONGITUD_MINIMA_TELEFONO = 7
LONGITUD_MAXIMA_TELEFONO = 15


def campo_texto(
    etiqueta: str,
    *,
    obligatorio: bool = False,
    valor: str = "",
    icono: str | None = None,
    validador: Validador | None = None,
    **extras: object,
) -> ft.TextField:
    """
    Crea un campo de texto con el estilo de la aplicación.

    Args:
        etiqueta: Rótulo del campo. Si es obligatorio se le añade un asterisco.
        obligatorio: Si el campo no puede quedar vacío.
        valor: Valor inicial.
        icono: Icono a mostrar al inicio del campo.
        validador: Comprobación adicional a aplicar mientras se escribe.
        **extras: Cualquier otro parámetro admitido por ``ft.TextField``.

    Returns:
        El campo listo para agregar a un formulario.
    """
    campo = ft.TextField(
        label=_rotulo(etiqueta, obligatorio),
        value=valor,
        prefix_icon=icono,
        border_color=BORDE,
        focused_border_color=ACENTO,
        bgcolor=SUPERFICIE,
        text_size=TEXTO_NORMAL,
        **extras,
    )
    if validador is not None:
        _conectar_validador(campo, validador)
    return campo


def campo_contrasena(
    etiqueta: str = "Contraseña",
    *,
    obligatorio: bool = True,
    ayuda: str | None = None,
) -> ft.TextField:
    """
    Crea un campo de contraseña oculto, con opción de revelarla.

    Args:
        etiqueta: Rótulo del campo.
        obligatorio: Si el campo no puede quedar vacío.
        ayuda: Texto de apoyo bajo el campo, por ejemplo para explicar que
            dejarlo en blanco conserva la contraseña actual.

    Returns:
        El campo listo para agregar a un formulario.
    """
    return campo_texto(
        etiqueta,
        obligatorio=obligatorio,
        password=True,
        can_reveal_password=True,
        icono=ft.Icons.LOCK,
        helper=ft.Text(ayuda, size=12) if ayuda else None,
    )


def campo_decimal(
    etiqueta: str,
    *,
    obligatorio: bool = False,
    valor: object = "0.00",
    minimo: Decimal = Decimal("0"),
    icono: str = ft.Icons.ATTACH_MONEY,
    filtrar_entrada: bool = True,
) -> ft.TextField:
    """
    Crea un campo para importes monetarios.

    Args:
        etiqueta: Rótulo del campo.
        obligatorio: Si el campo no puede quedar vacío.
        valor: Valor inicial.
        minimo: Importe mínimo aceptado.
        icono: Icono a mostrar al inicio del campo.
        filtrar_entrada: Si se impide teclear caracteres que no sean cifras.
            Desactivarlo deja escribir cualquier cosa para que el validador
            pueda explicar qué está mal: bloquear la tecla en silencio no le
            dice al usuario por qué no pasa nada al escribir.

    Returns:
        El campo listo para agregar a un formulario.
    """
    extras: dict[str, object] = {"keyboard_type": ft.KeyboardType.NUMBER}
    if filtrar_entrada:
        extras["input_filter"] = ft.InputFilter(regex_string=r"^[0-9]*\.?[0-9]*$")

    return campo_texto(
        etiqueta,
        obligatorio=obligatorio,
        valor=str(valor),
        icono=icono,
        validador=_validador_decimal(obligatorio, minimo),
        **extras,
    )


def campo_entero(
    etiqueta: str,
    *,
    obligatorio: bool = False,
    valor: object = 0,
    minimo: int = 0,
    icono: str = ft.Icons.NUMBERS,
) -> ft.TextField:
    """
    Crea un campo para cantidades enteras.

    Args:
        etiqueta: Rótulo del campo.
        obligatorio: Si el campo no puede quedar vacío.
        valor: Valor inicial.
        minimo: Cantidad mínima aceptada.
        icono: Icono a mostrar al inicio del campo.

    Returns:
        El campo listo para agregar a un formulario.
    """
    return campo_texto(
        etiqueta,
        obligatorio=obligatorio,
        valor=str(valor),
        icono=icono,
        validador=_validador_entero(obligatorio, minimo),
        keyboard_type=ft.KeyboardType.NUMBER,
        input_filter=ft.NumbersOnlyInputFilter(),
    )


def campo_fecha(etiqueta: str, *, obligatorio: bool = False, valor: str = "") -> ft.TextField:
    """
    Crea un campo de fecha en formato AAAA-MM-DD.

    Args:
        etiqueta: Rótulo del campo.
        obligatorio: Si el campo no puede quedar vacío.
        valor: Valor inicial.

    Returns:
        El campo listo para agregar a un formulario.
    """
    return campo_texto(
        etiqueta,
        obligatorio=obligatorio,
        valor=valor,
        icono=ft.Icons.CALENDAR_TODAY,
        validador=_validador_fecha(obligatorio),
        keyboard_type=ft.KeyboardType.DATETIME,
    )


def campo_telefono(
    etiqueta: str = "Teléfono",
    *,
    obligatorio: bool = False,
    valor: str = "",
) -> ft.TextField:
    """
    Crea un campo de teléfono que solo admite dígitos.

    El teclado numérico se sugiere, pero la validación no se apoya en él: un
    teclado es una comodidad y no una garantía, porque el texto puede llegar
    pegado desde el portapapeles.

    Args:
        etiqueta: Rótulo del campo.
        obligatorio: Si el campo no puede quedar vacío.
        valor: Valor inicial.

    Returns:
        El campo listo para agregar a un formulario.
    """
    return campo_texto(
        etiqueta,
        obligatorio=obligatorio,
        valor=valor,
        icono=ft.Icons.PHONE,
        validador=_validador_telefono(obligatorio),
        keyboard_type=ft.KeyboardType.PHONE,
    )


def campo_seleccion(
    etiqueta: str,
    opciones: list[tuple[object, str]],
    *,
    obligatorio: bool = False,
    valor: object = None,
    al_seleccionar: Callable | None = None,
) -> ft.Dropdown:
    """
    Crea una lista desplegable.

    En Flet 0.86.5 el evento del desplegable se llama ``on_select``; el
    ``on_change`` de versiones anteriores ya no existe.

    Args:
        etiqueta: Rótulo del campo.
        opciones: Pares (clave, texto a mostrar).
        obligatorio: Si hay que elegir una opción sí o sí.
        valor: Clave seleccionada inicialmente.
        al_seleccionar: Función a ejecutar cuando cambia la selección.

    Returns:
        El desplegable listo para agregar a un formulario.
    """
    return ft.Dropdown(
        label=_rotulo(etiqueta, obligatorio),
        value=str(valor) if valor is not None else None,
        options=[ft.DropdownOption(key=str(clave), text=texto) for clave, texto in opciones],
        border_color=BORDE,
        focused_border_color=ACENTO,
        bgcolor=SUPERFICIE,
        on_select=al_seleccionar,
    )


def actualizar_opciones(
    desplegable: ft.Dropdown, opciones: list[tuple[object, str]]
) -> None:
    """
    Reemplaza las opciones de un desplegable ya construido.

    Args:
        desplegable: Campo a actualizar.
        opciones: Pares (clave, texto a mostrar).
    """
    desplegable.options = [
        ft.DropdownOption(key=str(clave), text=texto) for clave, texto in opciones
    ]


# ── Validadores ─────────────────────────────────────────────────────────


def longitud_minima(minimo: int, etiqueta: str) -> Validador:
    """
    Construye un validador de longitud mínima.

    Args:
        minimo: Cantidad mínima de caracteres.
        etiqueta: Nombre del campo para el mensaje.

    Returns:
        Validador listo para pasar a un campo.
    """

    def validar(valor: str) -> str | None:
        """
        Comprueba que el texto llegue a la longitud exigida.

        Un campo vacío se da por bueno: de exigirlo se encarga ``obligatorio``,
        no este validador.

        Args:
            valor: Texto escrito en el campo.

        Returns:
            El mensaje de error, o None si el texto es aceptable.
        """
        if valor and len(valor.strip()) < minimo:
            return f"{etiqueta} debe tener al menos {minimo} caracteres"
        return None

    return validar


def _validador_decimal(obligatorio: bool, minimo: Decimal) -> Validador:
    """
    Construye el validador de un importe monetario.

    Args:
        obligatorio: Si el campo no puede quedar vacío.
        minimo: Importe mínimo aceptado.

    Returns:
        Validador listo para pasar a un campo.
    """

    def validar(valor: str) -> str | None:
        """
        Comprueba que el texto sea un importe válido y no baje del mínimo.

        Args:
            valor: Texto escrito en el campo.

        Returns:
            El mensaje de error, o None si el importe es aceptable.
        """
        texto = (valor or "").strip()
        if not texto:
            return "Este campo es obligatorio" if obligatorio else None
        try:
            importe = Decimal(texto)
        except InvalidOperation:
            return MENSAJE_SOLO_NUMEROS_POSITIVOS
        if importe < 0:
            return MENSAJE_SOLO_NUMEROS_POSITIVOS
        if importe < minimo:
            return f"No puede ser menor que {minimo}"
        return None

    return validar


def _validador_telefono(obligatorio: bool) -> Validador:
    """
    Construye el validador de un número de teléfono.

    Admite dígitos y el guion como separador, que es como se anotan los
    teléfonos en el local. Rechaza el resto —letras, espacios, paréntesis, el
    signo «+»— porque el teléfono se guarda tal como se escribe: si cada quien
    lo anota a su manera, después nadie puede buscarlo de forma fiable.

    Args:
        obligatorio: Si el campo no puede quedar vacío.

    Returns:
        Validador listo para pasar a un campo.
    """

    def validar(valor: str) -> str | None:
        """
        Comprueba que el texto sean solo dígitos y de un largo razonable.

        Args:
            valor: Texto escrito en el campo.

        Returns:
            El mensaje de error, o None si el teléfono es aceptable.
        """
        texto = (valor or "").strip()
        if not texto:
            return "Este campo es obligatorio" if obligatorio else None
        if not PATRON_TELEFONO.match(texto):
            return MENSAJE_TELEFONO

        # Los guiones separan, no cuentan como parte del número.
        digitos = texto.replace("-", "")
        if len(digitos) < LONGITUD_MINIMA_TELEFONO:
            return f"El teléfono debe tener al menos {LONGITUD_MINIMA_TELEFONO} dígitos"
        if len(digitos) > LONGITUD_MAXIMA_TELEFONO:
            return f"El teléfono no puede pasar de {LONGITUD_MAXIMA_TELEFONO} dígitos"
        return None

    return validar


def _validador_entero(obligatorio: bool, minimo: int) -> Validador:
    """
    Construye el validador de una cantidad entera.

    Args:
        obligatorio: Si el campo no puede quedar vacío.
        minimo: Cantidad mínima aceptada.

    Returns:
        Validador listo para pasar a un campo.
    """

    def validar(valor: str) -> str | None:
        """
        Comprueba que el texto sea un entero y no baje del mínimo.

        Args:
            valor: Texto escrito en el campo.

        Returns:
            El mensaje de error, o None si la cantidad es aceptable.
        """
        texto = (valor or "").strip()
        if not texto:
            return "Este campo es obligatorio" if obligatorio else None
        if not texto.lstrip("-").isdigit():
            return "Debe ser un número entero"
        if int(texto) < minimo:
            return f"No puede ser menor que {minimo}"
        return None

    return validar


def _validador_fecha(obligatorio: bool) -> Validador:
    """
    Construye el validador de una fecha AAAA-MM-DD.

    Args:
        obligatorio: Si el campo no puede quedar vacío.

    Returns:
        Validador listo para pasar a un campo.
    """

    def validar(valor: str) -> str | None:
        """
        Comprueba que el texto tenga el formato AAAA-MM-DD.

        Args:
            valor: Texto escrito en el campo.

        Returns:
            El mensaje de error, o None si la fecha está bien escrita.
        """
        texto = (valor or "").strip()
        if not texto:
            return "Este campo es obligatorio" if obligatorio else None
        if not PATRON_FECHA.match(texto):
            return "Use el formato AAAA-MM-DD"
        return None

    return validar


# ── Apoyo interno ───────────────────────────────────────────────────────


def encadenar_al_cambiar(campo: ft.TextField, manejador: Callable) -> None:
    """
    Añade un manejador al evento de cambio sin descartar el que ya tenía.

    Asignar ``campo.on_change`` directamente **reemplaza** lo que hubiera, y
    los campos con validación traen ahí su comprobación. Así se perdía: el
    campo de efectivo del punto de venta tenía validador, pero la pantalla lo
    sobreescribía al conectar el cálculo del cambio, de modo que nunca llegaba
    a avisar de nada.

    Args:
        campo: Campo al que añadir el manejador.
        manejador: Función a ejecutar además de lo que ya hubiera.
    """
    anterior = campo.on_change

    def ambos(evento: ft.ControlEvent) -> None:
        """
        Ejecuta primero lo que ya estaba y después lo nuevo.

        Args:
            evento: Evento de cambio que entrega Flet.
        """
        if anterior is not None:
            anterior(evento)
        manejador(evento)

    campo.on_change = ambos


def _rotulo(etiqueta: str, obligatorio: bool) -> str:
    """
    Compone el rótulo del campo, marcando los obligatorios con un asterisco.

    Args:
        etiqueta: Texto base del rótulo.
        obligatorio: Si el campo es obligatorio.

    Returns:
        El rótulo final.
    """
    return f"{etiqueta} *" if obligatorio else etiqueta


def _conectar_validador(campo: ft.TextField, validador: Validador) -> None:
    """
    Hace que el campo se valide solo mientras el usuario escribe.

    Args:
        campo: Campo al que conectar la validación.
        validador: Comprobación a aplicar.
    """

    def al_escribir(evento: ft.ControlEvent) -> None:
        """
        Valida el campo en cada pulsación y muestra el error en el propio control.

        Args:
            evento: Evento de cambio que entrega Flet.
        """
        control = evento.control
        control.error = validador(control.value or "")
        refrescar(control)

    campo.on_change = al_escribir

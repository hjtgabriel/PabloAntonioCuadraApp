"""
Lectura de registros para la interfaz.

Los servicios devuelven a veces diccionarios y a veces objetos de dominio. Las
pantallas no deberían tener que saber cuál de los dos reciben, así que toda la
lectura de campos pasa por aquí.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


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


def lector(registro: Any | None) -> Callable[..., Any]:
    """
    Construye el lector con el que un formulario se precarga.

    Evita repetir ``leer_valor(registro, clave, "") if registro else ""`` en
    cada campo de cada pantalla: en un alta ``registro`` es ``None`` y el lector
    devuelve siempre el valor predeterminado.

    Args:
        registro: Registro que se está editando, o None si es un alta.

    Returns:
        Función ``(clave, por_omision="")`` con el valor a mostrar en el campo.
    """

    def leer(clave: str, por_omision: Any = "") -> Any:
        """
        Da el valor con el que precargar un campo.

        Args:
            clave: Nombre del campo a leer.
            por_omision: Valor a usar en un alta, o si lo guardado es nulo.

        Returns:
            El valor guardado, o ``por_omision``.
        """
        if registro is None:
            return por_omision
        valor = leer_valor(registro, clave, por_omision)
        return por_omision if valor is None else valor

    return leer


def lector_de_texto(registro: Any | None) -> Callable[[str], str]:
    """
    Igual que :func:`lector`, pero garantizando texto.

    Los campos de texto de Flet no admiten ``None`` como valor, y un teléfono o
    una dirección vacíos llegan como ``None`` desde la base de datos.

    Args:
        registro: Registro que se está editando, o None si es un alta.

    Returns:
        Función ``(clave)`` con el valor del campo convertido a texto.
    """
    leer = lector(registro)

    def leer_texto(clave: str) -> str:
        """
        Da el valor de un campo convertido a texto.

        Args:
            clave: Nombre del campo a leer.

        Returns:
            El valor guardado como cadena, o vacío si no hay nada.
        """
        return str(leer(clave, ""))

    return leer_texto

"""
Reglas de formato compartidas por la interfaz y los servicios.

El teléfono se valida en dos sitios y por motivos distintos: la pantalla avisa
mientras se escribe, para que el usuario corrija en el momento; el servicio
rechaza al guardar, porque una regla que solo vive en la interfaz no protege
nada. Basta con llamar al servicio desde otro sitio —un script, una pantalla
nueva, una importación de datos— para saltársela.

La regla se escribe aquí una sola vez para que las dos comprobaciones no puedan
discrepar: sería peor tener una pantalla que avisa de algo que el servicio
acepta, o al revés.
"""

from __future__ import annotations

import re

PATRON_TELEFONO = re.compile(r"^\d+(-\d+)*$")
"""
Dígitos, opcionalmente separados por guiones simples.

El guion se admite porque es como se anotan los teléfonos en el local
(«8676-7203»). No se admite ninguna otra cosa —espacios, paréntesis, el signo
«+»— porque varios separadores harían que el mismo número quedara guardado de
formas distintas según quién lo escriba, y después nadie podría buscarlo.
"""

DIGITOS_TELEFONO = 8
"""Cifras que tiene un teléfono en Nicaragua, sin el código de país."""

MENSAJE_TELEFONO_FORMATO = "Solo números y guiones, sin letras ni símbolos"
MENSAJE_TELEFONO_LARGO = f"El teléfono debe tener {DIGITOS_TELEFONO} dígitos"


def revisar_telefono(valor: str | None, obligatorio: bool = False) -> str | None:
    """
    Comprueba un número de teléfono y explica qué está mal.

    Devuelve el mensaje en lugar de lanzar una excepción para que sirva a las
    dos capas: la pantalla lo muestra bajo el campo mientras se escribe, y el
    servicio lo convierte en el error que corresponda al guardar.

    Args:
        valor: Texto escrito, tal como lo teclea el usuario.
        obligatorio: Si el campo no puede quedar vacío.

    Returns:
        El mensaje de error, o None si el teléfono es aceptable.
    """
    texto = (valor or "").strip()
    if not texto:
        return "Este campo es obligatorio" if obligatorio else None
    if not PATRON_TELEFONO.match(texto):
        return MENSAJE_TELEFONO_FORMATO
    if len(solo_digitos(texto)) != DIGITOS_TELEFONO:
        return MENSAJE_TELEFONO_LARGO
    return None


def solo_digitos(telefono: str) -> str:
    """
    Quita los separadores de un teléfono y deja las cifras.

    Args:
        telefono: Teléfono tal como se escribió.

    Returns:
        Solo sus dígitos; los guiones separan, pero no son parte del número.
    """
    return telefono.replace("-", "")

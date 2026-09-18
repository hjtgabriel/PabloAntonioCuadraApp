"""
Formato de importes y fechas para toda la aplicación.

Estaba repetido en siete sitios con tres nombres distintos para lo mismo
(``_formato_importe``, ``_moneda``, ``_importe``), y la constante de la moneda
declarada en cuatro archivos. La moneda y el formato de fecha son decisiones
del negocio, no de cada pantalla: cambiar de córdobas a dólares tenía que
poderse hacer en un solo sitio.

La conversión a ``Decimal`` vive aquí por el mismo motivo: estaba copiada tal
cual en tres repositorios.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation

MONEDA = "C$"
"""Símbolo de la moneda del local."""

FORMATO_FECHA = "%Y-%m-%d %H:%M"
"""Formato de fecha y hora para las tablas de la aplicación."""

FORMATO_FECHA_LARGA = "%d/%m/%Y %H:%M"
"""Formato de fecha para los documentos que se entregan al cliente."""

SIN_DATO = "—"
"""Lo que se muestra donde la base de datos no tiene valor."""


def a_decimal(valor: object) -> Decimal:
    """
    Convierte a ``Decimal`` un valor monetario leído de la base de datos.

    Pasa siempre por ``str`` para no heredar el error de redondeo que tendría
    un ``float`` intermedio: los drivers devuelven los NUMERIC de formas
    distintas según el motor.

    Args:
        valor: Valor tal como lo devolvió el driver.

    Returns:
        El importe como ``Decimal``; cero si el valor era nulo o ilegible.
    """
    if valor is None:
        return Decimal("0")
    if isinstance(valor, Decimal):
        return valor
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def importe(valor: object) -> str:
    """
    Da formato de moneda a un valor.

    Args:
        valor: Importe a mostrar; None se trata como cero.

    Returns:
        El importe con el símbolo de la moneda y dos decimales.
    """
    return f"{MONEDA} {a_decimal(valor):,.2f}"


def fecha(valor: object, patron: str = FORMATO_FECHA) -> str:
    """
    Da formato legible a una marca de tiempo.

    Acepta tanto ``datetime`` como texto porque no todos los motores devuelven
    lo mismo: psycopg2 entrega ``datetime`` y SQLite la cadena que guardó.

    Args:
        valor: Fecha tal como llegó de la base de datos.
        patron: Formato a aplicar cuando el valor sí es una fecha.

    Returns:
        La fecha formateada, o un guion si no hay dato.
    """
    if valor is None:
        return SIN_DATO
    if isinstance(valor, datetime):
        return valor.strftime(patron)
    return str(valor)[: len("AAAA-MM-DD HH:MM")]


def o_guion(valor: object) -> str:
    """
    Muestra un valor o un guion si está vacío.

    Args:
        valor: Valor a mostrar.

    Returns:
        El valor como texto, o un guion si era nulo o vacío.
    """
    return str(valor) if valor not in (None, "") else SIN_DATO

"""Entidades del módulo de inventario."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class TipoMovimiento(StrEnum):
    """
    Clases de movimiento que puede sufrir el stock (RF05).

    Es un ``StrEnum`` para que el valor viaje tal cual a la base de datos y los
    registros históricos sigan siendo legibles.
    """

    ENTRADA = "Entrada"
    SALIDA = "Salida"
    VENTA = "Venta"
    AJUSTE = "Ajuste"

    @classmethod
    def desde_texto(cls, valor: str) -> TipoMovimiento:
        """
        Convierte el texto elegido en la interfaz al tipo correspondiente.

        Args:
            valor: Texto del movimiento, sin distinguir mayúsculas.

        Returns:
            El tipo de movimiento.

        Raises:
            ValueError: Si el texto no corresponde a ningún tipo conocido.
        """
        objetivo = (valor or "").strip().lower()
        for tipo in cls:
            if tipo.value.lower() == objetivo:
                return tipo
        validos = ", ".join(tipo.value for tipo in cls)
        raise ValueError(f"Tipo de movimiento inválido: {valor!r}. Use uno de: {validos}")

    @property
    def suma_stock(self) -> bool:
        """True si el movimiento incrementa las existencias."""
        return self is TipoMovimiento.ENTRADA


@dataclass(slots=True)
class Movimiento:
    """
    Entrada, salida o ajuste registrado sobre el stock de un producto (RF05).

    Attributes:
        idinventario: Clave primaria del movimiento.
        idproducto: Producto afectado.
        fechamovimiento: Momento en que se registró.
        tipomovimiento: Clase de movimiento.
        cantidad: Unidades involucradas, siempre en positivo.
        descripcion: Nombre del producto, solo lectura desde un JOIN.
    """

    idinventario: int
    idproducto: int
    fechamovimiento: datetime
    tipomovimiento: str
    cantidad: int
    descripcion: str | None = None

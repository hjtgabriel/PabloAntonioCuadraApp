"""Entidad de dominio del módulo de proveedores."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Proveedor:
    """
    Proveedor que surte productos a la librería.

    Attributes:
        idproveedor: Clave primaria; vale 0 mientras no se haya guardado.
        nombreproveedor: Razón social o nombre comercial.
        telefono: Teléfono de contacto, opcional.
        direccion: Dirección física, opcional.
    """

    idproveedor: int
    nombreproveedor: str
    telefono: str | None = None
    direccion: str | None = None

"""
Jerarquía de errores propios de la aplicación.

Se define aquí, en un módulo sin dependencias, para que ninguna capa tenga que
importar excepciones del driver de base de datos. Las capas superiores
(servicios y vistas) capturan únicamente estos tipos.

Importante: estos nombres NO deben coincidir con los de psycopg2. El proyecto
anterior declaraba su propia clase ``DatabaseError`` que sombreaba la del
driver, de modo que los ``except DatabaseError`` jamás capturaban un error real
de la base de datos.
"""

from __future__ import annotations


class ErrorAplicacion(Exception):
    """Raíz de todos los errores controlados de la aplicación."""


# ── Errores de infraestructura ──────────────────────────────────────────

class ErrorBaseDatos(ErrorAplicacion):
    """Fallo al hablar con la base de datos."""


class ErrorConexion(ErrorBaseDatos):
    """No se pudo obtener o abrir una conexión."""


class ErrorTransaccion(ErrorBaseDatos):
    """La transacción no pudo confirmarse y se revirtió."""


class ErrorIntegridad(ErrorBaseDatos):
    """Se violó una restricción de la base de datos (clave foránea, único, etc.)."""


# ── Errores de dominio ──────────────────────────────────────────────────

class ErrorValidacion(ErrorAplicacion):
    """Los datos suministrados no cumplen una regla de negocio."""


class ErrorNoEncontrado(ErrorAplicacion):
    """El registro solicitado no existe."""


class ErrorDuplicado(ErrorValidacion):
    """Ya existe un registro con ese valor único."""


class ErrorEnUso(ErrorValidacion):
    """No se puede eliminar porque otros registros dependen de este."""


class ErrorStockInsuficiente(ErrorValidacion):
    """La operación dejaría el stock en negativo."""


class ErrorAutenticacion(ErrorAplicacion):
    """Las credenciales son inválidas."""


class ErrorPermisos(ErrorAplicacion):
    """El rol del usuario no autoriza esta operación (RF02)."""


class ErrorRespaldo(ErrorAplicacion):
    """El respaldo no pudo generarse o copiarse (RNF05)."""

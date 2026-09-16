"""
Repositorios de los catálogos simples: rol, categoría y marca.

Las tres tablas tienen la misma forma —una clave y un nombre— así que heredan
todo su comportamiento de :class:`~nucleo.repositorio.RepositorioCatalogo` y
solo declaran a qué tabla y columnas apuntan.
"""

from __future__ import annotations

from nucleo.repositorio import RepositorioCatalogo


class RolRepositorio(RepositorioCatalogo):
    """Acceso a la tabla «rol» (RF02)."""

    tabla = "rol"
    clave = "idrol"
    columna_nombre = "nombrerol"


class CategoriaRepositorio(RepositorioCatalogo):
    """Acceso a la tabla «categoria» (RF03)."""

    tabla = "categoria"
    clave = "idcategoria"
    columna_nombre = "nombre"


class MarcaRepositorio(RepositorioCatalogo):
    """Acceso a la tabla «marca» (RF03)."""

    tabla = "marca"
    clave = "idmarca"
    columna_nombre = "nombremarca"

"""
Servicios de los catálogos: rol, categoría y marca.

Cada servicio es una instancia de :class:`~nucleo.servicio.ServicioCatalogo`
configurada con su repositorio, su etiqueta y las tablas que dependen de él.
Toda la lógica —validar, comprobar duplicados, impedir el borrado en uso— vive
una sola vez en el núcleo.
"""

from __future__ import annotations

from modulos.catalogos.repositorio import (
    CategoriaRepositorio,
    MarcaRepositorio,
    RolRepositorio,
)
from nucleo.base_datos import Conexion
from nucleo.servicio import Dependencia, ServicioCatalogo

PRODUCTOS_DEPENDEN = "productos"
USUARIOS_DEPENDEN = "usuarios"


def servicio_roles(conexion: Conexion | None = None) -> ServicioCatalogo:
    """
    Construye el servicio de roles.

    Args:
        conexion: Conexión de una transacción en curso, si la hay.

    Returns:
        Servicio listo para operar sobre la tabla «rol».
    """
    return ServicioCatalogo(
        repositorio=RolRepositorio(conexion),
        etiqueta="el rol",
        dependencias=(Dependencia("usuario", "idrol", USUARIOS_DEPENDEN),),
    )


def servicio_categorias(conexion: Conexion | None = None) -> ServicioCatalogo:
    """
    Construye el servicio de categorías.

    Args:
        conexion: Conexión de una transacción en curso, si la hay.

    Returns:
        Servicio listo para operar sobre la tabla «categoria».
    """
    return ServicioCatalogo(
        repositorio=CategoriaRepositorio(conexion),
        etiqueta="la categoría",
        dependencias=(Dependencia("producto", "idcategoria", PRODUCTOS_DEPENDEN),),
    )


def servicio_marcas(conexion: Conexion | None = None) -> ServicioCatalogo:
    """
    Construye el servicio de marcas.

    Args:
        conexion: Conexión de una transacción en curso, si la hay.

    Returns:
        Servicio listo para operar sobre la tabla «marca».
    """
    return ServicioCatalogo(
        repositorio=MarcaRepositorio(conexion),
        etiqueta="la marca",
        dependencias=(Dependencia("producto", "idmarca", PRODUCTOS_DEPENDEN),),
    )

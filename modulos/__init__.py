"""
Módulos de negocio del monolito.

Cada módulo cubre una capacidad del sistema y se organiza en tres archivos:

* ``modelos.py`` – entidades de dominio.
* ``repositorio.py`` – acceso a datos; el único que escribe SQL.
* ``servicios.py`` – reglas de negocio y coordinación de transacciones.

Los catálogos simples (rol, categoría, marca) no necesitan ``modelos.py``
porque heredan todo su comportamiento del núcleo.

Módulos disponibles: :mod:`~modulos.auth`, :mod:`~modulos.catalogos`,
:mod:`~modulos.personal`, :mod:`~modulos.proveedores`, :mod:`~modulos.productos`,
:mod:`~modulos.inventario`, :mod:`~modulos.ventas` y :mod:`~modulos.reportes`.
"""

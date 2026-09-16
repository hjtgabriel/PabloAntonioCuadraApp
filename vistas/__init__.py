"""
Capa de presentación.

Cada pantalla es una función ``pantalla_*`` que devuelve un control de Flet. Las
pantallas hablan únicamente con la capa de servicios: ninguna importa un
repositorio ni escribe SQL.

Las pantallas de mantenimiento (catálogos, proveedores, personal, productos) no
tienen código propio de listado, alta, edición ni borrado: todo eso vive una
sola vez en :mod:`vistas.crud`.
"""

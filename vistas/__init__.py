"""
Capa de presentación.

Cada pantalla es una función ``pantalla_*`` que devuelve un control de Flet. Las
pantallas hablan únicamente con la capa de servicios: ninguna importa un
repositorio ni escribe SQL.

Las pantallas de mantenimiento (catálogos, proveedores, personal, productos) no
tienen código propio de listado, alta, edición ni borrado: todo eso vive una
sola vez en :mod:`vistas.crud`.

Los formularios se declaran con
:func:`~vistas.componentes.dialogos.definir_campo`, que arma cada campo a partir
de su clave, su rótulo y la fábrica de control correspondiente. Así el rótulo y
el carácter obligatorio se escriben una sola vez, en lugar de repetirse para el
control y para la validación.
"""

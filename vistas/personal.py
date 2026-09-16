"""
Pantallas de empleados y de usuarios (RF01, RF02).

Ambas se arman sobre la misma pantalla CRUD genérica. La de usuarios añade el
campo de contraseña, que al editar se deja en blanco para conservar la actual:
así nunca hace falta mostrar ni volver a escribir la contraseña existente.
"""

from __future__ import annotations

import flet as ft

from modulos.catalogos.servicios import servicio_roles
from modulos.personal.servicios import ServicioEmpleados, ServicioUsuarios
from vistas.componentes.campos import (
    campo_contrasena,
    campo_seleccion,
    longitud_minima,
)
from vistas.componentes.dialogos import Campo, definir_campo
from vistas.componentes.registros import lector, lector_de_texto
from vistas.componentes.tablas import Columna
from vistas.crud import ConfiguracionCrud, construir_pantalla_crud

LONGITUD_MINIMA_NOMBRE = 2
LONGITUD_MINIMA_USUARIO = 3
AYUDA_CONTRASENA_EDICION = "Déjelo en blanco para conservar la contraseña actual"


def _campos_persona(registro: object | None) -> list[Campo]:
    """
    Arma los campos de datos personales, comunes a empleados y usuarios.

    Args:
        registro: Registro a editar, o None si es un alta.

    Returns:
        Campos de nombres, apellidos, dirección y teléfono.
    """
    valor = lector_de_texto(registro)
    return [
        definir_campo(
            "nombres",
            "Nombres",
            obligatorio=True,
            valor=valor("nombres"),
            icono=ft.Icons.PERSON,
            validador=longitud_minima(LONGITUD_MINIMA_NOMBRE, "Los nombres"),
        ),
        definir_campo(
            "apellidos",
            "Apellidos",
            obligatorio=True,
            valor=valor("apellidos"),
            icono=ft.Icons.PERSON_OUTLINE,
            validador=longitud_minima(LONGITUD_MINIMA_NOMBRE, "Los apellidos"),
        ),
        definir_campo(
            "direccion", "Dirección", valor=valor("direccion"), icono=ft.Icons.LOCATION_ON
        ),
        definir_campo("telefono", "Teléfono", valor=valor("telefono"), icono=ft.Icons.PHONE),
    ]


def _campos_usuario(registro: object | None) -> list[Campo]:
    """
    Arma el formulario de usuario, precargado si se está editando.

    A los datos personales les añade la credencial. Al editar, la contraseña
    deja de ser obligatoria: en blanco significa conservar la actual, de modo
    que nunca hace falta mostrar ni volver a escribir la que ya existe.

    Args:
        registro: Usuario a editar, o None si es un alta.

    Returns:
        Los campos del formulario, en orden de aparición.
    """
    editando = registro is not None
    valor = lector(registro)
    return [
        *_campos_persona(registro),
        definir_campo(
            "nombreusuario",
            "Nombre de usuario",
            obligatorio=True,
            valor=str(valor("nombreusuario")),
            icono=ft.Icons.ACCOUNT_CIRCLE,
            validador=longitud_minima(LONGITUD_MINIMA_USUARIO, "El nombre de usuario"),
        ),
        definir_campo(
            "contrasena",
            "Contraseña",
            campo_contrasena,
            obligatorio=not editando,
            ayuda=AYUDA_CONTRASENA_EDICION if editando else None,
        ),
        definir_campo(
            "idrol",
            "Rol",
            campo_seleccion,
            obligatorio=True,
            opciones=_opciones_rol(),
            valor=valor("idrol", None),
        ),
    ]


def pantalla_empleados(pagina: ft.Page) -> ft.Control:
    """
    Arma la pantalla de empleados.

    Args:
        pagina: Página de Flet sobre la que se dibuja.

    Returns:
        El control raíz de la pantalla.
    """
    servicio = ServicioEmpleados()

    return construir_pantalla_crud(
        pagina,
        ConfiguracionCrud(
            titulo="Empleados",
            entidad="el empleado",
            clave_id="idempleado",
            columnas=[
                Columna("idempleado", "ID", numerica=True),
                Columna("nombres", "Nombres"),
                Columna("apellidos", "Apellidos"),
                Columna("telefono", "Teléfono", formato=lambda valor: valor or "—"),
                Columna("nombreusuario", "Usuario", formato=_formato_usuario),
                Columna("nombrerol", "Rol", formato=lambda valor: valor or "—"),
            ],
            construir_campos=_campos_persona,
            listar=servicio.listar,
            crear=servicio.crear,
            actualizar=servicio.actualizar,
            eliminar=servicio.eliminar,
            marcador_busqueda="Buscar empleado…",
            mensaje_vacio="Aún no hay empleados registrados",
            texto_confirmar_borrado=(
                "¿Desea eliminar este empleado? Si tiene usuario, también se eliminará."
            ),
        ),
    )


def pantalla_usuarios(pagina: ft.Page) -> ft.Control:
    """
    Arma la pantalla de usuarios del sistema (RF01, RF02).

    Args:
        pagina: Página de Flet sobre la que se dibuja.

    Returns:
        El control raíz de la pantalla.
    """
    servicio = ServicioUsuarios()

    return construir_pantalla_crud(
        pagina,
        ConfiguracionCrud(
            titulo="Usuarios del sistema",
            entidad="el usuario",
            clave_id="idusuario",
            columnas=[
                Columna("idusuario", "ID", numerica=True),
                Columna("nombreusuario", "Usuario"),
                Columna("nombres", "Nombres", formato=lambda valor: valor or "—"),
                Columna("apellidos", "Apellidos", formato=lambda valor: valor or "—"),
                Columna("rol", "Rol"),
            ],
            construir_campos=_campos_usuario,
            listar=servicio.listar,
            crear=servicio.crear_con_empleado,
            actualizar=servicio.actualizar,
            eliminar=servicio.eliminar,
            marcador_busqueda="Buscar usuario…",
            mensaje_vacio="Aún no hay usuarios registrados",
            texto_confirmar_borrado=(
                "¿Desea eliminar este usuario? También se eliminará su empleado asociado."
            ),
        ),
    )


def _opciones_rol() -> list[tuple[object, str]]:
    """
    Trae los roles disponibles para el desplegable.

    Returns:
        Pares (clave del rol, nombre del rol).
    """
    return [(fila["idrol"], fila["nombrerol"]) for fila in servicio_roles().listar()]


def _formato_usuario(valor: object) -> str:
    """
    Formatea la columna de usuario en el listado de empleados.

    Args:
        valor: Nombre de usuario, o None si el empleado no tiene credencial.

    Returns:
        El nombre de usuario, o un aviso de que no tiene.
    """
    return str(valor) if valor else "Sin usuario"

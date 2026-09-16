"""
Creación del primer usuario administrador.

Se ejecuta una sola vez, después de cargar el esquema en la base de datos:

    python -m herramientas.crear_admin

Pide los datos por consola y guarda la contraseña ya cifrada (RNF04). Existe
porque, si no, no habría forma de entrar al sistema la primera vez sin escribir
un hash a mano en la base de datos.
"""

from __future__ import annotations

import getpass
import sys

from modulos.catalogos.servicios import servicio_roles
from modulos.personal.repositorio import UsuarioRepositorio
from modulos.personal.servicios import ServicioUsuarios
from nucleo.errores import ErrorAplicacion
from nucleo.registro import configurar_registro
from nucleo.seguridad import LONGITUD_MINIMA

ROL_ADMINISTRADOR = "Administrador"
ROL_VENDEDOR = "Vendedor"


def principal() -> int:
    """
    Crea el usuario administrador inicial.

    Returns:
        0 si todo salió bien, 1 si hubo algún problema.
    """
    configurar_registro()
    print("=" * 62)
    print("  Librería Pablo Antonio Cuadra — Crear usuario administrador")
    print("=" * 62)

    try:
        _asegurar_roles()
        idrol = _obtener_rol_administrador()
    except ErrorAplicacion as error:
        print(f"\n[ERROR] No se pudo preparar los roles: {error}")
        return 1
    except Exception as error:  # noqa: BLE001 - se informa al operador y se sale
        print(f"\n[ERROR] No se pudo conectar con la base de datos: {error}")
        print("Revise el archivo .env y que el esquema esté cargado.")
        return 1

    if _ya_existe_administrador(idrol):
        print("\nYa existe al menos un usuario administrador. No se creará otro.")
        return 0

    datos = _pedir_datos(idrol)
    try:
        idusuario = ServicioUsuarios().crear_con_empleado(datos)
    except ErrorAplicacion as error:
        print(f"\n[ERROR] {error}")
        return 1

    print(f"\n[LISTO] Usuario «{datos['nombreusuario']}» creado con la clave {idusuario}.")
    print("Ya puede iniciar la aplicación con:  python main.py")
    return 0


def _asegurar_roles() -> None:
    """Crea los roles que exige el RF02 si todavía no existen."""
    servicio = servicio_roles()
    existentes = {fila["nombrerol"] for fila in servicio.listar()}
    for nombre in (ROL_ADMINISTRADOR, ROL_VENDEDOR):
        if nombre not in existentes:
            servicio.crear(nombre)
            print(f"  · Rol «{nombre}» creado")


def _obtener_rol_administrador() -> int:
    """
    Busca la clave del rol de administración.

    Returns:
        Clave del rol.

    Raises:
        ErrorAplicacion: Si el rol no existe pese a haberse intentado crear.
    """
    for fila in servicio_roles().listar():
        if fila["nombrerol"] == ROL_ADMINISTRADOR:
            return fila["idrol"]
    raise ErrorAplicacion(f"No se encontró el rol «{ROL_ADMINISTRADOR}»")


def _ya_existe_administrador(idrol: int) -> bool:
    """
    Comprueba si ya hay algún usuario con rol de administración.

    Args:
        idrol: Clave del rol de administración.

    Returns:
        True si ya existe al menos uno.
    """
    return UsuarioRepositorio().contar("idrol = ?", (idrol,)) > 0


def _pedir_datos(idrol: int) -> dict:
    """
    Pide por consola los datos del administrador.

    Args:
        idrol: Clave del rol de administración a asignarle.

    Returns:
        Diccionario con los datos listos para el servicio.
    """
    print("\nComplete los datos del administrador:\n")
    return {
        "nombres": _pedir_texto("Nombres"),
        "apellidos": _pedir_texto("Apellidos"),
        "telefono": input("  Teléfono (opcional): ").strip() or None,
        "direccion": input("  Dirección (opcional): ").strip() or None,
        "nombreusuario": _pedir_texto("Nombre de usuario"),
        "contrasena": _pedir_contrasena(),
        "idrol": idrol,
    }


def _pedir_texto(etiqueta: str) -> str:
    """
    Pide un dato obligatorio hasta que el operador escriba algo.

    Args:
        etiqueta: Rótulo a mostrar.

    Returns:
        El texto escrito, sin espacios sobrantes.
    """
    while True:
        valor = input(f"  {etiqueta}: ").strip()
        if valor:
            return valor
        print("    Este dato es obligatorio.")


def _pedir_contrasena() -> str:
    """
    Pide la contraseña dos veces sin mostrarla en pantalla.

    Returns:
        La contraseña confirmada.
    """
    while True:
        clave = getpass.getpass(f"  Contraseña (mínimo {LONGITUD_MINIMA} caracteres): ")
        if len(clave) < LONGITUD_MINIMA:
            print(f"    Debe tener al menos {LONGITUD_MINIMA} caracteres.")
            continue
        if clave != getpass.getpass("  Repita la contraseña: "):
            print("    Las contraseñas no coinciden.")
            continue
        return clave


if __name__ == "__main__":
    sys.exit(principal())

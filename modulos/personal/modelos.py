"""
Entidades del módulo de personal.

Empleado y usuario van juntos porque en este sistema no existe uno sin el otro:
el usuario es la credencial con la que un empleado entra al sistema (RF01).
Tenerlos en el mismo módulo evita la frontera difusa que antes obligaba a
declarar el repositorio de empleados dos veces.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Empleado:
    """
    Persona que trabaja en la librería.

    Attributes:
        idempleado: Clave primaria; vale 0 mientras no se haya guardado.
        nombres: Nombres de pila.
        apellidos: Apellidos.
        direccion: Dirección domiciliar, opcional.
        telefono: Teléfono de contacto, opcional.
    """

    idempleado: int
    nombres: str
    apellidos: str
    direccion: str | None = None
    telefono: str | None = None

    @property
    def nombre_completo(self) -> str:
        """Nombres y apellidos unidos, para mostrar en listados."""
        return f"{self.nombres} {self.apellidos}".strip()


@dataclass(slots=True)
class Usuario:
    """
    Credencial de acceso de un empleado (RF01, RF02).

    Attributes:
        idusuario: Clave primaria; vale 0 mientras no se haya guardado.
        idempleado: Empleado al que pertenece la credencial.
        idrol: Rol que determina qué módulos puede ver (RF02).
        nombreusuario: Identificador de acceso, único en el sistema.
        contrasena: Hash PBKDF2 de la contraseña; nunca el texto plano (RNF04).
    """

    idusuario: int
    idempleado: int
    idrol: int
    nombreusuario: str
    contrasena: str


@dataclass(slots=True, frozen=True)
class Credencial:
    """
    Hash almacenado junto con los datos de sesión de un usuario.

    Existe para que la autenticación resuelva con una sola consulta lo que
    antes pedía dos, sin meter el hash dentro de
    :class:`UsuarioAutenticado`: ese objeto viaja hasta la interfaz y no debe
    llevar la credencial encima.

    Solo lo usa :mod:`modulos.auth.servicios`, y se descarta en cuanto se
    valida la contraseña.

    Attributes:
        hash_contrasena: Contraseña cifrada tal como está guardada.
        sesion: Datos que la interfaz necesita si la validación sale bien.
    """

    hash_contrasena: str
    sesion: UsuarioAutenticado


@dataclass(slots=True)
class UsuarioAutenticado:
    """
    Datos de sesión que la interfaz necesita tras un inicio de sesión correcto.

    No incluye la contraseña ni su hash: una vez validada la credencial, ese
    dato no vuelve a salir de la capa de datos.

    Attributes:
        idusuario: Clave del usuario que inició sesión.
        nombreusuario: Identificador de acceso.
        idempleado: Empleado asociado.
        nombres: Nombres del empleado.
        apellidos: Apellidos del empleado.
        idrol: Clave del rol.
        rol: Nombre del rol, solo para mostrarlo en la cabecera.
        rol_administra: Si el rol autoriza las secciones de administración
            (RF02). Viene de la base y no se deduce del nombre.
    """

    idusuario: int
    nombreusuario: str
    idempleado: int
    nombres: str
    apellidos: str
    idrol: int
    rol: str
    rol_administra: bool = False

    @property
    def nombre_completo(self) -> str:
        """Nombres y apellidos unidos, para el saludo de bienvenida."""
        return f"{self.nombres} {self.apellidos}".strip() or self.nombreusuario

    @property
    def es_administrador(self) -> bool:
        """
        Indica si el rol autoriza las secciones de administración (RF02).

        Se apoya en la marca «administra» del rol y no en cómo esté escrito su
        nombre. Antes bastaba con que empezara por «admin», de modo que
        renombrar el rol a «Gerencia» dejaba a esa persona sin permisos sin que
        nadie se enterara.
        """
        return self.rol_administra

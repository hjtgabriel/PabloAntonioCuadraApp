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
        rol: Nombre del rol, usado para decidir el menú visible (RF02).
    """

    idusuario: int
    nombreusuario: str
    idempleado: int
    nombres: str
    apellidos: str
    idrol: int
    rol: str

    @property
    def nombre_completo(self) -> str:
        """Nombres y apellidos unidos, para el saludo de bienvenida."""
        return f"{self.nombres} {self.apellidos}".strip() or self.nombreusuario

    @property
    def es_administrador(self) -> bool:
        """
        Indica si el rol tiene privilegios de administración (RF02).

        La comparación ignora mayúsculas y acentos del sufijo para tolerar
        «Administrador» y «Administración» como equivalentes.
        """
        return self.rol.strip().lower().startswith("admin")

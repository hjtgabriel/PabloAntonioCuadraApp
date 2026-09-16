"""Acceso a datos de las tablas «empleado» y «usuario»."""

from __future__ import annotations

from modulos.personal.modelos import Empleado, Usuario, UsuarioAutenticado
from nucleo.base_datos import obtener_motor
from nucleo.repositorio import RepositorioBase

CONSULTA_EMPLEADOS_CON_USUARIO = """
    SELECT e.idempleado, e.nombres, e.apellidos, e.direccion, e.telefono,
           u.idusuario, u.nombreusuario, u.idrol, r.nombrerol
    FROM empleado e
    LEFT JOIN usuario u ON e.idempleado = u.idempleado
    LEFT JOIN rol r ON u.idrol = r.idrol
"""

CONSULTA_USUARIOS_CON_DETALLE = """
    SELECT u.idusuario, u.nombreusuario, u.idrol, r.nombrerol AS rol,
           e.idempleado, e.nombres, e.apellidos, e.direccion, e.telefono
    FROM usuario u
    JOIN empleado e ON u.idempleado = e.idempleado
    JOIN rol r ON u.idrol = r.idrol
"""


class EmpleadoRepositorio(RepositorioBase[Empleado]):
    """Operaciones sobre la tabla «empleado»."""

    tabla = "empleado"
    clave = "idempleado"
    columnas = ("nombres", "apellidos", "direccion", "telefono")

    def _a_entidad(self, fila: dict) -> Empleado:
        """Convierte una fila de «empleado» en entidad de dominio."""
        return Empleado(
            idempleado=fila["idempleado"],
            nombres=fila["nombres"],
            apellidos=fila["apellidos"],
            direccion=fila.get("direccion"),
            telefono=fila.get("telefono"),
        )

    def _a_fila(self, entidad: Empleado) -> dict:
        """Convierte la entidad en el diccionario a persistir."""
        return {
            "nombres": entidad.nombres,
            "apellidos": entidad.apellidos,
            "direccion": entidad.direccion,
            "telefono": entidad.telefono,
        }

    def buscar(self, texto: str | None = None) -> list[dict]:
        """
        Lista empleados junto con su usuario y rol, si los tienen (RF08).

        Args:
            texto: Término de búsqueda parcial sobre nombres, apellidos o teléfono.

        Returns:
            Filas con datos de empleado, usuario y rol.
        """
        sql = CONSULTA_EMPLEADOS_CON_USUARIO
        parametros: tuple = ()

        if texto and texto.strip():
            dialecto = obtener_motor().dialecto
            patron = f"%{texto.strip()}%"
            sql += (
                f" WHERE {dialecto.comparar_texto('e.nombres')}"
                f" OR {dialecto.comparar_texto('e.apellidos')}"
                f" OR {dialecto.comparar_texto('e.telefono')}"
            )
            parametros = (patron, patron, patron)

        sql += " ORDER BY e.nombres, e.apellidos"
        return self.consultar(sql, parametros)

    def listar_sin_usuario(self) -> list[Empleado]:
        """
        Devuelve los empleados que todavía no tienen credencial de acceso.

        Returns:
            Empleados sin usuario asociado, ordenados por nombre.
        """
        filas = self.consultar(
            """
            SELECT e.idempleado, e.nombres, e.apellidos, e.direccion, e.telefono
            FROM empleado e
            LEFT JOIN usuario u ON e.idempleado = u.idempleado
            WHERE u.idempleado IS NULL
            ORDER BY e.nombres, e.apellidos
            """
        )
        return [self._a_entidad(fila) for fila in filas]

    def obtener_idusuario(self, idempleado: int) -> int | None:
        """
        Devuelve la clave del usuario de un empleado, si tiene.

        Args:
            idempleado: Clave del empleado.

        Returns:
            La clave del usuario, o None si el empleado no tiene credencial.
        """
        fila = self.consultar_uno(
            "SELECT idusuario FROM usuario WHERE idempleado = ?", (idempleado,)
        )
        return fila["idusuario"] if fila else None


class UsuarioRepositorio(RepositorioBase[Usuario]):
    """Operaciones sobre la tabla «usuario»."""

    tabla = "usuario"
    clave = "idusuario"
    columnas = ("idempleado", "idrol", "nombreusuario", "contrasena")

    def _a_entidad(self, fila: dict) -> Usuario:
        """Convierte una fila de «usuario» en entidad de dominio."""
        return Usuario(
            idusuario=fila["idusuario"],
            idempleado=fila["idempleado"],
            idrol=fila["idrol"],
            nombreusuario=fila["nombreusuario"],
            contrasena=fila["contrasena"],
        )

    def _a_fila(self, entidad: Usuario) -> dict:
        """
        Convierte la entidad en el diccionario a persistir.

        La contraseña se guarda tal cual llega: el cifrado es responsabilidad
        del servicio, que es quien conoce la regla de negocio (RNF04).
        """
        return {
            "idempleado": entidad.idempleado,
            "idrol": entidad.idrol,
            "nombreusuario": entidad.nombreusuario,
            "contrasena": entidad.contrasena,
        }

    def buscar_por_nombre(self, nombreusuario: str) -> Usuario | None:
        """
        Recupera un usuario por su identificador de acceso.

        Args:
            nombreusuario: Identificador de acceso exacto.

        Returns:
            El usuario, o None si no existe.
        """
        fila = self.consultar_uno(
            f"SELECT {self._lista_columnas()} FROM usuario WHERE nombreusuario = ?",
            (nombreusuario.strip(),),
        )
        return self._a_entidad(fila) if fila else None

    def existe_nombre_usuario(self, nombreusuario: str, excluir_id: int | None = None) -> bool:
        """
        Indica si el identificador de acceso ya está tomado.

        Args:
            nombreusuario: Identificador a verificar.
            excluir_id: Clave a ignorar, para no chocar consigo misma al editar.

        Returns:
            True si otro usuario ya lo usa.
        """
        condicion = obtener_motor().dialecto.comparar_texto("nombreusuario")
        parametros: list[object] = [nombreusuario.strip()]
        if excluir_id is not None:
            condicion += " AND idusuario <> ?"
            parametros.append(excluir_id)
        return self.contar(condicion, parametros) > 0

    def listar_con_detalle(self, texto: str | None = None) -> list[dict]:
        """
        Lista usuarios con los datos de su empleado y su rol (RF08).

        Nunca incluye la columna de contraseña.

        Args:
            texto: Término de búsqueda parcial sobre usuario, nombres o apellidos.

        Returns:
            Filas listas para mostrar en la tabla de usuarios.
        """
        sql = CONSULTA_USUARIOS_CON_DETALLE
        parametros: tuple = ()

        if texto and texto.strip():
            dialecto = obtener_motor().dialecto
            patron = f"%{texto.strip()}%"
            sql += (
                f" WHERE {dialecto.comparar_texto('u.nombreusuario')}"
                f" OR {dialecto.comparar_texto('e.nombres')}"
                f" OR {dialecto.comparar_texto('e.apellidos')}"
            )
            parametros = (patron, patron, patron)

        sql += " ORDER BY u.idusuario"
        return self.consultar(sql, parametros)

    def obtener_autenticado(self, nombreusuario: str) -> UsuarioAutenticado | None:
        """
        Arma los datos de sesión de un usuario ya validado.

        Args:
            nombreusuario: Identificador de acceso.

        Returns:
            Los datos de sesión, o None si el usuario no existe.
        """
        fila = self.consultar_uno(
            CONSULTA_USUARIOS_CON_DETALLE + " WHERE u.nombreusuario = ?",
            (nombreusuario.strip(),),
        )
        if not fila:
            return None
        return UsuarioAutenticado(
            idusuario=fila["idusuario"],
            nombreusuario=fila["nombreusuario"],
            idempleado=fila["idempleado"],
            nombres=fila["nombres"] or "",
            apellidos=fila["apellidos"] or "",
            idrol=fila["idrol"],
            rol=fila["rol"] or "",
        )

"""
Reglas de negocio de empleados y usuarios.

Las operaciones que tocan las dos tablas a la vez (alta de empleado con
credencial, baja de usuario con su empleado) corren dentro de una sola
transacción, de modo que nunca quede un empleado a medio crear.
"""

from __future__ import annotations

from modulos.personal.modelos import Empleado, Usuario
from modulos.personal.repositorio import EmpleadoRepositorio, UsuarioRepositorio
from nucleo.base_datos import Conexion, transaccion
from nucleo.errores import (
    ErrorDuplicado,
    ErrorEnUso,
    ErrorNoEncontrado,
    ErrorValidacion,
)
from nucleo.seguridad import cifrar_contrasena, validar_fortaleza
from nucleo.validacion import revisar_telefono

LONGITUD_MINIMA_NOMBRE = 2
LONGITUD_MINIMA_USUARIO = 3


class ServicioEmpleados:
    """Alta, baja, modificación y consulta de empleados."""

    def __init__(self, conexion: Conexion | None = None) -> None:
        """
        Args:
            conexion: Conexión de una transacción en curso, si la hay.
        """
        self._conexion = conexion
        self._repositorio = EmpleadoRepositorio(conexion)

    def listar(self, texto: str | None = None) -> list[dict]:
        """
        Lista empleados con su usuario y rol (RF08).

        Args:
            texto: Término de búsqueda parcial.

        Returns:
            Filas listas para mostrar en la tabla de empleados.
        """
        return self._repositorio.buscar(texto)

    def listar_sin_usuario(self) -> list[Empleado]:
        """Devuelve los empleados que aún no tienen credencial de acceso."""
        return self._repositorio.listar_sin_usuario()

    def crear(self, datos: dict) -> int:
        """
        Da de alta un empleado sin credencial de acceso.

        Args:
            datos: Diccionario con «nombres», «apellidos» y opcionalmente
                «direccion» y «telefono».

        Returns:
            Clave primaria generada.

        Raises:
            ErrorValidacion: Si faltan nombres o apellidos.
        """
        return self._repositorio.insertar(self._construir_empleado(0, datos))

    def actualizar(self, idempleado: int, datos: dict) -> bool:
        """
        Modifica los datos personales de un empleado.

        Args:
            idempleado: Clave del empleado.
            datos: Campos a cambiar; los ausentes conservan su valor actual.

        Returns:
            True si se guardó el cambio.

        Raises:
            ErrorNoEncontrado: Si el empleado no existe.
            ErrorValidacion: Si nombres o apellidos quedan vacíos.
        """
        actual = self._repositorio.buscar_por_id(idempleado)
        if actual is None:
            raise ErrorNoEncontrado("No se encontró el empleado solicitado")

        combinados = {
            "nombres": datos.get("nombres", actual.nombres),
            "apellidos": datos.get("apellidos", actual.apellidos),
            "direccion": datos.get("direccion", actual.direccion),
            "telefono": datos.get("telefono", actual.telefono),
        }
        return self._repositorio.actualizar(
            idempleado, self._construir_empleado(idempleado, combinados)
        )

    def eliminar(self, idempleado: int) -> bool:
        """
        Borra un empleado y su credencial, si la tiene.

        Args:
            idempleado: Clave del empleado.

        Returns:
            True si se borró.

        Raises:
            ErrorNoEncontrado: Si el empleado no existe.
            ErrorEnUso: Si su usuario tiene ventas registradas (RF11 exige
                conservar la trazabilidad de quién vendió).
        """
        if not self._repositorio.existe(idempleado):
            raise ErrorNoEncontrado("No se encontró el empleado solicitado")

        with transaccion(self._conexion) as conexion:
            empleados = EmpleadoRepositorio(conexion)
            usuarios = UsuarioRepositorio(conexion)

            idusuario = empleados.obtener_idusuario(idempleado)
            if idusuario is not None:
                _verificar_sin_ventas(usuarios, idusuario)
                usuarios.eliminar(idusuario)
            return empleados.eliminar(idempleado)

    @staticmethod
    def _construir_empleado(idempleado: int, datos: dict) -> Empleado:
        """
        Valida y normaliza los datos de un empleado.

        Args:
            idempleado: Clave a asignar a la entidad.
            datos: Campos recibidos de la interfaz.

        Returns:
            La entidad lista para persistir.

        Raises:
            ErrorValidacion: Si nombres o apellidos no alcanzan el mínimo.
        """
        nombres = _texto_obligatorio(datos.get("nombres"), "Los nombres")
        apellidos = _texto_obligatorio(datos.get("apellidos"), "Los apellidos")
        return Empleado(
            idempleado=idempleado,
            nombres=nombres,
            apellidos=apellidos,
            direccion=_texto_opcional(datos.get("direccion")),
            telefono=_telefono_valido(datos.get("telefono")),
        )


class ServicioUsuarios:
    """Gestión de credenciales de acceso y de sus roles (RF01, RF02)."""

    def __init__(self, conexion: Conexion | None = None) -> None:
        """
        Args:
            conexion: Conexión de una transacción en curso, si la hay.
        """
        self._conexion = conexion
        self._repositorio = UsuarioRepositorio(conexion)

    def listar(self, texto: str | None = None) -> list[dict]:
        """
        Lista usuarios con sus datos de empleado y rol (RF08).

        Args:
            texto: Término de búsqueda parcial.

        Returns:
            Filas listas para mostrar, sin la columna de contraseña.
        """
        return self._repositorio.listar_con_detalle(texto)

    def crear_con_empleado(self, datos: dict) -> int:
        """
        Crea un empleado y su credencial en una sola transacción.

        Si algo falla a mitad de camino no queda ningún registro suelto.

        Args:
            datos: Diccionario con «nombres», «apellidos», «nombreusuario»,
                «contrasena», «idrol» y opcionalmente «direccion» y «telefono».

        Returns:
            Clave del usuario creado.

        Raises:
            ErrorValidacion: Si algún dato obligatorio falta o es inválido.
            ErrorDuplicado: Si el identificador de acceso ya está tomado.
        """
        nombreusuario = _validar_nombre_usuario(datos.get("nombreusuario"))
        contrasena = str(datos.get("contrasena") or "")
        idrol = _validar_rol(datos.get("idrol"))
        _validar_contrasena(contrasena)

        with transaccion(self._conexion) as conexion:
            usuarios = UsuarioRepositorio(conexion)
            if usuarios.existe_nombre_usuario(nombreusuario):
                raise ErrorDuplicado(f"El usuario «{nombreusuario}» ya existe")

            idempleado = ServicioEmpleados(conexion).crear(datos)
            return usuarios.insertar(
                Usuario(
                    idusuario=0,
                    idempleado=idempleado,
                    idrol=idrol,
                    nombreusuario=nombreusuario,
                    contrasena=cifrar_contrasena(contrasena),
                )
            )

    def crear_para_empleado(self, datos: dict) -> int:
        """
        Da credencial de acceso a un empleado que ya está registrado.

        Es la vía normal desde la pantalla de usuarios: los datos personales ya
        están en el sistema, así que solo se piden el identificador de acceso,
        la contraseña y el rol. Evita volver a escribir nombres y apellidos, y
        con ello el riesgo de crear un empleado duplicado por una diferencia de
        tecleo.

        Args:
            datos: Diccionario con «idempleado», «nombreusuario», «contrasena»
                y «idrol».

        Returns:
            Clave del usuario creado.

        Raises:
            ErrorValidacion: Si algún dato obligatorio falta o es inválido.
            ErrorNoEncontrado: Si el empleado indicado no existe.
            ErrorDuplicado: Si el identificador de acceso ya está tomado, o si
                el empleado ya tiene credencial.
        """
        idempleado = _validar_empleado(datos.get("idempleado"))
        nombreusuario = _validar_nombre_usuario(datos.get("nombreusuario"))
        idrol = _validar_rol(datos.get("idrol"))
        contrasena = str(datos.get("contrasena") or "")
        _validar_contrasena(contrasena)

        with transaccion(self._conexion) as conexion:
            usuarios = UsuarioRepositorio(conexion)
            self._comprobar_que_puede_recibir_credencial(
                conexion, idempleado, nombreusuario
            )

            return usuarios.insertar(
                Usuario(
                    idusuario=0,
                    idempleado=idempleado,
                    idrol=idrol,
                    nombreusuario=nombreusuario,
                    contrasena=cifrar_contrasena(contrasena),
                )
            )

    @staticmethod
    def _comprobar_que_puede_recibir_credencial(
        conexion: Conexion, idempleado: int, nombreusuario: str
    ) -> None:
        """
        Verifica que se pueda dar acceso a ese empleado con ese identificador.

        Args:
            conexion: Conexión de la transacción en curso.
            idempleado: Empleado al que se dará acceso.
            nombreusuario: Identificador de acceso solicitado.

        Raises:
            ErrorNoEncontrado: Si el empleado no existe.
            ErrorDuplicado: Si ya tiene credencial, o si el identificador está
                tomado por otro.
        """
        empleados = EmpleadoRepositorio(conexion)

        if empleados.buscar_por_id(idempleado) is None:
            raise ErrorNoEncontrado("No se encontró el empleado seleccionado")
        if empleados.obtener_idusuario(idempleado) is not None:
            raise ErrorDuplicado("Ese empleado ya tiene un usuario asignado")
        if UsuarioRepositorio(conexion).existe_nombre_usuario(nombreusuario):
            raise ErrorDuplicado(f"El usuario «{nombreusuario}» ya existe")

    def actualizar(self, idusuario: int, datos: dict) -> bool:
        """
        Modifica un usuario y los datos personales de su empleado.

        La contraseña solo se cambia si viene un valor no vacío; dejar el campo
        en blanco conserva la actual.

        Args:
            idusuario: Clave del usuario.
            datos: Campos a cambiar.

        Returns:
            True si se guardó el cambio.

        Raises:
            ErrorNoEncontrado: Si el usuario no existe.
            ErrorDuplicado: Si el nuevo identificador de acceso ya está tomado.
            ErrorValidacion: Si algún dato es inválido.
        """
        with transaccion(self._conexion) as conexion:
            usuarios = UsuarioRepositorio(conexion)
            actual = usuarios.buscar_por_id(idusuario)
            if actual is None:
                raise ErrorNoEncontrado("No se encontró el usuario solicitado")

            nombreusuario = _validar_nombre_usuario(
                datos.get("nombreusuario", actual.nombreusuario)
            )
            if usuarios.existe_nombre_usuario(nombreusuario, excluir_id=idusuario):
                raise ErrorDuplicado(f"El usuario «{nombreusuario}» ya existe")

            ServicioEmpleados(conexion).actualizar(actual.idempleado, datos)

            return usuarios.actualizar(
                idusuario,
                Usuario(
                    idusuario=idusuario,
                    idempleado=actual.idempleado,
                    idrol=_validar_rol(datos.get("idrol", actual.idrol)),
                    nombreusuario=nombreusuario,
                    contrasena=self._resolver_contrasena(datos.get("contrasena"), actual.contrasena),
                ),
            )

    def eliminar(self, idusuario: int) -> bool:
        """
        Borra un usuario y el empleado al que pertenece.

        Args:
            idusuario: Clave del usuario.

        Returns:
            True si se borró.

        Raises:
            ErrorNoEncontrado: Si el usuario no existe.
            ErrorEnUso: Si el usuario tiene ventas registradas.
        """
        with transaccion(self._conexion) as conexion:
            usuarios = UsuarioRepositorio(conexion)
            actual = usuarios.buscar_por_id(idusuario)
            if actual is None:
                raise ErrorNoEncontrado("No se encontró el usuario solicitado")

            _verificar_sin_ventas(usuarios, idusuario)
            usuarios.eliminar(idusuario)
            return EmpleadoRepositorio(conexion).eliminar(actual.idempleado)

    @staticmethod
    def _resolver_contrasena(nueva: str | None, actual: str) -> str:
        """
        Decide qué hash guardar al actualizar un usuario.

        Args:
            nueva: Contraseña escrita en el formulario; vacía significa «no cambiar».
            actual: Hash que ya está almacenado.

        Returns:
            El hash de la contraseña nueva, o el actual si no se cambió.

        Raises:
            ErrorValidacion: Si la contraseña nueva es demasiado corta.
        """
        if not nueva or not str(nueva).strip():
            return actual
        _validar_contrasena(str(nueva))
        return cifrar_contrasena(str(nueva))


# ── Validaciones compartidas del módulo ─────────────────────────────────


def _verificar_sin_ventas(repositorio: UsuarioRepositorio, idusuario: int) -> None:
    """
    Impide borrar un usuario que ya registró ventas.

    Args:
        repositorio: Repositorio con la conexión de la transacción en curso.
        idusuario: Clave del usuario a verificar.

    Raises:
        ErrorEnUso: Si el usuario tiene ventas asociadas.
    """
    fila = repositorio.consultar_uno(
        "SELECT COUNT(*) AS total FROM venta WHERE idusuario = ?", (idusuario,)
    )
    if fila and int(fila["total"]) > 0:
        raise ErrorEnUso(
            "No se puede eliminar: el usuario tiene ventas registradas. "
            "El historial de ventas debe conservar quién las hizo."
        )


def _validar_nombre_usuario(valor: str | None) -> str:
    """
    Normaliza y valida un identificador de acceso.

    Args:
        valor: Identificador escrito por el usuario.

    Returns:
        El identificador sin espacios sobrantes.

    Raises:
        ErrorValidacion: Si no alcanza la longitud mínima.
    """
    limpio = (valor or "").strip()
    if len(limpio) < LONGITUD_MINIMA_USUARIO:
        raise ErrorValidacion(
            f"El nombre de usuario debe tener al menos {LONGITUD_MINIMA_USUARIO} caracteres"
        )
    return limpio


def _validar_contrasena(valor: str) -> None:
    """
    Comprueba la fortaleza mínima de una contraseña (RNF04).

    Args:
        valor: Contraseña en texto plano.

    Raises:
        ErrorValidacion: Si no cumple el mínimo exigido.
    """
    try:
        validar_fortaleza(valor)
    except ValueError as error:
        raise ErrorValidacion(str(error)) from error


def _validar_rol(valor: object) -> int:
    """
    Convierte y valida la clave de rol recibida de la interfaz.

    Args:
        valor: Clave del rol, posiblemente como texto.

    Returns:
        La clave como entero.

    Raises:
        ErrorValidacion: Si falta o no es un número.
    """
    if valor is None or str(valor).strip() == "":
        raise ErrorValidacion("Debe seleccionar un rol")
    try:
        return int(valor)
    except (TypeError, ValueError) as error:
        raise ErrorValidacion("El rol seleccionado no es válido") from error


def _validar_empleado(valor: object) -> int:
    """
    Convierte y valida la clave de empleado recibida de la interfaz.

    Args:
        valor: Clave del empleado, posiblemente como texto.

    Returns:
        La clave como entero.

    Raises:
        ErrorValidacion: Si falta o no es un número.
    """
    if valor is None or str(valor).strip() == "":
        raise ErrorValidacion("Debe seleccionar un empleado")
    try:
        return int(valor)
    except (TypeError, ValueError) as error:
        raise ErrorValidacion("El empleado seleccionado no es válido") from error


def _texto_obligatorio(valor: object, etiqueta: str) -> str:
    """
    Normaliza un campo de texto que no puede quedar vacío.

    Args:
        valor: Texto recibido de la interfaz.
        etiqueta: Nombre del campo para el mensaje de error.

    Returns:
        El texto sin espacios sobrantes.

    Raises:
        ErrorValidacion: Si no alcanza la longitud mínima.
    """
    limpio = str(valor or "").strip()
    if len(limpio) < LONGITUD_MINIMA_NOMBRE:
        raise ErrorValidacion(f"{etiqueta} deben tener al menos {LONGITUD_MINIMA_NOMBRE} caracteres")
    return limpio


def _telefono_valido(valor: object) -> str | None:
    """
    Normaliza y comprueba un teléfono antes de guardarlo.

    La pantalla ya avisa mientras se escribe, pero esa comprobación no protege
    los datos: quien llame al servicio desde otro sitio —un script, una
    importación, una pantalla nueva— se la saltaría. La regla es la misma en
    ambas capas porque vive en :mod:`nucleo.validacion`.

    Args:
        valor: Teléfono recibido de la interfaz.

    Returns:
        El teléfono sin espacios sobrantes, o None si venía vacío.

    Raises:
        ErrorValidacion: Si el formato o el largo no son válidos.
    """
    limpio = _texto_opcional(valor)
    problema = revisar_telefono(limpio)
    if problema is not None:
        raise ErrorValidacion(problema)
    return limpio


def _texto_opcional(valor: object) -> str | None:
    """
    Normaliza un campo de texto opcional.

    Args:
        valor: Texto recibido de la interfaz.

    Returns:
        El texto sin espacios sobrantes, o None si quedó vacío.
    """
    if valor is None:
        return None
    limpio = str(valor).strip()
    return limpio or None

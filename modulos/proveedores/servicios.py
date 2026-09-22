"""Reglas de negocio del módulo de proveedores."""

from __future__ import annotations

from modulos.proveedores.modelos import Proveedor
from modulos.proveedores.repositorio import ProveedorRepositorio
from nucleo.base_datos import Conexion
from nucleo.errores import ErrorDuplicado, ErrorEnUso, ErrorNoEncontrado, ErrorValidacion
from nucleo.validacion import revisar_telefono

LONGITUD_MINIMA_NOMBRE = 2


class ServicioProveedores:
    """Alta, baja, modificación y consulta de proveedores."""

    def __init__(self, repositorio: ProveedorRepositorio | None = None, conexion: Conexion | None = None) -> None:
        """
        Args:
            repositorio: Repositorio a usar; útil para inyectar uno falso en pruebas.
            conexion: Conexión de una transacción en curso, si la hay.
        """
        self._repositorio = repositorio or ProveedorRepositorio(conexion)

    def listar(self, texto: str | None = None) -> list[Proveedor]:
        """
        Lista proveedores, opcionalmente filtrados (RF08).

        Args:
            texto: Término de búsqueda parcial.

        Returns:
            Proveedores ordenados por nombre.
        """
        return self._repositorio.buscar(texto)

    def crear(self, nombre: str, telefono: str | None = None, direccion: str | None = None) -> int:
        """
        Da de alta un proveedor.

        Args:
            nombre: Nombre o razón social; obligatorio.
            telefono: Teléfono de contacto, opcional.
            direccion: Dirección física, opcional.

        Returns:
            Clave primaria generada.

        Raises:
            ErrorValidacion: Si el nombre es demasiado corto.
            ErrorDuplicado: Si ya existe un proveedor con ese nombre.
        """
        limpio = self._validar_nombre(nombre)
        if self._repositorio.existe_nombre(limpio):
            raise ErrorDuplicado(f"Ya existe un proveedor llamado «{limpio}»")

        return self._repositorio.insertar(
            Proveedor(
                idproveedor=0,
                nombreproveedor=limpio,
                telefono=_telefono_valido(telefono),
                direccion=_texto_opcional(direccion),
            )
        )

    def actualizar(self, idproveedor: int, datos: dict) -> bool:
        """
        Modifica un proveedor existente.

        Args:
            idproveedor: Clave del proveedor.
            datos: Campos a cambiar; se aceptan «nombreproveedor», «telefono»
                y «direccion». Los ausentes conservan su valor actual.

        Returns:
            True si se guardó el cambio.

        Raises:
            ErrorNoEncontrado: Si el proveedor no existe.
            ErrorValidacion: Si el nombre resultante es inválido.
            ErrorDuplicado: Si otro proveedor ya usa ese nombre.
        """
        actual = self._repositorio.buscar_por_id(idproveedor)
        if actual is None:
            raise ErrorNoEncontrado("No se encontró el proveedor solicitado")

        nombre = self._validar_nombre(datos.get("nombreproveedor", actual.nombreproveedor))
        if self._repositorio.existe_nombre(nombre, excluir_id=idproveedor):
            raise ErrorDuplicado(f"Ya existe un proveedor llamado «{nombre}»")

        actualizado = Proveedor(
            idproveedor=idproveedor,
            nombreproveedor=nombre,
            telefono=_telefono_valido(datos.get("telefono", actual.telefono)),
            direccion=_texto_opcional(datos.get("direccion", actual.direccion)),
        )
        return self._repositorio.actualizar(idproveedor, actualizado)

    def eliminar(self, idproveedor: int) -> bool:
        """
        Borra un proveedor que no surta ningún producto.

        Args:
            idproveedor: Clave del proveedor.

        Returns:
            True si se borró.

        Raises:
            ErrorNoEncontrado: Si el proveedor no existe.
            ErrorEnUso: Si tiene productos asociados.
        """
        if not self._repositorio.existe(idproveedor):
            raise ErrorNoEncontrado("No se encontró el proveedor solicitado")
        if self._repositorio.contar_productos(idproveedor) > 0:
            raise ErrorEnUso("No se puede eliminar: hay productos de este proveedor")
        return self._repositorio.eliminar(idproveedor)

    @staticmethod
    def _validar_nombre(nombre: str | None) -> str:
        """
        Normaliza y valida el nombre del proveedor.

        Args:
            nombre: Nombre tal como lo escribió el usuario.

        Returns:
            El nombre sin espacios sobrantes.

        Raises:
            ErrorValidacion: Si queda por debajo del mínimo de caracteres.
        """
        limpio = (nombre or "").strip()
        if len(limpio) < LONGITUD_MINIMA_NOMBRE:
            raise ErrorValidacion(
                f"El nombre del proveedor debe tener al menos {LONGITUD_MINIMA_NOMBRE} caracteres"
            )
        return limpio


def _telefono_valido(valor: object) -> str | None:
    """
    Normaliza y comprueba un teléfono antes de guardarlo.

    La pantalla ya avisa mientras se escribe, pero esa comprobación no protege
    los datos: quien llame al servicio desde otro sitio se la saltaría. La
    regla es la misma en ambas capas porque vive en :mod:`nucleo.validacion`.

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


def _texto_opcional(valor: str | None) -> str | None:
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

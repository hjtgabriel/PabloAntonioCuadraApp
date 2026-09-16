"""
Servicio genérico para catálogos.

Concentra las validaciones que antes estaban copiadas en los servicios de rol,
categoría y marca: nombre obligatorio, nombre único y bloqueo del borrado
cuando otras tablas dependen del registro.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nucleo.errores import ErrorDuplicado, ErrorEnUso, ErrorNoEncontrado, ErrorValidacion
from nucleo.repositorio import RepositorioCatalogo

LONGITUD_MINIMA_NOMBRE = 2


@dataclass(frozen=True, slots=True)
class Dependencia:
    """
    Tabla que apunta a un catálogo y que impide borrarlo mientras lo use.

    Attributes:
        tabla: Nombre de la tabla dependiente (por ejemplo «producto»).
        columna: Columna de clave foránea dentro de esa tabla.
        descripcion: Texto en plural para el mensaje de error («productos»).
    """

    tabla: str
    columna: str
    descripcion: str


class ServicioCatalogo:
    """
    Reglas de negocio de un catálogo simple.

    Sirve igual para roles, categorías y marcas; lo único que cambia es el
    repositorio, la etiqueta que se muestra al usuario y qué tablas dependen
    de él.
    """

    def __init__(
        self,
        repositorio: RepositorioCatalogo,
        etiqueta: str,
        dependencias: tuple[Dependencia, ...] = (),
    ) -> None:
        """
        Args:
            repositorio: Repositorio del catálogo.
            etiqueta: Nombre singular para los mensajes («categoría», «marca»).
            dependencias: Tablas que impiden el borrado mientras lo referencien.
        """
        self._repositorio = repositorio
        self._etiqueta = etiqueta
        self._dependencias = dependencias

    @property
    def columna_nombre(self) -> str:
        """Nombre de la columna que guarda la descripción del catálogo."""
        return self._repositorio.columna_nombre

    @property
    def columna_clave(self) -> str:
        """Nombre de la columna de clave primaria."""
        return self._repositorio.clave

    def listar(self, texto: str | None = None) -> list[dict]:
        """
        Lista el catálogo, opcionalmente filtrado (RF08).

        Args:
            texto: Término de búsqueda parcial.

        Returns:
            Entradas ordenadas por nombre.
        """
        return self._repositorio.listar_ordenado(texto)

    def crear(self, nombre: str) -> int:
        """
        Da de alta una entrada.

        Args:
            nombre: Nombre de la nueva entrada.

        Returns:
            Clave primaria generada.

        Raises:
            ErrorValidacion: Si el nombre es demasiado corto.
            ErrorDuplicado: Si ya existe una entrada con ese nombre.
        """
        limpio = self._validar_nombre(nombre)
        if self._repositorio.existe_nombre(limpio):
            raise ErrorDuplicado(f"Ya existe {self._etiqueta} con el nombre «{limpio}»")
        return self._repositorio.insertar({self.columna_nombre: limpio})

    def actualizar(self, identificador: Any, nombre: str) -> bool:
        """
        Renombra una entrada existente.

        Args:
            identificador: Clave primaria de la entrada.
            nombre: Nombre nuevo.

        Returns:
            True si se guardó el cambio.

        Raises:
            ErrorValidacion: Si el nombre es demasiado corto.
            ErrorNoEncontrado: Si la entrada no existe.
            ErrorDuplicado: Si otra entrada ya usa ese nombre.
        """
        limpio = self._validar_nombre(nombre)
        if not self._repositorio.existe(identificador):
            raise ErrorNoEncontrado(f"No se encontró {self._etiqueta} solicitada")
        if self._repositorio.existe_nombre(limpio, excluir_id=identificador):
            raise ErrorDuplicado(f"Ya existe {self._etiqueta} con el nombre «{limpio}»")
        return self._repositorio.actualizar(identificador, {self.columna_nombre: limpio})

    def eliminar(self, identificador: Any) -> bool:
        """
        Borra una entrada si ninguna otra tabla la está usando.

        Args:
            identificador: Clave primaria de la entrada.

        Returns:
            True si se borró.

        Raises:
            ErrorNoEncontrado: Si la entrada no existe.
            ErrorEnUso: Si hay registros que la referencian.
        """
        if not self._repositorio.existe(identificador):
            raise ErrorNoEncontrado(f"No se encontró {self._etiqueta} solicitada")
        self._verificar_dependencias(identificador)
        return self._repositorio.eliminar(identificador)

    def _validar_nombre(self, nombre: str) -> str:
        """
        Normaliza y valida el nombre recibido.

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
                f"El nombre de {self._etiqueta} debe tener al menos "
                f"{LONGITUD_MINIMA_NOMBRE} caracteres"
            )
        return limpio

    def _verificar_dependencias(self, identificador: Any) -> None:
        """
        Comprueba que ninguna tabla dependiente use este registro.

        Args:
            identificador: Clave primaria a verificar.

        Raises:
            ErrorEnUso: Si alguna tabla dependiente lo referencia.
        """
        for dependencia in self._dependencias:
            sql = f"SELECT COUNT(*) AS total FROM {dependencia.tabla} WHERE {dependencia.columna} = ?"
            fila = self._repositorio.consultar_uno(sql, (identificador,))
            if fila and int(next(iter(fila.values()))) > 0:
                raise ErrorEnUso(
                    f"No se puede eliminar: hay {dependencia.descripcion} que usan "
                    f"esta {self._etiqueta}"
                )

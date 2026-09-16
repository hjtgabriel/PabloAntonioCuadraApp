"""
Repositorios base.

``RepositorioBase`` concentra el CRUD que antes se repetía en cada módulo.
``RepositorioCatalogo`` va un paso más allá y resuelve por completo las tablas
de catálogo (rol, categoría, marca), que solo tienen identificador y nombre: sus
repositorios concretos quedan reducidos a declarar tres atributos.

Un repositorio puede recibir una conexión ya abierta. Cuando la recibe, se suma
a la transacción en curso en lugar de abrir otra; así varias operaciones se
confirman o se revierten juntas.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from nucleo.base_datos import Conexion, obtener_motor, transaccion
from nucleo.errores import ErrorNoEncontrado

logger = logging.getLogger(__name__)

E = TypeVar("E")
"""Tipo de la entidad de dominio que maneja el repositorio."""

SIN_PARAMETROS: tuple[Any, ...] = ()


class RepositorioBase(ABC, Generic[E]):
    """
    Operaciones CRUD comunes a todas las entidades.

    Las subclases declaran ``tabla``, ``clave`` y ``columnas``, e implementan la
    conversión entre fila de base de datos y entidad de dominio.
    """

    tabla: str = ""
    clave: str = ""
    columnas: tuple[str, ...] = ()

    def __init__(self, conexion: Conexion | None = None) -> None:
        """
        Args:
            conexion: Conexión de una transacción en curso. Si es None, cada
                operación abre y cierra la suya.

        Raises:
            NotImplementedError: Si la subclase no declaró tabla o columnas.
        """
        if not self.tabla or not self.clave or not self.columnas:
            raise NotImplementedError(
                f"{type(self).__name__} debe declarar «tabla», «clave» y «columnas»"
            )
        self._conexion = conexion

    # ── Conversión entidad ↔ fila ───────────────────────────────

    @abstractmethod
    def _a_entidad(self, fila: dict) -> E:
        """Convierte una fila de la base de datos en entidad de dominio."""

    @abstractmethod
    def _a_fila(self, entidad: E) -> dict:
        """Convierte una entidad de dominio en el diccionario a persistir."""

    # ── Lectura ─────────────────────────────────────────────────

    def buscar_por_id(self, identificador: Any) -> E | None:
        """
        Busca una entidad por su clave primaria.

        Args:
            identificador: Valor de la clave primaria.

        Returns:
            La entidad, o None si no existe.
        """
        sql = f"SELECT {self._lista_columnas()} FROM {self.tabla} WHERE {self.clave} = ?"
        with self._trabajar() as conexion:
            fila = conexion.consultar_uno(sql, (identificador,))
        return self._a_entidad(fila) if fila else None

    def obtener_por_id(self, identificador: Any) -> E:
        """
        Igual que ``buscar_por_id`` pero exige que la entidad exista.

        Args:
            identificador: Valor de la clave primaria.

        Returns:
            La entidad encontrada.

        Raises:
            ErrorNoEncontrado: Si no existe ninguna fila con esa clave.
        """
        entidad = self.buscar_por_id(identificador)
        if entidad is None:
            raise ErrorNoEncontrado(f"No existe el registro {identificador} en {self.tabla}")
        return entidad

    def listar(
        self,
        condicion: str | None = None,
        parametros: Sequence[Any] = SIN_PARAMETROS,
        orden: str | None = None,
        limite: int | None = None,
        desplazamiento: int | None = None,
    ) -> list[E]:
        """
        Lista entidades con filtros opcionales.

        Args:
            condicion: Cláusula WHERE sin la palabra «WHERE», con marcadores «?».
            parametros: Valores para los marcadores de la condición.
            orden: Cláusula ORDER BY sin las palabras «ORDER BY».
            limite: Cantidad máxima de filas (paginación, RNF07).
            desplazamiento: Filas a saltar antes de empezar.

        Returns:
            Lista de entidades; vacía si no hubo coincidencias.
        """
        sql = f"SELECT {self._lista_columnas()} FROM {self.tabla}"
        valores = list(parametros)

        if condicion:
            sql += f" WHERE {condicion}"
        if orden:
            sql += f" ORDER BY {orden}"
        if limite is not None:
            sql += " LIMIT ?"
            valores.append(limite)
        if desplazamiento is not None:
            sql += " OFFSET ?"
            valores.append(desplazamiento)

        with self._trabajar() as conexion:
            filas = conexion.consultar(sql, valores)
        return [self._a_entidad(fila) for fila in filas]

    def contar(
        self,
        condicion: str | None = None,
        parametros: Sequence[Any] = SIN_PARAMETROS,
    ) -> int:
        """
        Cuenta filas que cumplen una condición.

        Args:
            condicion: Cláusula WHERE sin la palabra «WHERE».
            parametros: Valores para los marcadores.

        Returns:
            Cantidad de filas coincidentes.
        """
        sql = f"SELECT COUNT(*) AS total FROM {self.tabla}"
        if condicion:
            sql += f" WHERE {condicion}"
        with self._trabajar() as conexion:
            return int(conexion.consultar_escalar(sql, parametros) or 0)

    def existe(self, identificador: Any) -> bool:
        """Indica si hay una fila con esa clave primaria."""
        return self.contar(f"{self.clave} = ?", (identificador,)) > 0

    # ── Escritura ───────────────────────────────────────────────

    def insertar(self, entidad: E) -> int:
        """
        Inserta una entidad nueva.

        Args:
            entidad: Entidad a guardar (su clave primaria se ignora).

        Returns:
            Clave primaria generada por la base de datos.
        """
        valores = self._a_fila(entidad)
        with self._trabajar_escribiendo() as conexion:
            return conexion.insertar(self.tabla, valores, self.clave)

    def actualizar(self, identificador: Any, entidad: E) -> bool:
        """
        Sobrescribe una entidad existente.

        Args:
            identificador: Clave primaria de la fila a modificar.
            entidad: Entidad con los valores nuevos.

        Returns:
            True si se modificó alguna fila.
        """
        valores = self._a_fila(entidad)
        if not valores:
            return False

        asignaciones = ", ".join(f"{columna} = ?" for columna in valores)
        sql = f"UPDATE {self.tabla} SET {asignaciones} WHERE {self.clave} = ?"
        with self._trabajar_escribiendo() as conexion:
            return conexion.ejecutar(sql, (*valores.values(), identificador)) > 0

    def eliminar(self, identificador: Any) -> bool:
        """
        Borra una fila por su clave primaria.

        Args:
            identificador: Clave primaria de la fila a borrar.

        Returns:
            True si se borró alguna fila.
        """
        sql = f"DELETE FROM {self.tabla} WHERE {self.clave} = ?"
        with self._trabajar_escribiendo() as conexion:
            return conexion.ejecutar(sql, (identificador,)) > 0

    # ── Consultas propias del dominio ───────────────────────────

    def consultar(self, sql: str, parametros: Sequence[Any] = SIN_PARAMETROS) -> list[dict]:
        """
        Ejecuta un SELECT propio del dominio (con JOIN, agregados, etc.).

        Args:
            sql: Sentencia SELECT con marcadores «?».
            parametros: Valores para los marcadores.

        Returns:
            Filas como diccionarios.
        """
        with self._trabajar() as conexion:
            return conexion.consultar(sql, parametros)

    def consultar_uno(self, sql: str, parametros: Sequence[Any] = SIN_PARAMETROS) -> dict | None:
        """Ejecuta un SELECT propio del dominio y devuelve solo la primera fila."""
        with self._trabajar() as conexion:
            return conexion.consultar_uno(sql, parametros)

    def ejecutar(self, sql: str, parametros: Sequence[Any] = SIN_PARAMETROS) -> int:
        """
        Ejecuta una escritura propia del dominio.

        Args:
            sql: Sentencia INSERT, UPDATE o DELETE con marcadores «?».
            parametros: Valores para los marcadores.

        Returns:
            Cantidad de filas afectadas.
        """
        with self._trabajar_escribiendo() as conexion:
            return conexion.ejecutar(sql, parametros)

    # ── Apoyo interno ───────────────────────────────────────────

    def _lista_columnas(self, prefijo: str = "") -> str:
        """
        Arma la lista de columnas del SELECT, con la clave primaria incluida.

        Args:
            prefijo: Alias de tabla a anteponer, por ejemplo «p.».

        Returns:
            Columnas separadas por coma.
        """
        return ", ".join(f"{prefijo}{columna}" for columna in (self.clave, *self.columnas))

    def _trabajar(self):
        """Devuelve un contexto de solo lectura: reusa la conexión o toma una del motor."""
        if self._conexion is not None:
            return _ConexionPrestada(self._conexion)
        return obtener_motor().conexion()

    def _trabajar_escribiendo(self):
        """Devuelve un contexto de escritura: se suma a la transacción abierta o abre una."""
        return transaccion(self._conexion)


class _ConexionPrestada:
    """Envuelve una conexión ajena para usarla con ``with`` sin cerrarla."""

    def __init__(self, conexion: Conexion) -> None:
        """
        Args:
            conexion: Conexión ya abierta por otro, que no hay que cerrar.
        """
        self._conexion = conexion

    def __enter__(self) -> Conexion:
        """
        Entrega la conexión prestada sin abrir ninguna nueva.

        Returns:
            La misma conexión que se recibió.
        """
        return self._conexion

    def __exit__(self, *_excepcion: object) -> bool:
        """
        Sale del bloque sin cerrar la conexión, que es de quien la prestó.

        Returns:
            False, para que cualquier excepción siga su curso.
        """
        return False


class RepositorioCatalogo(RepositorioBase[dict]):
    """
    Repositorio para tablas de catálogo: identificador + un nombre.

    Cubre «rol», «categoria» y «marca», que antes tenían tres repositorios de
    164 líneas prácticamente idénticos. Una subclase concreta solo necesita::

        class MarcaRepositorio(RepositorioCatalogo):
            tabla = "marca"
            clave = "idmarca"
            columna_nombre = "nombremarca"

    Las entidades se manejan como diccionarios porque un catálogo no tiene
    comportamiento propio que justifique una clase.
    """

    columna_nombre: str = ""

    def __init__(self, conexion: Conexion | None = None) -> None:
        """
        Args:
            conexion: Conexión de una transacción en curso, si la hay.

        Raises:
            NotImplementedError: Si la subclase no declaró ``columna_nombre``.
        """
        if not self.columna_nombre:
            raise NotImplementedError(f"{type(self).__name__} debe declarar «columna_nombre»")
        self.columnas = (self.columna_nombre,)
        super().__init__(conexion)

    def _a_entidad(self, fila: dict) -> dict:
        """Un catálogo se representa tal cual viene de la base de datos."""
        return dict(fila)

    def _a_fila(self, entidad: dict) -> dict:
        """Solo persiste la columna de nombre; la clave la genera la base de datos."""
        return {self.columna_nombre: entidad[self.columna_nombre]}

    def listar_ordenado(self, texto: str | None = None) -> list[dict]:
        """
        Lista el catálogo alfabéticamente, con filtro opcional por nombre.

        Args:
            texto: Término de búsqueda parcial; None o vacío lista todo.

        Returns:
            Entradas del catálogo ordenadas por nombre.
        """
        if texto and texto.strip():
            condicion = obtener_motor().dialecto.comparar_texto(self.columna_nombre)
            return self.listar(condicion, (f"%{texto.strip()}%",), orden=self.columna_nombre)
        return self.listar(orden=self.columna_nombre)

    def existe_nombre(self, nombre: str, excluir_id: Any | None = None) -> bool:
        """
        Indica si el nombre ya está tomado.

        Args:
            nombre: Nombre a verificar.
            excluir_id: Clave a ignorar en la comparación, para no chocar
                consigo misma al editar.

        Returns:
            True si otro registro ya usa ese nombre.
        """
        condicion = obtener_motor().dialecto.comparar_texto(self.columna_nombre)
        parametros: list[Any] = [nombre.strip()]
        if excluir_id is not None:
            condicion += f" AND {self.clave} <> ?"
            parametros.append(excluir_id)
        return self.contar(condicion, parametros) > 0

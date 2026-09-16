"""
Capa de acceso a la base de datos.

Responsabilidades:

* Abstraer el driver detrás de la clase ``Motor`` (PostgreSQL con reserva de
  conexiones, o SQLite para pruebas).
* Entregar a los repositorios un objeto ``Conexion`` uniforme cuyos métodos
  siempre devuelven filas como diccionarios, sin importar el motor.
* Ofrecer transacciones atómicas que se pueden anidar sin abrir una segunda
  conexión: si ya se está dentro de una transacción, la interna se suma a ella
  y quien la abrió decide el commit.

Este módulo es el único de todo el proyecto que importa ``psycopg2``.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager
from typing import Any

from config import obtener_configuracion
from nucleo.dialecto import DialectoPostgreSQL, DialectoSQL, DialectoSQLite
from nucleo.errores import (
    ErrorAplicacion,
    ErrorConexion,
    ErrorIntegridad,
    ErrorTransaccion,
)

logger = logging.getLogger(__name__)

SIN_PARAMETROS: tuple[Any, ...] = ()


class Conexion:
    """
    Conexión a la base de datos con una interfaz independiente del motor.

    Los repositorios trabajan siempre contra esta clase, nunca contra el objeto
    del driver. El SQL se escribe con marcadores «?» y esta clase lo adapta al
    dialecto activo.
    """

    def __init__(self, conexion_driver: Any, dialecto: DialectoSQL) -> None:
        """
        Args:
            conexion_driver: Conexión nativa del driver (psycopg2 o sqlite3).
            dialecto: Dialecto SQL correspondiente al motor.
        """
        self._driver = conexion_driver
        self._dialecto = dialecto

    @property
    def dialecto(self) -> DialectoSQL:
        """Dialecto SQL del motor al que apunta esta conexión."""
        return self._dialecto

    @property
    def driver(self) -> Any:
        """Conexión nativa subyacente (solo para utilidades de bajo nivel)."""
        return self._driver

    # ── Lectura ─────────────────────────────────────────────────

    def consultar(self, sql: str, parametros: Sequence[Any] = SIN_PARAMETROS) -> list[dict]:
        """
        Ejecuta un SELECT y devuelve todas las filas.

        Args:
            sql: Sentencia SELECT con marcadores «?».
            parametros: Valores para los marcadores.

        Returns:
            Lista de filas como diccionarios (vacía si no hubo resultados).
        """
        with self._cursor() as cursor:
            cursor.execute(self._dialecto.adaptar_parametros(sql), tuple(parametros))
            return [dict(fila) for fila in cursor.fetchall()]

    def consultar_uno(self, sql: str, parametros: Sequence[Any] = SIN_PARAMETROS) -> dict | None:
        """
        Ejecuta un SELECT y devuelve la primera fila.

        Args:
            sql: Sentencia SELECT con marcadores «?».
            parametros: Valores para los marcadores.

        Returns:
            La primera fila como diccionario, o None si no hubo resultados.
        """
        with self._cursor() as cursor:
            cursor.execute(self._dialecto.adaptar_parametros(sql), tuple(parametros))
            fila = cursor.fetchone()
            return dict(fila) if fila is not None else None

    def consultar_escalar(self, sql: str, parametros: Sequence[Any] = SIN_PARAMETROS) -> Any:
        """
        Ejecuta un SELECT de un solo valor (COUNT, SUM, MAX…) y lo devuelve.

        Args:
            sql: Sentencia SELECT que produce una única columna.
            parametros: Valores para los marcadores.

        Returns:
            El valor de la primera columna de la primera fila, o None.
        """
        fila = self.consultar_uno(sql, parametros)
        if not fila:
            return None
        return next(iter(fila.values()))

    # ── Escritura ───────────────────────────────────────────────

    def ejecutar(self, sql: str, parametros: Sequence[Any] = SIN_PARAMETROS) -> int:
        """
        Ejecuta un INSERT, UPDATE o DELETE.

        Args:
            sql: Sentencia con marcadores «?».
            parametros: Valores para los marcadores.

        Returns:
            Cantidad de filas afectadas.

        Raises:
            ErrorIntegridad: Si se viola una restricción de la base de datos.
        """
        with self._cursor() as cursor:
            try:
                cursor.execute(self._dialecto.adaptar_parametros(sql), tuple(parametros))
            except Exception as error:
                raise self._traducir_error(error) from error
            return cursor.rowcount

    def insertar(self, tabla: str, valores: dict[str, Any], clave: str) -> int:
        """
        Inserta una fila y devuelve la clave primaria generada.

        Resuelve por dentro la diferencia entre motores: PostgreSQL usa
        ``RETURNING`` y SQLite usa ``lastrowid``.

        Args:
            tabla: Nombre de la tabla destino.
            valores: Diccionario columna → valor.
            clave: Nombre de la columna clave primaria.

        Returns:
            Valor de la clave primaria de la fila recién insertada.

        Raises:
            ErrorIntegridad: Si se viola una restricción de la base de datos.
        """
        columnas = list(valores)
        marcadores = ", ".join("?" for _ in columnas)
        sql = f"INSERT INTO {tabla} ({', '.join(columnas)}) VALUES ({marcadores})"
        if self._dialecto.soporta_returning:
            sql += f" RETURNING {clave}"

        with self._cursor() as cursor:
            try:
                cursor.execute(self._dialecto.adaptar_parametros(sql), tuple(valores.values()))
            except Exception as error:
                raise self._traducir_error(error) from error

            if self._dialecto.soporta_returning:
                fila = cursor.fetchone()
                return int(next(iter(dict(fila).values())))
            return int(cursor.lastrowid)

    # ── Control de transacción ──────────────────────────────────

    def confirmar(self) -> None:
        """Confirma la transacción en curso."""
        self._driver.commit()

    def revertir(self) -> None:
        """Revierte la transacción en curso."""
        self._driver.rollback()

    # ── Apoyo interno ───────────────────────────────────────────

    @contextmanager
    def _cursor(self) -> Iterator[Any]:
        """Abre un cursor que produce filas tipo diccionario y lo cierra al salir."""
        cursor = self._driver.cursor()
        try:
            yield cursor
        finally:
            cursor.close()

    @staticmethod
    def _traducir_error(error: Exception) -> Exception:
        """
        Convierte un error del driver en un error propio de la aplicación.

        Args:
            error: Excepción lanzada por el driver.

        Returns:
            ``ErrorIntegridad`` si corresponde a una restricción violada; en
            caso contrario devuelve el error original para no ocultarlo.
        """
        nombre = type(error).__name__
        if "IntegrityError" in nombre:
            return ErrorIntegridad(str(error))
        return error


class Motor(ABC):
    """Fuente de conexiones a la base de datos."""

    def __init__(self, dialecto: DialectoSQL) -> None:
        self._dialecto = dialecto

    @property
    def dialecto(self) -> DialectoSQL:
        """Dialecto SQL de este motor."""
        return self._dialecto

    @abstractmethod
    def conexion(self) -> AbstractContextManager[Conexion]:
        """
        Entrega una conexión lista para usar y la libera al terminar.

        Las subclases implementan este método decorándolo con
        ``@contextmanager``.
        """

    @abstractmethod
    def cerrar(self) -> None:
        """Libera todos los recursos del motor."""


class MotorPostgreSQL(Motor):
    """
    Motor de PostgreSQL con reserva de conexiones (pool) apta para hilos.

    La reserva evita reabrir la conexión en cada consulta, que es lo que permite
    registrar una venta en menos de 3 segundos (RNF06) y sostener catálogos
    grandes sin degradarse (RNF07).
    """

    def __init__(self) -> None:
        super().__init__(DialectoPostgreSQL())
        from psycopg2.pool import ThreadedConnectionPool

        configuracion = obtener_configuracion()
        try:
            self._pool = ThreadedConnectionPool(
                minconn=configuracion.db_pool_min,
                maxconn=configuracion.db_pool_max,
                host=configuracion.db_host,
                port=configuracion.db_puerto,
                dbname=configuracion.db_nombre,
                user=configuracion.db_usuario,
                password=configuracion.db_password,
            )
        except Exception as error:
            raise ErrorConexion(f"No se pudo conectar a PostgreSQL: {error}") from error

        logger.info(
            "Reserva de conexiones lista (min=%d, max=%d) sobre %s:%s/%s",
            configuracion.db_pool_min,
            configuracion.db_pool_max,
            configuracion.db_host,
            configuracion.db_puerto,
            configuracion.db_nombre,
        )

    @contextmanager
    def conexion(self) -> Iterator[Conexion]:
        """Toma una conexión de la reserva y la devuelve al terminar."""
        conexion_driver = None
        try:
            conexion_driver = self._pool.getconn()
            conexion_driver.autocommit = False
            yield _ConexionPostgreSQL(conexion_driver, self._dialecto)
        except ErrorConexion:
            raise
        except Exception as error:
            raise ErrorConexion(f"Error obteniendo conexión: {error}") from error
        finally:
            if conexion_driver is not None:
                self._pool.putconn(conexion_driver)

    def cerrar(self) -> None:
        """Cierra todas las conexiones de la reserva."""
        self._pool.closeall()
        logger.info("Reserva de conexiones cerrada")


class _ConexionPostgreSQL(Conexion):
    """Conexión de PostgreSQL cuyos cursores devuelven filas como diccionarios."""

    @contextmanager
    def _cursor(self) -> Iterator[Any]:
        """Abre un cursor con ``RealDictCursor`` para obtener filas indexadas por nombre."""
        from psycopg2.extras import RealDictCursor

        cursor = self._driver.cursor(cursor_factory=RealDictCursor)
        try:
            yield cursor
        finally:
            cursor.close()


class MotorSQLite(Motor):
    """
    Motor de SQLite, usado por la batería de pruebas.

    Su existencia demuestra que la capa de datos no está atada a PostgreSQL:
    los repositorios corren sin cambios sobre ambos motores.
    """

    def __init__(self, ruta: str = ":memory:") -> None:
        super().__init__(DialectoSQLite())
        self._ruta = ruta
        self._local = threading.local()

    def _obtener_driver(self) -> sqlite3.Connection:
        """Devuelve la conexión SQLite propia del hilo actual, creándola si hace falta."""
        conexion = getattr(self._local, "conexion", None)
        if conexion is None:
            conexion = sqlite3.connect(self._ruta, check_same_thread=False)
            conexion.row_factory = sqlite3.Row
            conexion.execute("PRAGMA foreign_keys = ON")
            self._local.conexion = conexion
        return conexion

    @contextmanager
    def conexion(self) -> Iterator[Conexion]:
        """Entrega la conexión del hilo actual."""
        yield Conexion(self._obtener_driver(), self._dialecto)

    def cerrar(self) -> None:
        """Cierra la conexión del hilo actual, si existe."""
        conexion = getattr(self._local, "conexion", None)
        if conexion is not None:
            conexion.close()
            self._local.conexion = None


# ── Motor activo del proceso ────────────────────────────────────────────

_motor: Motor | None = None
_candado = threading.Lock()


def obtener_motor() -> Motor:
    """
    Devuelve el motor activo, creándolo la primera vez según la configuración.

    Returns:
        El motor correspondiente a ``DB_MOTOR``.
    """
    global _motor
    if _motor is None:
        with _candado:
            if _motor is None:
                configuracion = obtener_configuracion()
                if configuracion.usa_sqlite:
                    _motor = MotorSQLite(str(configuracion.ruta_sqlite))
                else:
                    _motor = MotorPostgreSQL()
    return _motor


def configurar_motor(motor: Motor | None) -> None:
    """
    Fija el motor activo a mano.

    Lo usan las pruebas para trabajar sobre SQLite en memoria.

    Args:
        motor: Motor a instalar, o None para volver al arranque automático.
    """
    global _motor
    with _candado:
        _motor = motor


def cerrar_motor() -> None:
    """Cierra el motor activo y lo descarta."""
    global _motor
    with _candado:
        if _motor is not None:
            _motor.cerrar()
            _motor = None


@contextmanager
def transaccion(conexion: Conexion | None = None) -> Iterator[Conexion]:
    """
    Ejecuta un bloque de trabajo de forma atómica.

    Si se recibe una conexión, significa que ya hay una transacción abierta más
    afuera: el bloque se suma a ella y no confirma nada, porque el commit le
    corresponde a quien la abrió. Eso permite que un servicio llame a otro sin
    provocar un bloqueo entre dos conexiones distintas.

    Los errores propios de la aplicación se propagan tal cual, después de
    revertir: si una venta se rechaza por falta de existencias, quien la pidió
    debe recibir un ``ErrorStockInsuficiente`` y no un ``ErrorTransaccion``
    genérico que le esconda el motivo. Solo los fallos ajenos se envuelven.

    Args:
        conexion: Conexión de una transacción ya abierta, o None para abrir una.

    Yields:
        La conexión sobre la que trabajar.

    Raises:
        ErrorAplicacion: El error de negocio que haya ocurrido, sin alterar.
        ErrorTransaccion: Si el fallo vino de fuera de la aplicación.

    Ejemplo::

        with transaccion() as cx:
            repositorio = ProductoRepositorio(cx)
            repositorio.insertar(producto)
    """
    if conexion is not None:
        yield conexion
        return

    with obtener_motor().conexion() as nueva_conexion:
        try:
            yield nueva_conexion
            nueva_conexion.confirmar()
        except Exception as error:
            _revertir_sin_ocultar(nueva_conexion, error)
            if isinstance(error, ErrorAplicacion):
                raise
            raise ErrorTransaccion(str(error)) from error


def _revertir_sin_ocultar(conexion: Conexion, error_original: Exception) -> None:
    """
    Revierte la transacción registrando, pero sin propagar, un fallo del rollback.

    Args:
        conexion: Conexión a revertir.
        error_original: Error que provocó la reversión, solo para el registro.
    """
    try:
        conexion.revertir()
        logger.warning("Transacción revertida por: %s", error_original)
    except Exception as error_rollback:
        logger.error("Además falló la reversión: %s", error_rollback)

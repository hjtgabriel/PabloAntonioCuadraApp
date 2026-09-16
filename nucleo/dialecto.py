"""
Abstracción del dialecto SQL.

Todo el SQL del proyecto se escribe con marcadores ``?`` y, cuando necesita algo
que cambia entre motores (búsqueda sin distinguir mayúsculas, recuperar la clave
recién generada, recortar una marca de tiempo a fecha, restar días), lo pide a
través de este objeto en vez de incrustar sintaxis de PostgreSQL.

Gracias a esto, migrar a otro motor consiste en escribir una subclase de
``DialectoSQL`` y un adaptador de conexión, sin tocar ni un repositorio.

Ya vienen dos implementaciones: PostgreSQL (la de producción) y SQLite (que
además permite ejecutar la batería de pruebas sin instalar un servidor).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class DialectoSQL(ABC):
    """Diferencias de sintaxis entre motores de base de datos."""

    nombre: str
    marcador: str
    """Marcador de parámetro del driver: «%s» en psycopg2, «?» en sqlite3."""

    soporta_returning: bool
    """True si el motor puede devolver la clave generada con RETURNING."""

    def adaptar_parametros(self, sql: str) -> str:
        """
        Traduce los marcadores «?» del SQL al estilo que espera el driver.

        Args:
            sql: Sentencia escrita con marcadores «?».

        Returns:
            La misma sentencia con el marcador propio del motor.
        """
        if self.marcador == "?":
            return sql
        return sql.replace("?", self.marcador)

    @abstractmethod
    def comparar_texto(self, columna: str) -> str:
        """
        Fragmento de condición para buscar texto sin distinguir mayúsculas.

        Args:
            columna: Nombre (o expresión) de la columna a comparar.

        Returns:
            Condición lista para concatenar en un WHERE, con un marcador «?».
        """

    @abstractmethod
    def solo_fecha(self, columna: str) -> str:
        """Expresión que recorta una marca de tiempo a su fecha."""

    @abstractmethod
    def hace_dias(self, dias: int) -> str:
        """Expresión que representa la fecha de hace ``dias`` días."""

    def ahora(self) -> str:
        """Expresión de la fecha y hora actual del servidor."""
        return "CURRENT_TIMESTAMP"


class DialectoPostgreSQL(DialectoSQL):
    """Dialecto de PostgreSQL, el motor de producción del sistema (RNF01)."""

    nombre = "postgresql"
    marcador = "%s"
    soporta_returning = True

    def comparar_texto(self, columna: str) -> str:
        """Usa ILIKE, el operador nativo de PostgreSQL."""
        return f"{columna} ILIKE ?"

    def solo_fecha(self, columna: str) -> str:
        """Convierte a DATE con CAST estándar."""
        return f"CAST({columna} AS DATE)"

    def hace_dias(self, dias: int) -> str:
        """Resta días con la sintaxis INTERVAL de PostgreSQL."""
        return f"CURRENT_DATE - INTERVAL '{int(dias)} days'"


class DialectoSQLite(DialectoSQL):
    """
    Dialecto de SQLite.

    Se usa en las pruebas automatizadas y sirve de comprobación de que la capa
    de datos no depende de PostgreSQL.
    """

    nombre = "sqlite"
    marcador = "?"
    soporta_returning = False

    def comparar_texto(self, columna: str) -> str:
        """SQLite no tiene ILIKE; se normaliza con UPPER en ambos lados."""
        return f"UPPER({columna}) LIKE UPPER(?)"

    def solo_fecha(self, columna: str) -> str:
        """SQLite recorta la fecha con la función DATE()."""
        return f"DATE({columna})"

    def hace_dias(self, dias: int) -> str:
        """SQLite resta días con modificadores de la función DATE()."""
        return f"DATE('now', '-{int(dias)} days')"


DIALECTOS: dict[str, type[DialectoSQL]] = {
    DialectoPostgreSQL.nombre: DialectoPostgreSQL,
    DialectoSQLite.nombre: DialectoSQLite,
}


def obtener_dialecto(nombre: str) -> DialectoSQL:
    """
    Construye el dialecto correspondiente a un motor.

    Args:
        nombre: Identificador del motor («postgresql» o «sqlite»).

    Returns:
        Instancia del dialecto.

    Raises:
        ValueError: Si el motor no tiene dialecto registrado.
    """
    clase = DIALECTOS.get(nombre.strip().lower())
    if clase is None:
        admitidos = ", ".join(sorted(DIALECTOS))
        raise ValueError(f"Sin dialecto para el motor {nombre!r}. Disponibles: {admitidos}")
    return clase()

"""
Pruebas de la abstracción de base de datos.

El hecho de que toda la batería corra sobre SQLite ya demuestra que el sistema
no depende de PostgreSQL. Estas pruebas verifican explícitamente las piezas que
hacen posible esa independencia, para que nadie las rompa sin darse cuenta.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from nucleo.dialecto import (
    DialectoPostgreSQL,
    DialectoSQLite,
    obtener_dialecto,
)

RAIZ = pathlib.Path(__file__).resolve().parents[1]


# ── El dialecto traduce lo que cambia entre motores ─────────────────────


def test_los_marcadores_se_adaptan_a_cada_motor():
    """El SQL se escribe con «?» y cada dialecto lo traduce a su estilo."""
    sql = "SELECT * FROM producto WHERE idproducto = ? AND stock > ?"
    assert DialectoSQLite().adaptar_parametros(sql) == sql
    assert DialectoPostgreSQL().adaptar_parametros(sql).count("%s") == 2
    assert "?" not in DialectoPostgreSQL().adaptar_parametros(sql)


def test_la_busqueda_sin_mayusculas_usa_la_sintaxis_de_cada_motor():
    """PostgreSQL resuelve con ILIKE; SQLite necesita normalizar con UPPER."""
    assert DialectoPostgreSQL().comparar_texto("descripcion") == "descripcion ILIKE ?"
    assert "UPPER" in DialectoSQLite().comparar_texto("descripcion")
    assert "ILIKE" not in DialectoSQLite().comparar_texto("descripcion")


def test_el_recorte_a_fecha_se_adapta():
    """Cada motor recorta una marca de tiempo a su manera."""
    assert DialectoPostgreSQL().solo_fecha("v.fechaventa") == "CAST(v.fechaventa AS DATE)"
    assert DialectoSQLite().solo_fecha("v.fechaventa") == "DATE(v.fechaventa)"


def test_la_resta_de_dias_se_adapta():
    """El INTERVAL de PostgreSQL no existe en SQLite."""
    assert "INTERVAL" in DialectoPostgreSQL().hace_dias(7)
    assert "INTERVAL" not in DialectoSQLite().hace_dias(7)
    assert "-7 days" in DialectoSQLite().hace_dias(7)


def test_cada_motor_declara_si_soporta_returning():
    """La recuperación de la clave generada difiere entre motores."""
    assert DialectoPostgreSQL().soporta_returning
    assert not DialectoSQLite().soporta_returning


def test_se_obtiene_el_dialecto_por_nombre():
    """La fábrica debe resolver el dialecto a partir del nombre del motor."""
    assert isinstance(obtener_dialecto("postgresql"), DialectoPostgreSQL)
    assert isinstance(obtener_dialecto("sqlite"), DialectoSQLite)


def test_un_motor_desconocido_falla_con_mensaje_claro():
    """Pedir un motor sin dialecto debe explicar cuáles hay."""
    with pytest.raises(ValueError, match="Disponibles"):
        obtener_dialecto("oracle")


# ── El driver no se filtra a las capas superiores ───────────────────────


def _archivos_python(*carpetas: str) -> list[pathlib.Path]:
    """
    Reúne los archivos Python de las carpetas indicadas.

    Args:
        carpetas: Nombres de carpeta relativos a la raíz del proyecto.

    Returns:
        Rutas de todos los archivos «.py» encontrados.
    """
    archivos: list[pathlib.Path] = []
    for carpeta in carpetas:
        archivos.extend(
            ruta
            for ruta in (RAIZ / carpeta).rglob("*.py")
            if "__pycache__" not in ruta.parts
        )
    return archivos


def _importa_el_driver(ruta: pathlib.Path) -> bool:
    """
    Indica si un archivo importa psycopg2 de verdad.

    Mira las sentencias de importación del árbol sintáctico en vez de buscar el
    texto, para no confundir una importación real con una mención en un
    comentario o en una cadena de documentación.

    Args:
        ruta: Archivo Python a inspeccionar.

    Returns:
        True si el archivo importa el driver.
    """
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import) and any(
            alias.name.split(".")[0] == "psycopg2" for alias in nodo.names
        ):
            return True
        if isinstance(nodo, ast.ImportFrom) and (nodo.module or "").split(".")[0] == "psycopg2":
            return True
    return False


def test_ninguna_capa_de_negocio_importa_el_driver():
    """
    Solo el núcleo puede conocer psycopg2.

    Si un repositorio importara el driver, cambiar de motor obligaría a tocar
    los módulos de negocio.
    """
    culpables = [
        ruta.relative_to(RAIZ).as_posix()
        for ruta in _archivos_python("modulos", "vistas")
        if _importa_el_driver(ruta)
    ]
    assert culpables == [], f"Estos archivos importan el driver: {culpables}"


def test_solo_un_archivo_del_nucleo_conoce_el_driver():
    """La dependencia de psycopg2 debe estar concentrada en un único archivo."""
    con_driver = sorted(
        ruta.name for ruta in _archivos_python("nucleo") if _importa_el_driver(ruta)
    )
    assert con_driver == ["base_datos.py"]


def test_no_queda_sintaxis_de_postgresql_incrustada():
    """
    Las palabras propias de PostgreSQL deben pedirse al dialecto.

    Encontrarlas escritas a mano en un módulo significaría que el SQL volvió a
    quedar atado a un motor concreto.
    """
    prohibidas = ("ILIKE", "::date", "INTERVAL '")
    culpables = []
    for ruta in _archivos_python("modulos"):
        contenido = ruta.read_text(encoding="utf-8")
        encontradas = [palabra for palabra in prohibidas if palabra in contenido]
        if encontradas:
            culpables.append(f"{ruta.relative_to(RAIZ).as_posix()}: {encontradas}")
    assert culpables == [], f"Sintaxis de PostgreSQL incrustada en: {culpables}"


def test_los_marcadores_de_psycopg2_no_aparecen_en_los_modulos():
    """El SQL de negocio debe usar «?», no el «%s» propio de psycopg2."""
    culpables = [
        ruta.relative_to(RAIZ).as_posix()
        for ruta in _archivos_python("modulos")
        if "= %s" in ruta.read_text(encoding="utf-8")
    ]
    assert culpables == [], f"Marcadores de psycopg2 en: {culpables}"


# ── La conexión normaliza el resultado ──────────────────────────────────


def test_las_filas_llegan_siempre_como_diccionario(base_datos):
    """
    Las consultas deben devolver filas indexables por nombre de columna.

    Es la regresión del defecto que tenía la versión anterior: el código leía
    ``fila[0]`` sobre filas que en realidad eran diccionarios.
    """
    with base_datos.conexion() as conexion:
        fila = conexion.consultar_uno("SELECT nombrerol FROM rol WHERE idrol = ?", (1,))
    assert isinstance(fila, dict)
    assert fila["nombrerol"] == "Administrador"


def test_el_escalar_devuelve_el_valor_sin_indexar(base_datos):
    """Los conteos deben poder leerse sin depender de la posición de la columna."""
    with base_datos.conexion() as conexion:
        total = conexion.consultar_escalar("SELECT COUNT(*) FROM rol")
    assert total == 2


def test_insertar_devuelve_la_clave_generada(base_datos):
    """
    Insertar debe devolver la clave nueva en cualquier motor.

    PostgreSQL la obtiene con RETURNING y SQLite con lastrowid; la diferencia
    queda resuelta dentro de la conexión.
    """
    with base_datos.conexion() as conexion:
        identificador = conexion.insertar("marca", {"nombremarca": "Faber"}, "idmarca")
        conexion.confirmar()
    assert isinstance(identificador, int)
    assert identificador > 0

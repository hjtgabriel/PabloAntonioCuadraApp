"""
Pruebas de la abstracción de base de datos.

El hecho de que toda la batería corra sobre SQLite ya demuestra que el sistema
no depende de PostgreSQL. Estas pruebas verifican explícitamente las piezas que
hacen posible esa independencia, para que nadie las rompa sin darse cuenta.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

from nucleo.base_datos import MotorSQLite, cerrar_motor, configurar_motor
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


# ── Ninguna consulta se ata a un motor concreto ─────────────────────────

CONSTRUCCIONES_ATADAS = {
    "ILIKE": "solo existe en PostgreSQL; use dialecto.comparar_texto()",
    "SERIAL": "tipo de PostgreSQL; el esquema de cada motor va en docs/",
    "AUTOINCREMENT": "tipo de SQLite; el esquema de cada motor va en docs/",
    "NEXTVAL": "secuencias de PostgreSQL",
    "INTERVAL": "sintaxis de fechas de PostgreSQL; use dialecto.hace_dias()",
    "GETDATE": "sintaxis de SQL Server",
    "NOW()": "difiere entre motores; use CURRENT_TIMESTAMP",
    "::": "conversión de tipos propia de PostgreSQL",
    "%S": "marcador de PostgreSQL; escriba «?» y deje traducir al dialecto",
}

ARCHIVOS_DE_DATOS = [
    ruta
    for carpeta in ("modulos", "nucleo")
    for ruta in pathlib.Path(carpeta).rglob("*.py")
    if ruta.name != "dialecto.py"
]


def literales_sql(ruta: pathlib.Path) -> list[str]:
    """
    Extrae de un archivo los textos que parecen consultas SQL.

    Busca en los literales de cadena y no en el archivo entero para no
    confundirse con los «%s» de los mensajes del registro de eventos.

    Args:
        ruta: Archivo a inspeccionar.

    Returns:
        Los literales que contienen una sentencia SQL.
    """
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    palabras = ("SELECT ", "INSERT INTO", "UPDATE ", "DELETE FROM")
    return [
        nodo.value
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Constant)
        and isinstance(nodo.value, str)
        and any(palabra in nodo.value.upper() for palabra in palabras)
    ]


@pytest.mark.parametrize("ruta", ARCHIVOS_DE_DATOS, ids=lambda r: str(r))
def test_ninguna_consulta_usa_sintaxis_de_un_solo_motor(ruta):
    """
    Migrar de motor no debe obligar a reescribir consultas una por una.

    Todo lo que cambia entre motores vive en «nucleo/dialecto.py»: si una
    consulta usa ILIKE o INTERVAL directamente, ese punto único deja de serlo.
    """
    encontradas = [
        f"{construccion} ({motivo})"
        for sql in literales_sql(ruta)
        for construccion, motivo in CONSTRUCCIONES_ATADAS.items()
        if construccion in sql.upper()
    ]

    assert not encontradas, f"{ruta} ata su SQL a un motor: " + "; ".join(encontradas)


NOMBRES_DE_IDENTIFICADOR = frozenset({
    "condicion", "asignaciones", "marcadores", "tabla", "clave", "orden",
    "columnas", "alias", "prefijo",
    # Fragmentos que devuelve el dialecto, guardados en una variable para que
    # la consulta se lea mejor: «ahora = dialecto.ahora()».
    "ahora", "fecha",
})
"""
Variables locales que contienen nombres de tabla o fragmentos del dialecto.

Es una lista cerrada a propósito. Admitir «cualquier nombre corto» dejaba pasar
``f"... WHERE nombre = '{nombre}'"``, que es exactamente la inyección que esta
prueba debe cazar: comprobado introduciéndola.
"""

PATRONES_PERMITIDOS = (
    # Atributos y métodos del propio repositorio: self.tabla, self.clave,
    # self._lista_columnas(), dependencia.columna.
    re.compile(r"^self\.[A-Za-z_][A-Za-z0-9_]*(\(\))?$"),
    re.compile(r"^[a-z_]+\.(tabla|clave|columna|columna_nombre|columna_clave)$"),
    # El dialecto es el único autorizado a componer fragmentos de SQL: es
    # justamente la pieza que aísla lo que cambia entre motores.
    re.compile(r"^dialecto\.[a-z_]+\(.*\)$"),
    # Listas de nombres de columna unidas para un INSERT.
    re.compile(r"^'[,\s]*'\.join\([a-z_]+\)$"),
)
"""
Formas de interpolación admitidas dentro de una consulta.

Los nombres de tabla y de columna no pueden viajar como parámetro, así que no
queda otra que interpolarlos. Los **valores** sí pueden, y por eso deben.
"""


def _es_interpolacion_admitida(expresion: str) -> bool:
    """
    Indica si lo interpolado en una consulta es un identificador y no un valor.

    Args:
        expresion: Código fuente de lo que se interpola.

    Returns:
        True si es un nombre declarado como identificador o encaja con alguna
        de las formas autorizadas.
    """
    if expresion in NOMBRES_DE_IDENTIFICADOR:
        return True
    return any(patron.match(expresion) for patron in PATRONES_PERMITIDOS)


@pytest.mark.parametrize("ruta", ARCHIVOS_DE_DATOS, ids=lambda r: str(r))
def test_las_consultas_no_interpolan_valores(ruta):
    """
    Los valores viajan como parámetros, nunca dentro del texto de la consulta.

    Es a la vez la defensa contra la inyección SQL y lo que permite que el
    dialecto traduzca los marcadores al estilo de cada motor. Solo se admite
    interpolar identificadores que el propio repositorio define.
    """
    sospechosas = [
        f"línea {nodo.lineno}: {ast.unparse(trozo.value)}"
        for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8")))
        if isinstance(nodo, ast.JoinedStr) and _contiene_sql(nodo)
        for trozo in nodo.values
        if isinstance(trozo, ast.FormattedValue)
        and not _es_interpolacion_admitida(ast.unparse(trozo.value))
    ]

    assert not sospechosas, f"{ruta} interpola valores en el SQL: " + "; ".join(sospechosas)


def _contiene_sql(nodo: ast.JoinedStr) -> bool:
    """
    Indica si un literal con formato contiene una sentencia SQL.

    Args:
        nodo: Literal a revisar.

    Returns:
        True si alguna de sus partes fijas es SQL.
    """
    palabras = ("SELECT ", "INSERT INTO", "UPDATE ", "DELETE FROM", " WHERE ", " ORDER BY ")
    return any(
        isinstance(trozo, ast.Constant)
        and isinstance(trozo.value, str)
        and any(palabra in trozo.value.upper() for palabra in palabras)
        for trozo in nodo.values
    )


# ── Los tipos sobreviven al cambio de motor ─────────────────────────────


def test_el_booleano_del_rol_se_lee_igual_en_ambos_motores(base_datos):
    """
    SQLite no tiene BOOLEAN: guarda 0 y 1. PostgreSQL devuelve True y False.

    La marca «administra» decide los permisos del RF02, así que leerla mal en
    un motor dejaría al administrador sin acceso o se lo daría a un vendedor.
    """
    from modulos.personal.repositorio import UsuarioRepositorio
    from modulos.personal.servicios import ServicioUsuarios

    ServicioUsuarios().crear_con_empleado(
        {
            "nombres": "Ana",
            "apellidos": "López",
            "nombreusuario": "jefa",
            "contrasena": "clave-segura-1",
            "idrol": 1,
        }
    )

    sesion = UsuarioRepositorio().obtener_autenticado("jefa")

    assert isinstance(sesion.rol_administra, bool)
    assert sesion.es_administrador is True


# ── Añadir un motor nuevo no debe tocar el resto del código ──────────────


class DialectoFuturo(DialectoSQLite):
    """
    Dialecto de un motor hipotético.

    Hereda de SQLite para reusar su driver —lo que se prueba aquí no es el
    driver— pero declara su propio nombre y cambia una traducción, que es
    justo lo que distingue a un motor de otro.
    """

    nombre = "futuro"

    def comparar_texto(self, columna: str) -> str:
        """
        Compara sin distinguir mayúsculas con la sintaxis de este motor.

        Args:
            columna: Columna a comparar.

        Returns:
            Condición lista para la cláusula WHERE.
        """
        return f"LOWER({columna}) LIKE LOWER(?)"


class MotorFuturo(MotorSQLite):
    """Motor nuevo: lo único que declara es que usa su propio dialecto."""

    def __init__(self, ruta: str = ":memory:") -> None:
        """
        Args:
            ruta: Archivo de la base.
        """
        super().__init__(ruta)
        self._dialecto = DialectoFuturo()


@pytest.fixture
def motor_futuro():
    """
    Instala un motor recién inventado con el esquema de pruebas cargado.

    Yields:
        El motor activo para toda la aplicación.
    """
    from tests.conftest import ESQUEMA_PRUEBAS

    motor = MotorFuturo(":memory:")
    configurar_motor(motor)
    with motor.conexion() as conexion:
        conexion.driver.executescript(ESQUEMA_PRUEBAS)
        conexion.confirmar()

    yield motor

    cerrar_motor()
    configurar_motor(None)


def test_la_aplicacion_entera_corre_sobre_un_motor_nuevo(motor_futuro):
    """
    Migrar de base de datos debe costar dos clases y nada más.

    Esta prueba recorre el negocio completo —acceso, catálogo, búsqueda,
    filtros, inventario, venta, factura y reportes— sobre un motor que no
    existía al escribir ninguno de esos módulos. Si alguien ata una consulta a
    PostgreSQL, aquí se nota.
    """
    from decimal import Decimal

    from modulos.auth.servicios import ServicioAutenticacion
    from modulos.inventario.servicios import ServicioInventario
    from modulos.personal.servicios import ServicioUsuarios
    from modulos.productos.modelos import FiltroCatalogo
    from modulos.productos.servicios import ServicioProductos
    from modulos.reportes.servicios import ServicioReportes
    from modulos.ventas.factura import componer_html
    from modulos.ventas.servicios import ServicioVentas

    assert motor_futuro.dialecto.nombre == "futuro"

    idusuario = ServicioUsuarios().crear_con_empleado(
        {
            "nombres": "Ana",
            "apellidos": "López",
            "nombreusuario": "ana",
            "contrasena": "clave-segura-1",
            "idrol": 1,
        }
    )
    sesion = ServicioAutenticacion().iniciar_sesion("ana", "clave-segura-1")
    assert sesion.es_administrador is True

    productos = ServicioProductos()
    idproducto = productos.crear(
        {
            "descripcion": "Cuaderno Universitario",
            "idcategoria": 1,
            "idmarca": 1,
            "idproveedor": 1,
            "preciocompra": Decimal("20.00"),
            "precioventa": Decimal("100.00"),
            "stock": 10,
            "stockminimo": 2,
        }
    )
    assert len(productos.listar("cuaderno")) == 1
    assert len(productos.listar(filtro=FiltroCatalogo(idmarca=1))) == 1

    ServicioInventario().registrar_movimiento(idproducto, "Entrada", 5)
    assert productos.obtener(idproducto).stock == 15

    ventas = ServicioVentas()
    comprobante = ventas.registrar(
        idusuario, [{"idproducto": idproducto, "cantidad": 2}], "500.00"
    )

    productos.actualizar(idproducto, {"precioventa": Decimal("999.00")})
    venta = ventas.obtener_detalle(comprobante.idventa)
    assert sum(linea.subtotal for linea in venta.detalles) == venta.totalventa

    assert componer_html(venta, "Librería Pablo Antonio Cuadra", 80).startswith("<!DOCTYPE")

    reportes = ServicioReportes()
    assert reportes.ventas_semanales() != []
    assert reportes.articulos_mas_vendidos() != []

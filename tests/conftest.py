"""
Preparación común de las pruebas.

Las pruebas corren sobre SQLite en memoria a través del mismo
:class:`~nucleo.base_datos.Motor` que usa la aplicación en producción. Eso tiene
dos ventajas: no hace falta instalar PostgreSQL para probar, y de paso queda
comprobado que la capa de datos no depende de un motor concreto.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modulos.personal.servicios import ServicioUsuarios  # noqa: E402
from modulos.productos.servicios import ServicioProductos  # noqa: E402
from nucleo.base_datos import MotorSQLite, cerrar_motor, configurar_motor  # noqa: E402

ESQUEMA_PRUEBAS = """
CREATE TABLE rol (
    idrol      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombrerol  TEXT NOT NULL UNIQUE,
    administra INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE categoria (
    idcategoria INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT NOT NULL UNIQUE
);
CREATE TABLE marca (
    idmarca     INTEGER PRIMARY KEY AUTOINCREMENT,
    nombremarca TEXT NOT NULL UNIQUE
);
CREATE TABLE proveedor (
    idproveedor     INTEGER PRIMARY KEY AUTOINCREMENT,
    nombreproveedor TEXT NOT NULL UNIQUE,
    telefono        TEXT,
    direccion       TEXT
);
CREATE TABLE empleado (
    idempleado INTEGER PRIMARY KEY AUTOINCREMENT,
    nombres    TEXT NOT NULL,
    apellidos  TEXT NOT NULL,
    direccion  TEXT,
    telefono   TEXT
);
CREATE TABLE usuario (
    idusuario     INTEGER PRIMARY KEY AUTOINCREMENT,
    idempleado    INTEGER NOT NULL REFERENCES empleado(idempleado),
    idrol         INTEGER NOT NULL REFERENCES rol(idrol),
    nombreusuario TEXT NOT NULL UNIQUE,
    contrasena    TEXT NOT NULL
);
CREATE TABLE producto (
    idproducto   INTEGER PRIMARY KEY AUTOINCREMENT,
    descripcion  TEXT NOT NULL,
    idcategoria  INTEGER NOT NULL REFERENCES categoria(idcategoria),
    idmarca      INTEGER NOT NULL REFERENCES marca(idmarca),
    idproveedor  INTEGER NOT NULL REFERENCES proveedor(idproveedor),
    preciocompra NUMERIC NOT NULL DEFAULT 0,
    precioventa  NUMERIC NOT NULL DEFAULT 0,
    stock        INTEGER NOT NULL DEFAULT 0,
    stockminimo  INTEGER NOT NULL DEFAULT 5
);
CREATE TABLE historialprecios (
    idhistorial    INTEGER PRIMARY KEY AUTOINCREMENT,
    idproducto     INTEGER NOT NULL REFERENCES producto(idproducto),
    fechacambio    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    precioanterior NUMERIC NOT NULL,
    precionuevo    NUMERIC NOT NULL
);
CREATE TABLE inventario (
    idinventario    INTEGER PRIMARY KEY AUTOINCREMENT,
    idproducto      INTEGER NOT NULL REFERENCES producto(idproducto),
    fechamovimiento TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    tipomovimiento  TEXT NOT NULL,
    cantidad        INTEGER NOT NULL
);
CREATE TABLE venta (
    idventa          INTEGER PRIMARY KEY AUTOINCREMENT,
    idusuario        INTEGER NOT NULL REFERENCES usuario(idusuario),
    fechaventa       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    totalventa       NUMERIC NOT NULL,
    efectivorecibido NUMERIC NOT NULL,
    cambioentregado  NUMERIC NOT NULL
);
CREATE TABLE detalleventa (
    iddetalleventa INTEGER PRIMARY KEY AUTOINCREMENT,
    idventa        INTEGER NOT NULL REFERENCES venta(idventa),
    idproducto     INTEGER NOT NULL REFERENCES producto(idproducto),
    cantidad       INTEGER NOT NULL,
    preciounitario NUMERIC NOT NULL
);
INSERT INTO rol (nombrerol, administra) VALUES ('Administrador', 1), ('Vendedor', 0);
INSERT INTO categoria (nombre) VALUES ('Papelería'), ('Libros');
INSERT INTO marca (nombremarca) VALUES ('Genérica'), ('Norma');
INSERT INTO proveedor (nombreproveedor, telefono) VALUES ('Distribuidora Central', '22334455');
"""


@pytest.fixture
def base_datos():
    """
    Crea una base SQLite en memoria con el esquema y los catálogos mínimos.

    Yields:
        El motor instalado, ya activo para toda la aplicación.
    """
    motor = MotorSQLite(":memory:")
    configurar_motor(motor)

    with motor.conexion() as conexion:
        conexion.driver.executescript(ESQUEMA_PRUEBAS)
        conexion.confirmar()

    yield motor

    cerrar_motor()
    configurar_motor(None)


@pytest.fixture
def usuario_admin(base_datos) -> int:
    """
    Crea un usuario administrador de prueba.

    Returns:
        Clave del usuario creado.
    """
    return ServicioUsuarios().crear_con_empleado(
        {
            "nombres": "Ana",
            "apellidos": "Martínez",
            "nombreusuario": "admin",
            "contrasena": "clave-segura-1",
            "idrol": 1,
        }
    )


@pytest.fixture
def producto_demo(base_datos) -> int:
    """
    Crea un producto con 20 unidades en existencia.

    Returns:
        Clave del producto creado.
    """
    return ServicioProductos().crear(
        {
            "descripcion": "Cuaderno universitario",
            "idcategoria": 1,
            "idmarca": 1,
            "idproveedor": 1,
            "preciocompra": Decimal("20.00"),
            "precioventa": Decimal("35.50"),
            "stock": 20,
            "stockminimo": 5,
        }
    )

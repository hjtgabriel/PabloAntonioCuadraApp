-- ============================================================================
--  Librería Pablo Antonio Cuadra — Esquema de base de datos (PostgreSQL)
--
--  Ejecute este archivo una sola vez, sobre una base de datos vacía:
--      createdb PabloAntonioCuadraBD
--      psql -d PabloAntonioCuadraBD -f docs/esquema_postgresql.sql
--
--  Después cree el primer usuario administrador con:
--      python -m herramientas.crear_admin
-- ============================================================================

-- ── Catálogos independientes ────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS rol (
    idrol       SERIAL PRIMARY KEY,
    nombrerol   VARCHAR(50) NOT NULL UNIQUE,
    -- Quién administra es un dato del rol, no una convención sobre su nombre.
    -- Antes se deducía de que el nombre empezara por «admin», así que
    -- renombrar el rol a «Gerencia» dejaba a esa persona sin permisos y sin
    -- ningún aviso (RF02).
    administra  BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS categoria (
    idcategoria SERIAL PRIMARY KEY,
    nombre      VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS marca (
    idmarca     SERIAL PRIMARY KEY,
    nombremarca VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS proveedor (
    idproveedor     SERIAL PRIMARY KEY,
    nombreproveedor VARCHAR(150) NOT NULL UNIQUE,
    telefono        VARCHAR(20),
    direccion       VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS empleado (
    idempleado SERIAL PRIMARY KEY,
    nombres    VARCHAR(100) NOT NULL,
    apellidos  VARCHAR(100) NOT NULL,
    direccion  VARCHAR(255),
    telefono   VARCHAR(20)
);

-- ── Tablas con relaciones ───────────────────────────────────────────────

-- La contraseña guarda el hash PBKDF2-SHA256, nunca el texto plano (RNF04).
-- El formato es «pbkdf2_sha256$iteraciones$sal$hash», de unos 110 caracteres.
CREATE TABLE IF NOT EXISTS usuario (
    idusuario     SERIAL PRIMARY KEY,
    idempleado    INTEGER NOT NULL REFERENCES empleado(idempleado),
    idrol         INTEGER NOT NULL REFERENCES rol(idrol),
    nombreusuario VARCHAR(100) NOT NULL UNIQUE,
    contrasena    VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS producto (
    idproducto   SERIAL PRIMARY KEY,
    descripcion  VARCHAR(255) NOT NULL,
    idcategoria  INTEGER NOT NULL REFERENCES categoria(idcategoria),
    idmarca      INTEGER NOT NULL REFERENCES marca(idmarca),
    idproveedor  INTEGER NOT NULL REFERENCES proveedor(idproveedor),
    preciocompra NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (preciocompra >= 0),
    precioventa  NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (precioventa  >= 0),
    stock        INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
    stockminimo  INTEGER NOT NULL DEFAULT 5 CHECK (stockminimo >= 0)
);

CREATE TABLE IF NOT EXISTS historialprecios (
    idhistorial    SERIAL PRIMARY KEY,
    idproducto     INTEGER NOT NULL REFERENCES producto(idproducto),
    fechacambio    TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    precioanterior NUMERIC(18,2) NOT NULL,
    precionuevo    NUMERIC(18,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS inventario (
    idinventario    SERIAL PRIMARY KEY,
    idproducto      INTEGER NOT NULL REFERENCES producto(idproducto),
    fechamovimiento TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    tipomovimiento  VARCHAR(50) NOT NULL
        CHECK (tipomovimiento IN ('Entrada', 'Salida', 'Venta', 'Ajuste')),
    cantidad        INTEGER NOT NULL CHECK (cantidad >= 0)
);

CREATE TABLE IF NOT EXISTS venta (
    idventa          SERIAL PRIMARY KEY,
    idusuario        INTEGER NOT NULL REFERENCES usuario(idusuario),
    fechaventa       TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    totalventa       NUMERIC(18,2) NOT NULL CHECK (totalventa >= 0),
    efectivorecibido NUMERIC(18,2) NOT NULL CHECK (efectivorecibido >= 0),
    cambioentregado  NUMERIC(18,2) NOT NULL CHECK (cambioentregado >= 0)
);

CREATE TABLE IF NOT EXISTS detalleventa (
    iddetalleventa SERIAL PRIMARY KEY,
    idventa        INTEGER NOT NULL REFERENCES venta(idventa),
    idproducto     INTEGER NOT NULL REFERENCES producto(idproducto),
    cantidad       INTEGER NOT NULL CHECK (cantidad > 0),
    -- El precio pactado es un hecho de la venta, no del catálogo. Sin esta
    -- columna la factura se calculaba con el precio actual del producto, de
    -- modo que reimprimir una venta antigua tras un cambio de precio daba un
    -- documento que se contradecía con su propio total.
    preciounitario NUMERIC(18,2) NOT NULL CHECK (preciounitario >= 0)
);

-- ── Índices de apoyo ────────────────────────────────────────────────────
-- Sostienen la búsqueda por nombre (RF08) y los reportes (RF11-RF13) con
-- catálogos de 1.000 productos o más sin degradar el rendimiento (RNF07).

CREATE INDEX IF NOT EXISTS ix_producto_descripcion  ON producto (LOWER(descripcion));
CREATE INDEX IF NOT EXISTS ix_producto_categoria    ON producto (idcategoria);
CREATE INDEX IF NOT EXISTS ix_producto_marca        ON producto (idmarca);
CREATE INDEX IF NOT EXISTS ix_producto_proveedor    ON producto (idproveedor);
CREATE INDEX IF NOT EXISTS ix_producto_stock_bajo   ON producto (stock);

CREATE INDEX IF NOT EXISTS ix_venta_fecha           ON venta (fechaventa);
CREATE INDEX IF NOT EXISTS ix_venta_usuario         ON venta (idusuario);
CREATE INDEX IF NOT EXISTS ix_detalleventa_venta    ON detalleventa (idventa);
CREATE INDEX IF NOT EXISTS ix_detalleventa_producto ON detalleventa (idproducto);

CREATE INDEX IF NOT EXISTS ix_inventario_producto   ON inventario (idproducto, fechamovimiento DESC);
CREATE INDEX IF NOT EXISTS ix_historial_producto    ON historialprecios (idproducto, fechacambio DESC);

CREATE INDEX IF NOT EXISTS ix_usuario_empleado      ON usuario (idempleado);

-- ── Datos iniciales ─────────────────────────────────────────────────────
-- Los dos roles que exige el RF02. Se insertan solo si no existen.

INSERT INTO rol (nombrerol, administra)
SELECT 'Administrador', TRUE
WHERE NOT EXISTS (SELECT 1 FROM rol WHERE nombrerol = 'Administrador');

INSERT INTO rol (nombrerol, administra)
SELECT 'Vendedor', FALSE
WHERE NOT EXISTS (SELECT 1 FROM rol WHERE nombrerol = 'Vendedor');

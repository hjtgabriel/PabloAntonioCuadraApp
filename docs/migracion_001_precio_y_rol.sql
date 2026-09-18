-- ════════════════════════════════════════════════════════════════════════
--  Migración 001 — Precio pactado en la venta y marca de administración
-- ════════════════════════════════════════════════════════════════════════
--
--  Ejecútela UNA VEZ sobre una base ya creada con la versión anterior:
--
--      psql -d PabloAntonioCuadraBD -f docs/migracion_001_precio_y_rol.sql
--
--  Haga un respaldo antes:
--
--      python -m herramientas.respaldo_programado --tipo diario --sin-correo
--
--  Es idempotente: volver a ejecutarla no hace daño.
--
--  Qué corrige
--  ───────────
--  1. «detalleventa» no guardaba el precio de venta, así que la factura se
--     calculaba con el precio ACTUAL del producto. Reimprimir una venta
--     antigua después de cambiar precios daba un documento cuyas líneas no
--     sumaban su propio total.
--
--  2. Quién administra se deducía de que el nombre del rol empezara por
--     «admin». Renombrar «Administrador» a «Gerencia» dejaba a esa persona
--     sin permisos, en silencio (RF02).
-- ════════════════════════════════════════════════════════════════════════

BEGIN;

-- ── 1. Precio pactado en cada línea de venta ────────────────────────────

ALTER TABLE detalleventa ADD COLUMN IF NOT EXISTS preciounitario NUMERIC(18,2);

-- Para las ventas ya registradas no existe el precio de entonces: se pierde
-- con el diseño anterior. El precio actual del producto es la mejor
-- aproximación disponible, y a partir de aquí cada línea conserva el suyo.
UPDATE detalleventa d
   SET preciounitario = p.precioventa
  FROM producto p
 WHERE p.idproducto = d.idproducto
   AND d.preciounitario IS NULL;

ALTER TABLE detalleventa ALTER COLUMN preciounitario SET NOT NULL;

ALTER TABLE detalleventa DROP CONSTRAINT IF EXISTS detalleventa_precio_no_negativo;
ALTER TABLE detalleventa ADD CONSTRAINT detalleventa_precio_no_negativo
    CHECK (preciounitario >= 0);

-- ── 2. Marca de administración en el rol ────────────────────────────────

ALTER TABLE rol ADD COLUMN IF NOT EXISTS administra BOOLEAN NOT NULL DEFAULT FALSE;

-- Se respeta la convención anterior una sola vez, al migrar. De aquí en
-- adelante manda la columna y no el nombre.
UPDATE rol SET administra = TRUE WHERE LOWER(nombrerol) LIKE 'admin%';

COMMIT;

-- ── Comprobación ────────────────────────────────────────────────────────
-- Estas dos consultas deben devolver cero filas:
--
--   SELECT * FROM detalleventa WHERE preciounitario IS NULL;
--   SELECT * FROM rol WHERE administra IS NULL;

"""Acceso a datos de las tablas «producto» e «historialprecios»."""

from __future__ import annotations

from decimal import Decimal

from modulos.productos.modelos import CambioPrecio, FiltroCatalogo, Producto
from nucleo.base_datos import obtener_motor
from nucleo.repositorio import RepositorioBase

CONSULTA_PRODUCTOS_CON_RELACIONES = """
    SELECT p.idproducto, p.descripcion, p.idcategoria, p.idmarca, p.idproveedor,
           p.preciocompra, p.precioventa, p.stock, p.stockminimo,
           c.nombre AS categoria, m.nombremarca AS marca, pr.nombreproveedor AS proveedor
    FROM producto p
    LEFT JOIN categoria c ON p.idcategoria = c.idcategoria
    LEFT JOIN marca m ON p.idmarca = m.idmarca
    LEFT JOIN proveedor pr ON p.idproveedor = pr.idproveedor
"""


def condiciones_de_filtro(
    filtro: FiltroCatalogo | None, alias: str = "p"
) -> tuple[list[str], list[object]]:
    """
    Traduce un filtro de catálogo a condiciones SQL.

    Está aquí una sola vez porque las tres consultas que lo usan —catálogo,
    historial de precios e historial de inventario— acotan por los mismos dos
    campos del producto. El alias es parámetro porque cada consulta nombra la
    tabla «producto» a su manera.

    Args:
        filtro: Criterios a aplicar, o None para no acotar nada.
        alias: Alias con el que la consulta nombra la tabla «producto».

    Returns:
        Par (condiciones, parámetros) listo para unir con ``AND``.
    """
    if filtro is None or filtro.vacio:
        return [], []

    condiciones: list[str] = []
    parametros: list[object] = []
    if filtro.idcategoria is not None:
        condiciones.append(f"{alias}.idcategoria = ?")
        parametros.append(filtro.idcategoria)
    if filtro.idmarca is not None:
        condiciones.append(f"{alias}.idmarca = ?")
        parametros.append(filtro.idmarca)
    return condiciones, parametros


def agregar_condiciones(sql: str, condiciones: list[str]) -> str:
    """
    Añade a una consulta las condiciones acumuladas, si las hay.

    Args:
        sql: Consulta sin cláusula ``WHERE``.
        condiciones: Condiciones a exigir todas a la vez.

    Returns:
        La consulta con su ``WHERE``, o tal cual si no había condiciones.
    """
    if not condiciones:
        return sql
    return sql + " WHERE " + " AND ".join(condiciones)


class ProductoRepositorio(RepositorioBase[Producto]):
    """Operaciones sobre la tabla «producto»."""

    tabla = "producto"
    clave = "idproducto"
    columnas = (
        "descripcion",
        "idcategoria",
        "idmarca",
        "idproveedor",
        "preciocompra",
        "precioventa",
        "stock",
        "stockminimo",
    )

    def _a_entidad(self, fila: dict) -> Producto:
        """Convierte una fila de «producto» en entidad de dominio."""
        return Producto(
            idproducto=fila["idproducto"],
            descripcion=fila["descripcion"],
            idcategoria=fila["idcategoria"],
            idmarca=fila["idmarca"],
            idproveedor=fila["idproveedor"],
            preciocompra=_a_decimal(fila["preciocompra"]),
            precioventa=_a_decimal(fila["precioventa"]),
            stock=int(fila["stock"] or 0),
            stockminimo=int(fila["stockminimo"] or 0),
            categoria=fila.get("categoria"),
            marca=fila.get("marca"),
            proveedor=fila.get("proveedor"),
        )

    def _a_fila(self, entidad: Producto) -> dict:
        """Convierte la entidad en el diccionario a persistir."""
        return {
            "descripcion": entidad.descripcion,
            "idcategoria": entidad.idcategoria,
            "idmarca": entidad.idmarca,
            "idproveedor": entidad.idproveedor,
            "preciocompra": str(entidad.preciocompra),
            "precioventa": str(entidad.precioventa),
            "stock": entidad.stock,
            "stockminimo": entidad.stockminimo,
        }

    def buscar(
        self,
        texto: str | None = None,
        limite: int | None = None,
        desplazamiento: int | None = None,
        filtro: FiltroCatalogo | None = None,
    ) -> list[Producto]:
        """
        Lista productos con su categoría, marca y proveedor (RF08).

        Args:
            texto: Término de búsqueda parcial sobre la descripción.
            limite: Máximo de filas a traer; permite paginar catálogos
                grandes sin degradar el rendimiento (RNF07).
            desplazamiento: Filas a saltar antes de empezar.
            filtro: Acotación por marca y categoría; se combina con el texto.

        Returns:
            Productos ordenados por descripción.
        """
        condiciones, parametros = condiciones_de_filtro(filtro)

        if texto and texto.strip():
            condiciones.append(obtener_motor().dialecto.comparar_texto("p.descripcion"))
            parametros.append(f"%{texto.strip()}%")

        sql = agregar_condiciones(CONSULTA_PRODUCTOS_CON_RELACIONES, condiciones)
        sql += " ORDER BY p.descripcion"
        if limite is not None:
            sql += " LIMIT ?"
            parametros.append(limite)
        if desplazamiento is not None:
            sql += " OFFSET ?"
            parametros.append(desplazamiento)

        return [self._a_entidad(fila) for fila in self.consultar(sql, parametros)]

    def obtener_con_relaciones(self, idproducto: int) -> Producto | None:
        """
        Recupera un producto con los nombres de sus relaciones.

        Args:
            idproducto: Clave del producto.

        Returns:
            El producto, o None si no existe.
        """
        fila = self.consultar_uno(
            CONSULTA_PRODUCTOS_CON_RELACIONES + " WHERE p.idproducto = ?", (idproducto,)
        )
        return self._a_entidad(fila) if fila else None

    def listar_bajo_minimo(self) -> list[Producto]:
        """
        Devuelve los productos cuyo stock llegó al mínimo (RF07, RF13).

        Returns:
            Productos con stock crítico, del más escaso al menos escaso.
        """
        filas = self.consultar(
            CONSULTA_PRODUCTOS_CON_RELACIONES + " WHERE p.stock <= p.stockminimo ORDER BY p.stock ASC"
        )
        return [self._a_entidad(fila) for fila in filas]

    def ajustar_stock(self, idproducto: int, delta: int) -> int:
        """
        Suma (o resta) unidades al stock de un producto.

        Se resuelve con una sola sentencia ``UPDATE … stock = stock + ?`` para
        que la base de datos aplique el cambio de forma atómica, sin que dos
        ventas simultáneas puedan pisarse.

        Args:
            idproducto: Clave del producto.
            delta: Unidades a sumar; negativo para descontar.

        Returns:
            Cantidad de filas afectadas: 1 si se aplicó, 0 si no existe.
        """
        return self.ejecutar(
            "UPDATE producto SET stock = stock + ? WHERE idproducto = ?", (delta, idproducto)
        )

    def obtener_precio_y_stock(self, idproducto: int) -> dict | None:
        """
        Lee el precio de venta y las existencias de un producto.

        Args:
            idproducto: Clave del producto.

        Returns:
            Diccionario con «descripcion», «precioventa» y «stock», o None.
        """
        fila = self.consultar_uno(
            "SELECT descripcion, precioventa, stock FROM producto WHERE idproducto = ?",
            (idproducto,),
        )
        if fila is None:
            return None
        return {
            "descripcion": fila["descripcion"],
            "precioventa": _a_decimal(fila["precioventa"]),
            "stock": int(fila["stock"] or 0),
        }

    def contar_ventas(self, idproducto: int) -> int:
        """
        Cuenta en cuántos detalles de venta aparece el producto.

        Args:
            idproducto: Clave del producto.

        Returns:
            Cantidad de líneas de venta que lo referencian.
        """
        fila = self.consultar_uno(
            "SELECT COUNT(*) AS total FROM detalleventa WHERE idproducto = ?", (idproducto,)
        )
        return int(fila["total"]) if fila else 0


class HistorialPreciosRepositorio(RepositorioBase[CambioPrecio]):
    """Operaciones sobre la tabla «historialprecios» (RF06)."""

    tabla = "historialprecios"
    clave = "idhistorial"
    columnas = ("idproducto", "fechacambio", "precioanterior", "precionuevo")

    def _a_entidad(self, fila: dict) -> CambioPrecio:
        """Convierte una fila de «historialprecios» en entidad de dominio."""
        return CambioPrecio(
            idhistorial=fila["idhistorial"],
            idproducto=fila["idproducto"],
            fechacambio=fila["fechacambio"],
            precioanterior=_a_decimal(fila["precioanterior"]),
            precionuevo=_a_decimal(fila["precionuevo"]),
            descripcion=fila.get("descripcion"),
        )

    def _a_fila(self, entidad: CambioPrecio) -> dict:
        """Convierte la entidad en el diccionario a persistir."""
        return {
            "idproducto": entidad.idproducto,
            "precioanterior": str(entidad.precioanterior),
            "precionuevo": str(entidad.precionuevo),
        }

    def registrar(self, idproducto: int, anterior: Decimal, nuevo: Decimal) -> None:
        """
        Anota un cambio de precio con la fecha del servidor (RF06).

        Args:
            idproducto: Producto cuyo precio cambió.
            anterior: Precio que tenía antes.
            nuevo: Precio que queda vigente.
        """
        ahora = obtener_motor().dialecto.ahora()
        self.ejecutar(
            "INSERT INTO historialprecios "
            f"(idproducto, fechacambio, precioanterior, precionuevo) VALUES (?, {ahora}, ?, ?)",
            (idproducto, str(anterior), str(nuevo)),
        )

    def listar_historial(
        self, idproducto: int | None = None, filtro: FiltroCatalogo | None = None
    ) -> list[CambioPrecio]:
        """
        Lista los cambios de precio, del más reciente al más antiguo (RF06).

        Args:
            idproducto: Si se indica, limita el historial a ese producto.
            filtro: Acotación por marca y categoría del producto.

        Returns:
            Cambios de precio con el nombre del producto incluido.
        """
        sql = """
            SELECT h.idhistorial, h.idproducto, p.descripcion, h.fechacambio,
                   h.precioanterior, h.precionuevo
            FROM historialprecios h
            JOIN producto p ON h.idproducto = p.idproducto
        """
        condiciones, parametros = condiciones_de_filtro(filtro)
        if idproducto is not None:
            condiciones.append("h.idproducto = ?")
            parametros.append(idproducto)

        sql = agregar_condiciones(sql, condiciones)
        sql += " ORDER BY h.fechacambio DESC, h.idhistorial DESC"

        return [self._a_entidad(fila) for fila in self.consultar(sql, parametros)]


def _a_decimal(valor: object) -> Decimal:
    """
    Convierte a ``Decimal`` un valor monetario leído de la base de datos.

    Pasa siempre por ``str`` para no heredar el error de redondeo que tendría
    un ``float`` intermedio.

    Args:
        valor: Valor tal como lo devolvió el driver.

    Returns:
        El importe como ``Decimal``; cero si el valor era nulo.
    """
    if valor is None:
        return Decimal("0")
    return Decimal(str(valor))

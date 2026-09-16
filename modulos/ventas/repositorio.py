"""Acceso a datos de las tablas «venta» y «detalleventa»."""

from __future__ import annotations

from decimal import Decimal

from modulos.ventas.modelos import DetalleVenta, Venta
from nucleo.base_datos import obtener_motor
from nucleo.repositorio import RepositorioBase

CONSULTA_VENTAS = """
    SELECT v.idventa, v.idusuario, u.nombreusuario, v.fechaventa,
           v.totalventa, v.efectivorecibido, v.cambioentregado
    FROM venta v
    JOIN usuario u ON v.idusuario = u.idusuario
"""


class VentaRepositorio(RepositorioBase[Venta]):
    """Operaciones sobre la tabla «venta»."""

    tabla = "venta"
    clave = "idventa"
    columnas = (
        "idusuario",
        "fechaventa",
        "totalventa",
        "efectivorecibido",
        "cambioentregado",
    )

    def _a_entidad(self, fila: dict) -> Venta:
        """Convierte una fila de «venta» en entidad de dominio."""
        return Venta(
            idventa=fila["idventa"],
            idusuario=fila["idusuario"],
            fechaventa=fila["fechaventa"],
            totalventa=_a_decimal(fila["totalventa"]),
            efectivorecibido=_a_decimal(fila["efectivorecibido"]),
            cambioentregado=_a_decimal(fila["cambioentregado"]),
            nombreusuario=fila.get("nombreusuario"),
        )

    def _a_fila(self, entidad: Venta) -> dict:
        """Convierte la entidad en el diccionario a persistir."""
        return {
            "idusuario": entidad.idusuario,
            "totalventa": str(entidad.totalventa),
            "efectivorecibido": str(entidad.efectivorecibido),
            "cambioentregado": str(entidad.cambioentregado),
        }

    def registrar_cabecera(
        self, idusuario: int, total: Decimal, efectivo: Decimal, cambio: Decimal
    ) -> int:
        """
        Inserta la cabecera de la venta con la fecha del servidor.

        Args:
            idusuario: Usuario que registra la venta.
            total: Importe total cobrado.
            efectivo: Efectivo recibido.
            cambio: Cambio entregado.

        Returns:
            Clave primaria de la venta creada.
        """
        ahora = obtener_motor().dialecto.ahora()
        sql = (
            "INSERT INTO venta (idusuario, fechaventa, totalventa, efectivorecibido, cambioentregado) "
            f"VALUES (?, {ahora}, ?, ?, ?)"
        )
        dialecto = obtener_motor().dialecto
        parametros = (idusuario, str(total), str(efectivo), str(cambio))

        if dialecto.soporta_returning:
            fila = self.consultar_uno(sql + " RETURNING idventa", parametros)
            return int(fila["idventa"])

        self.ejecutar(sql, parametros)
        fila = self.consultar_uno("SELECT MAX(idventa) AS idventa FROM venta")
        return int(fila["idventa"])

    def registrar_detalle(self, idventa: int, idproducto: int, cantidad: int) -> None:
        """
        Inserta una línea de la venta.

        Args:
            idventa: Venta a la que pertenece.
            idproducto: Producto vendido.
            cantidad: Unidades vendidas.
        """
        self.ejecutar(
            "INSERT INTO detalleventa (idventa, idproducto, cantidad) VALUES (?, ?, ?)",
            (idventa, idproducto, cantidad),
        )

    def listar_recientes(self, limite: int | None = None) -> list[Venta]:
        """
        Lista las ventas con el nombre del vendedor, de la más reciente a la más antigua.

        Args:
            limite: Máximo de ventas a traer.

        Returns:
            Ventas ordenadas por fecha descendente.
        """
        sql = CONSULTA_VENTAS + " ORDER BY v.fechaventa DESC, v.idventa DESC"
        parametros: tuple = ()
        if limite is not None:
            sql += " LIMIT ?"
            parametros = (limite,)
        return [self._a_entidad(fila) for fila in self.consultar(sql, parametros)]

    def obtener_con_detalle(self, idventa: int) -> Venta | None:
        """
        Recupera una venta junto con sus líneas.

        Args:
            idventa: Clave de la venta.

        Returns:
            La venta con sus detalles, o None si no existe.
        """
        fila = self.consultar_uno(CONSULTA_VENTAS + " WHERE v.idventa = ?", (idventa,))
        if fila is None:
            return None

        venta = self._a_entidad(fila)
        venta.detalles = self.listar_detalles(idventa)
        return venta

    def listar_detalles(self, idventa: int) -> list[DetalleVenta]:
        """
        Devuelve las líneas de una venta con su subtotal.

        Args:
            idventa: Clave de la venta.

        Returns:
            Líneas de la venta.
        """
        filas = self.consultar(
            """
            SELECT d.iddetalleventa, d.idventa, d.idproducto, d.cantidad,
                   p.descripcion, p.precioventa,
                   (d.cantidad * p.precioventa) AS subtotal
            FROM detalleventa d
            JOIN producto p ON d.idproducto = p.idproducto
            WHERE d.idventa = ?
            ORDER BY d.iddetalleventa
            """,
            (idventa,),
        )
        return [
            DetalleVenta(
                iddetalleventa=fila["iddetalleventa"],
                idventa=fila["idventa"],
                idproducto=fila["idproducto"],
                cantidad=int(fila["cantidad"]),
                descripcion=fila.get("descripcion"),
                precioventa=_a_decimal(fila["precioventa"]),
                subtotal=_a_decimal(fila["subtotal"]),
            )
            for fila in filas
        ]

    def eliminar_detalles(self, idventa: int) -> int:
        """
        Borra todas las líneas de una venta.

        Args:
            idventa: Clave de la venta.

        Returns:
            Cantidad de líneas borradas.
        """
        return self.ejecutar("DELETE FROM detalleventa WHERE idventa = ?", (idventa,))


def _a_decimal(valor: object) -> Decimal:
    """
    Convierte a ``Decimal`` un importe leído de la base de datos.

    Args:
        valor: Valor tal como lo devolvió el driver.

    Returns:
        El importe como ``Decimal``; cero si el valor era nulo.
    """
    if valor is None:
        return Decimal("0")
    return Decimal(str(valor))

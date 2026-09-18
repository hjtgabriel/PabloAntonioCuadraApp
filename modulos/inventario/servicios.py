"""
Reglas de negocio del inventario (RF04, RF05, RF07).

Este módulo es el **único** lugar donde se mueve el stock. Antes la misma
operación estaba copiada en el repositorio de productos y en el de inventario,
de modo que al corregir una quedaba mal la otra, y además la vista llamaba a
una tercera función que anotaba el movimiento sin descontar existencias.

Aquí toda variación de stock pasa por ``registrar_movimiento``, que en una sola
transacción ajusta las existencias y deja el asiento en el historial.
"""

from __future__ import annotations

import logging

from modulos.inventario.modelos import Movimiento, TipoMovimiento
from modulos.inventario.repositorio import InventarioRepositorio
from modulos.productos.modelos import FiltroCatalogo, Producto
from modulos.productos.repositorio import ProductoRepositorio
from nucleo.base_datos import Conexion, transaccion
from nucleo.errores import ErrorNoEncontrado, ErrorStockInsuficiente, ErrorValidacion

logger = logging.getLogger(__name__)


class ServicioInventario:
    """Movimientos de stock y alertas de reabastecimiento."""

    def __init__(self, conexion: Conexion | None = None) -> None:
        """
        Args:
            conexion: Conexión de una transacción en curso, si la hay.
        """
        self._conexion = conexion
        self._repositorio = InventarioRepositorio(conexion)
        self._productos = ProductoRepositorio(conexion)

    def registrar_movimiento(self, idproducto: int, tipo: str | TipoMovimiento, cantidad: int) -> int:
        """
        Ajusta el stock de un producto y anota el movimiento (RF04, RF05).

        Las dos escrituras ocurren en la misma transacción: si el asiento falla,
        el stock vuelve atrás, y viceversa.

        Cuando el movimiento resta, el descuento y su comprobación van en una
        sola sentencia. Comprobar antes en Python y escribir después dejaba una
        ventana por la que dos ventas simultáneas de la última unidad pasaban
        las dos.

        Args:
            idproducto: Producto a mover.
            tipo: «Entrada», «Salida», «Venta» o «Ajuste». En un ajuste, la
                cantidad es el stock final deseado, no la diferencia.
            cantidad: Unidades, siempre en positivo.

        Returns:
            El stock que queda tras aplicar el movimiento.

        Raises:
            ErrorValidacion: Si el tipo o la cantidad son inválidos.
            ErrorNoEncontrado: Si el producto no existe.
            ErrorStockInsuficiente: Si la operación dejaría el stock negativo.
        """
        movimiento = _validar_tipo(tipo)
        cantidad_valida = _validar_cantidad(cantidad, movimiento)

        with transaccion(self._conexion) as conexion:
            productos = ProductoRepositorio(conexion)
            inventario = InventarioRepositorio(conexion)

            actual = productos.buscar_por_id(idproducto)
            if actual is None:
                raise ErrorNoEncontrado(f"No existe el producto {idproducto}")

            delta = self._calcular_delta(movimiento, cantidad_valida, actual)
            stock_final = actual.stock + delta

            if delta < 0:
                if not productos.descontar_stock(idproducto, -delta):
                    raise ErrorStockInsuficiente(
                        f"No hay existencias suficientes de «{actual.descripcion}»: "
                        f"hay {actual.stock} y se intentan retirar {abs(delta)}"
                    )
            elif delta > 0:
                productos.ajustar_stock(idproducto, delta)
            inventario.anotar(idproducto, movimiento.value, cantidad_valida)

            logger.info(
                "Movimiento %s de %d unidades en el producto %d; stock %d → %d",
                movimiento.value, cantidad_valida, idproducto, actual.stock, stock_final,
            )
            return stock_final

    def listar_historial(
        self, idproducto: int | None = None, filtro: FiltroCatalogo | None = None
    ) -> list[Movimiento]:
        """
        Devuelve el historial de movimientos (RF05).

        Args:
            idproducto: Si se indica, limita el historial a ese producto.
            filtro: Acotación por marca y categoría del producto.

        Returns:
            Movimientos del más reciente al más antiguo.
        """
        return self._repositorio.listar_historial(idproducto, filtro)

    def listar_alertas_stock(self) -> list[Producto]:
        """
        Devuelve los productos que alcanzaron su stock mínimo (RF07).

        Returns:
            Productos con existencias críticas, del más escaso al menos escaso.
        """
        return self._productos.listar_bajo_minimo()

    @staticmethod
    def _calcular_delta(tipo: TipoMovimiento, cantidad: int, producto: Producto) -> int:
        """
        Traduce un movimiento a la variación que hay que aplicar al stock.

        Args:
            tipo: Clase de movimiento.
            cantidad: Unidades del movimiento (o stock final, si es un ajuste).
            producto: Producto con sus existencias actuales.

        Returns:
            Unidades a sumar al stock; negativo si hay que descontar.
        """
        if tipo is TipoMovimiento.AJUSTE:
            return cantidad - producto.stock
        return cantidad if tipo.suma_stock else -cantidad


def _validar_tipo(tipo: str | TipoMovimiento) -> TipoMovimiento:
    """
    Normaliza el tipo de movimiento recibido.

    Args:
        tipo: Tipo como texto o como enumerado.

    Returns:
        El tipo de movimiento.

    Raises:
        ErrorValidacion: Si el texto no corresponde a ningún tipo conocido.
    """
    if isinstance(tipo, TipoMovimiento):
        return tipo
    try:
        return TipoMovimiento.desde_texto(tipo)
    except ValueError as error:
        raise ErrorValidacion(str(error)) from error


def _validar_cantidad(cantidad: object, tipo: TipoMovimiento) -> int:
    """
    Comprueba que la cantidad sea un entero admisible para el tipo.

    Un ajuste puede fijar el stock en cero; los demás movimientos exigen al
    menos una unidad.

    Args:
        cantidad: Cantidad recibida de la interfaz.
        tipo: Clase de movimiento.

    Returns:
        La cantidad como entero.

    Raises:
        ErrorValidacion: Si no es un número o está fuera de rango.
    """
    try:
        valor = int(cantidad)
    except (TypeError, ValueError) as error:
        raise ErrorValidacion("La cantidad debe ser un número entero") from error

    minimo = 0 if tipo is TipoMovimiento.AJUSTE else 1
    if valor < minimo:
        raise ErrorValidacion(
            "El stock final de un ajuste no puede ser negativo"
            if tipo is TipoMovimiento.AJUSTE
            else "La cantidad debe ser mayor que cero"
        )
    return valor

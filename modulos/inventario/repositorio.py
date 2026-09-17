"""Acceso a datos de la tabla «inventario»."""

from __future__ import annotations

from modulos.inventario.modelos import Movimiento
from modulos.productos.modelos import FiltroCatalogo
from modulos.productos.repositorio import agregar_condiciones, condiciones_de_filtro
from nucleo.base_datos import obtener_motor
from nucleo.repositorio import RepositorioBase


class InventarioRepositorio(RepositorioBase[Movimiento]):
    """Operaciones sobre la tabla «inventario» (RF05)."""

    tabla = "inventario"
    clave = "idinventario"
    columnas = ("idproducto", "fechamovimiento", "tipomovimiento", "cantidad")

    def _a_entidad(self, fila: dict) -> Movimiento:
        """Convierte una fila de «inventario» en entidad de dominio."""
        return Movimiento(
            idinventario=fila["idinventario"],
            idproducto=fila["idproducto"],
            fechamovimiento=fila["fechamovimiento"],
            tipomovimiento=fila["tipomovimiento"],
            cantidad=int(fila["cantidad"] or 0),
            descripcion=fila.get("descripcion"),
        )

    def _a_fila(self, entidad: Movimiento) -> dict:
        """Convierte la entidad en el diccionario a persistir."""
        return {
            "idproducto": entidad.idproducto,
            "tipomovimiento": entidad.tipomovimiento,
            "cantidad": entidad.cantidad,
        }

    def anotar(self, idproducto: int, tipo: str, cantidad: int) -> None:
        """
        Deja constancia de un movimiento con la fecha del servidor (RF05).

        No toca el stock: de eso se encarga el servicio, que hace ambas cosas
        dentro de una misma transacción.

        Args:
            idproducto: Producto afectado.
            tipo: Clase de movimiento.
            cantidad: Unidades involucradas, en positivo.
        """
        ahora = obtener_motor().dialecto.ahora()
        self.ejecutar(
            "INSERT INTO inventario "
            f"(idproducto, fechamovimiento, tipomovimiento, cantidad) VALUES (?, {ahora}, ?, ?)",
            (idproducto, tipo, cantidad),
        )

    def listar_historial(
        self, idproducto: int | None = None, filtro: FiltroCatalogo | None = None
    ) -> list[Movimiento]:
        """
        Lista los movimientos, del más reciente al más antiguo (RF05).

        Args:
            idproducto: Si se indica, limita el historial a ese producto.
            filtro: Acotación por marca y categoría del producto.

        Returns:
            Movimientos con el nombre del producto incluido.
        """
        sql = """
            SELECT i.idinventario, i.idproducto, p.descripcion,
                   i.fechamovimiento, i.tipomovimiento, i.cantidad
            FROM inventario i
            JOIN producto p ON i.idproducto = p.idproducto
        """
        condiciones, parametros = condiciones_de_filtro(filtro)
        if idproducto is not None:
            condiciones.append("i.idproducto = ?")
            parametros.append(idproducto)

        sql = agregar_condiciones(sql, condiciones)
        sql += " ORDER BY i.fechamovimiento DESC, i.idinventario DESC"

        return [self._a_entidad(fila) for fila in self.consultar(sql, parametros)]

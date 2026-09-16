"""Acceso a datos de la tabla «proveedor»."""

from __future__ import annotations

from modulos.proveedores.modelos import Proveedor
from nucleo.base_datos import obtener_motor
from nucleo.repositorio import RepositorioBase


class ProveedorRepositorio(RepositorioBase[Proveedor]):
    """Operaciones de lectura y escritura sobre «proveedor»."""

    tabla = "proveedor"
    clave = "idproveedor"
    columnas = ("nombreproveedor", "telefono", "direccion")

    def _a_entidad(self, fila: dict) -> Proveedor:
        """Convierte una fila de «proveedor» en entidad de dominio."""
        return Proveedor(
            idproveedor=fila["idproveedor"],
            nombreproveedor=fila["nombreproveedor"],
            telefono=fila.get("telefono"),
            direccion=fila.get("direccion"),
        )

    def _a_fila(self, entidad: Proveedor) -> dict:
        """Convierte la entidad en el diccionario a persistir (sin la clave)."""
        return {
            "nombreproveedor": entidad.nombreproveedor,
            "telefono": entidad.telefono,
            "direccion": entidad.direccion,
        }

    def buscar(self, texto: str | None = None) -> list[Proveedor]:
        """
        Lista proveedores, opcionalmente filtrados por nombre o teléfono (RF08).

        Args:
            texto: Término de búsqueda parcial.

        Returns:
            Proveedores ordenados por nombre.
        """
        if not texto or not texto.strip():
            return self.listar(orden="nombreproveedor")

        dialecto = obtener_motor().dialecto
        patron = f"%{texto.strip()}%"
        condicion = (
            f"({dialecto.comparar_texto('nombreproveedor')} "
            f"OR {dialecto.comparar_texto('telefono')})"
        )
        return self.listar(condicion, (patron, patron), orden="nombreproveedor")

    def existe_nombre(self, nombre: str, excluir_id: int | None = None) -> bool:
        """
        Indica si otro proveedor ya usa ese nombre.

        Args:
            nombre: Nombre a verificar.
            excluir_id: Clave a ignorar, para no chocar consigo misma al editar.

        Returns:
            True si el nombre está tomado.
        """
        condicion = obtener_motor().dialecto.comparar_texto("nombreproveedor")
        parametros: list[object] = [nombre.strip()]
        if excluir_id is not None:
            condicion += " AND idproveedor <> ?"
            parametros.append(excluir_id)
        return self.contar(condicion, parametros) > 0

    def contar_productos(self, idproveedor: int) -> int:
        """
        Cuenta cuántos productos surte este proveedor.

        Args:
            idproveedor: Clave del proveedor.

        Returns:
            Cantidad de productos asociados.
        """
        fila = self.consultar_uno(
            "SELECT COUNT(*) AS total FROM producto WHERE idproveedor = ?", (idproveedor,)
        )
        return int(fila["total"]) if fila else 0

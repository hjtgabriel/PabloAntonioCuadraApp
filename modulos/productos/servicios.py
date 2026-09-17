"""
Reglas de negocio del catálogo de productos (RF03, RF06, RF07, RF08).

Al crear o modificar un producto, este servicio coordina tres escrituras que
deben ocurrir juntas o no ocurrir: la fila del producto, el asiento de entrada
de inventario por el stock inicial y el registro del cambio de precio. Todas
comparten la misma conexión, así que una falla revierte el conjunto.
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from modulos.inventario.modelos import TipoMovimiento
from modulos.inventario.servicios import ServicioInventario
from modulos.productos.modelos import (
    STOCK_MINIMO_POR_OMISION,
    CambioPrecio,
    FiltroCatalogo,
    Producto,
)
from modulos.productos.repositorio import HistorialPreciosRepositorio, ProductoRepositorio
from nucleo.base_datos import Conexion, transaccion
from nucleo.errores import ErrorEnUso, ErrorNoEncontrado, ErrorValidacion

logger = logging.getLogger(__name__)

LONGITUD_MINIMA_DESCRIPCION = 2
CAMPOS_OBLIGATORIOS = (
    ("descripcion", "La descripción"),
    ("idcategoria", "La categoría"),
    ("idmarca", "La marca"),
    ("idproveedor", "El proveedor"),
)


class ServicioProductos:
    """Alta, baja, modificación y consulta de productos."""

    def __init__(self, conexion: Conexion | None = None) -> None:
        """
        Args:
            conexion: Conexión de una transacción en curso, si la hay.
        """
        self._conexion = conexion
        self._repositorio = ProductoRepositorio(conexion)
        self._historial = HistorialPreciosRepositorio(conexion)

    # ── Consultas ───────────────────────────────────────────────

    def listar(
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
            limite: Máximo de filas, para paginar catálogos grandes (RNF07).
            desplazamiento: Filas a saltar antes de empezar.
            filtro: Acotación por marca y categoría; se suma a la búsqueda por
                texto en vez de sustituirla.

        Returns:
            Productos ordenados por descripción.
        """
        return self._repositorio.buscar(texto, limite, desplazamiento, filtro)

    def obtener(self, idproducto: int) -> Producto:
        """
        Recupera un producto por su clave.

        Args:
            idproducto: Clave del producto.

        Returns:
            El producto con los nombres de sus relaciones.

        Raises:
            ErrorNoEncontrado: Si el producto no existe.
        """
        producto = self._repositorio.obtener_con_relaciones(idproducto)
        if producto is None:
            raise ErrorNoEncontrado("No se encontró el producto solicitado")
        return producto

    def listar_historial_precios(
        self, idproducto: int | None = None, filtro: FiltroCatalogo | None = None
    ) -> list[CambioPrecio]:
        """
        Devuelve la evolución de precios registrada (RF06).

        Args:
            idproducto: Si se indica, limita el historial a ese producto.
            filtro: Acotación por marca y categoría del producto.

        Returns:
            Cambios de precio del más reciente al más antiguo.
        """
        return self._historial.listar_historial(idproducto, filtro)

    # ── Escrituras ──────────────────────────────────────────────

    def crear(self, datos: dict) -> int:
        """
        Da de alta un producto (RF03).

        Si se indica un stock inicial mayor que cero, queda registrado como un
        movimiento de entrada para que el historial de inventario cuadre desde
        el primer día (RF05).

        Args:
            datos: Campos del formulario de producto.

        Returns:
            Clave primaria generada.

        Raises:
            ErrorValidacion: Si falta un campo obligatorio o un importe es inválido.
        """
        producto = self._construir(0, datos)

        with transaccion(self._conexion) as conexion:
            repositorio = ProductoRepositorio(conexion)
            idproducto = repositorio.insertar(
                Producto(
                    idproducto=0,
                    descripcion=producto.descripcion,
                    idcategoria=producto.idcategoria,
                    idmarca=producto.idmarca,
                    idproveedor=producto.idproveedor,
                    preciocompra=producto.preciocompra,
                    precioventa=producto.precioventa,
                    stock=0,
                    stockminimo=producto.stockminimo,
                )
            )

            if producto.stock > 0:
                ServicioInventario(conexion).registrar_movimiento(
                    idproducto, TipoMovimiento.ENTRADA, producto.stock
                )

            logger.info("Producto creado: %s (clave %d)", producto.descripcion, idproducto)
            return idproducto

    def actualizar(self, idproducto: int, datos: dict) -> bool:
        """
        Modifica un producto existente (RF03).

        Cuando cambia el precio de venta, el cambio queda anotado en el
        historial dentro de la misma transacción (RF06). El stock no se toca
        aquí: solo se mueve por inventario o por una venta.

        Args:
            idproducto: Clave del producto.
            datos: Campos a cambiar; los ausentes conservan su valor actual.

        Returns:
            True si se guardó el cambio.

        Raises:
            ErrorNoEncontrado: Si el producto no existe.
            ErrorValidacion: Si algún campo resulta inválido.
        """
        actual = self._repositorio.buscar_por_id(idproducto)
        if actual is None:
            raise ErrorNoEncontrado("No se encontró el producto solicitado")

        combinados = self._combinar_con_actual(actual, datos)
        nuevo = self._construir(idproducto, combinados)
        nuevo.stock = actual.stock

        with transaccion(self._conexion) as conexion:
            repositorio = ProductoRepositorio(conexion)
            guardado = repositorio.actualizar(idproducto, nuevo)

            if nuevo.precioventa != actual.precioventa:
                HistorialPreciosRepositorio(conexion).registrar(
                    idproducto, actual.precioventa, nuevo.precioventa
                )
                logger.info(
                    "Precio del producto %d: %s → %s",
                    idproducto, actual.precioventa, nuevo.precioventa,
                )
            return guardado

    def eliminar(self, idproducto: int) -> bool:
        """
        Borra un producto que nunca se haya vendido.

        Args:
            idproducto: Clave del producto.

        Returns:
            True si se borró.

        Raises:
            ErrorNoEncontrado: Si el producto no existe.
            ErrorEnUso: Si aparece en alguna venta; borrarlo rompería los
                reportes históricos (RF11, RF12).
        """
        if not self._repositorio.existe(idproducto):
            raise ErrorNoEncontrado("No se encontró el producto solicitado")
        if self._repositorio.contar_ventas(idproducto) > 0:
            raise ErrorEnUso(
                "No se puede eliminar: el producto tiene ventas registradas y "
                "los reportes históricos dejarían de cuadrar."
            )

        with transaccion(self._conexion) as conexion:
            conexion.ejecutar("DELETE FROM historialprecios WHERE idproducto = ?", (idproducto,))
            conexion.ejecutar("DELETE FROM inventario WHERE idproducto = ?", (idproducto,))
            return conexion.ejecutar("DELETE FROM producto WHERE idproducto = ?", (idproducto,)) > 0

    # ── Apoyo interno ───────────────────────────────────────────

    @staticmethod
    def _combinar_con_actual(actual: Producto, datos: dict) -> dict:
        """
        Mezcla los campos del formulario con los valores vigentes.

        Args:
            actual: Producto tal como está guardado.
            datos: Campos que envió el formulario.

        Returns:
            Diccionario completo listo para validar.
        """
        return {
            "descripcion": datos.get("descripcion", actual.descripcion),
            "idcategoria": datos.get("idcategoria", actual.idcategoria),
            "idmarca": datos.get("idmarca", actual.idmarca),
            "idproveedor": datos.get("idproveedor", actual.idproveedor),
            "preciocompra": datos.get("preciocompra", actual.preciocompra),
            "precioventa": datos.get("precioventa", actual.precioventa),
            "stock": actual.stock,
            "stockminimo": datos.get("stockminimo", actual.stockminimo),
        }

    @staticmethod
    def _construir(idproducto: int, datos: dict) -> Producto:
        """
        Valida y normaliza los campos de un producto.

        Args:
            idproducto: Clave a asignar a la entidad.
            datos: Campos recibidos de la interfaz.

        Returns:
            La entidad lista para persistir.

        Raises:
            ErrorValidacion: Si falta un campo obligatorio (RF03) o si algún
                importe o cantidad es inválido.
        """
        for campo, etiqueta in CAMPOS_OBLIGATORIOS:
            if datos.get(campo) in (None, ""):
                raise ErrorValidacion(f"{etiqueta} es obligatoria")

        descripcion = str(datos["descripcion"]).strip()
        if len(descripcion) < LONGITUD_MINIMA_DESCRIPCION:
            raise ErrorValidacion(
                f"La descripción debe tener al menos {LONGITUD_MINIMA_DESCRIPCION} caracteres"
            )

        return Producto(
            idproducto=idproducto,
            descripcion=descripcion,
            idcategoria=_a_entero(datos["idcategoria"], "La categoría"),
            idmarca=_a_entero(datos["idmarca"], "La marca"),
            idproveedor=_a_entero(datos["idproveedor"], "El proveedor"),
            preciocompra=_a_importe(datos.get("preciocompra", 0), "El precio de compra"),
            precioventa=_a_importe(datos.get("precioventa", 0), "El precio de venta"),
            stock=_a_entero(datos.get("stock", 0), "El stock", minimo=0),
            stockminimo=_a_entero(
                datos.get("stockminimo", STOCK_MINIMO_POR_OMISION), "El stock mínimo", minimo=0
            ),
        )


def _a_entero(valor: object, etiqueta: str, minimo: int = 1) -> int:
    """
    Convierte un campo del formulario a entero validando su rango.

    Args:
        valor: Valor recibido, normalmente como texto.
        etiqueta: Nombre del campo para el mensaje de error.
        minimo: Valor mínimo aceptado.

    Returns:
        El valor como entero.

    Raises:
        ErrorValidacion: Si no es un número o queda por debajo del mínimo.
    """
    try:
        numero = int(str(valor).strip())
    except (TypeError, ValueError) as error:
        raise ErrorValidacion(f"{etiqueta} debe ser un número entero") from error
    if numero < minimo:
        raise ErrorValidacion(f"{etiqueta} no puede ser menor que {minimo}")
    return numero


def _a_importe(valor: object, etiqueta: str) -> Decimal:
    """
    Convierte un campo del formulario a importe monetario.

    Args:
        valor: Valor recibido, normalmente como texto.
        etiqueta: Nombre del campo para el mensaje de error.

    Returns:
        El importe como ``Decimal`` con dos decimales.

    Raises:
        ErrorValidacion: Si no es un número o es negativo.
    """
    try:
        importe = Decimal(str(valor).strip() or "0")
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ErrorValidacion(f"{etiqueta} debe ser un número válido") from error
    if importe < 0:
        raise ErrorValidacion(f"{etiqueta} no puede ser negativo")
    return importe.quantize(Decimal("0.01"))

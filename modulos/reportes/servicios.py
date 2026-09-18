"""
Reportes de gestión (RF11, RF12, RF13).

Son consultas de solo lectura con agregados. Toda la sintaxis que cambia entre
motores —recortar una marca de tiempo a fecha, restar días— se pide al dialecto
en vez de escribirla a mano, así que estos reportes funcionan igual sobre
PostgreSQL que sobre cualquier otro motor que se soporte en el futuro.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from nucleo.base_datos import Conexion, obtener_motor
from nucleo.formato import a_decimal
from nucleo.repositorio import RepositorioBase

DIAS_SEMANA = 7
TOP_VENDIDOS = 10

ESTADO_CRITICO = "Crítico"
ESTADO_BAJO = "Bajo"
ESTADO_NORMAL = "Normal"


@dataclass(slots=True)
class VentaDiaria:
    """
    Resumen de las ventas de un día (RF11).

    Attributes:
        fecha: Día al que corresponde el resumen.
        cantidad_ventas: Número de tiquetes emitidos.
        total_vendido: Importe total facturado.
        total_efectivo: Efectivo recibido en total.
        total_cambio: Cambio entregado en total.
    """

    fecha: date
    cantidad_ventas: int
    total_vendido: Decimal
    total_efectivo: Decimal
    total_cambio: Decimal


@dataclass(slots=True)
class ArticuloVendido:
    """
    Artículo con su volumen de ventas acumulado (RF12).

    Attributes:
        descripcion: Nombre del producto.
        marca: Marca del producto.
        categoria: Categoría del producto.
        unidades: Unidades vendidas en total.
        importe: Importe facturado por ese producto.
    """

    descripcion: str
    marca: str
    categoria: str
    unidades: int
    importe: Decimal


@dataclass(slots=True)
class NivelStock:
    """
    Situación de existencias de un producto (RF13).

    Attributes:
        idproducto: Clave del producto.
        descripcion: Nombre del producto.
        marca: Marca del producto.
        categoria: Categoría del producto.
        stock: Existencias actuales.
        stockminimo: Umbral de reabastecimiento.
        estado: «Crítico», «Bajo» o «Normal».
    """

    idproducto: int
    descripcion: str
    marca: str
    categoria: str
    stock: int
    stockminimo: int
    estado: str

    @property
    def unidades_a_reponer(self) -> int:
        """Cuántas unidades faltan para volver al doble del mínimo."""
        objetivo = self.stockminimo * 2
        return max(0, objetivo - self.stock)


class _ConsultaReportes(RepositorioBase[dict]):
    """
    Repositorio de solo lectura para los reportes.

    Declara una tabla nominal porque no hace CRUD: solo aprovecha la maquinaria
    de conexiones y de consulta del repositorio base.
    """

    tabla = "venta"
    clave = "idventa"
    columnas = ("idusuario",)

    def _a_entidad(self, fila: dict) -> dict:
        """Los reportes trabajan con filas planas, sin entidad de dominio."""
        return dict(fila)

    def _a_fila(self, entidad: dict) -> dict:
        """No aplica: este repositorio nunca escribe."""
        raise NotImplementedError("Los reportes son de solo lectura")


class ServicioReportes:
    """Consultas agregadas para la toma de decisiones."""

    def __init__(self, conexion: Conexion | None = None) -> None:
        """
        Args:
            conexion: Conexión de una transacción en curso, si la hay.
        """
        self._consulta = _ConsultaReportes(conexion)

    def ventas_semanales(self, dias: int = DIAS_SEMANA) -> list[VentaDiaria]:
        """
        Resume las ventas de los últimos días, incluido efectivo y cambio (RF11).

        Args:
            dias: Ventana de días hacia atrás a considerar.

        Returns:
            Un resumen por día, del más antiguo al más reciente.
        """
        dialecto = obtener_motor().dialecto
        fecha = dialecto.solo_fecha("v.fechaventa")
        sql = f"""
            SELECT {fecha} AS fecha,
                   COUNT(*) AS cantidad_ventas,
                   SUM(v.totalventa) AS total_vendido,
                   SUM(v.efectivorecibido) AS total_efectivo,
                   SUM(v.cambioentregado) AS total_cambio
            FROM venta v
            WHERE {fecha} >= {dialecto.hace_dias(dias)}
            GROUP BY {fecha}
            ORDER BY fecha
        """
        return [
            VentaDiaria(
                fecha=fila["fecha"],
                cantidad_ventas=int(fila["cantidad_ventas"] or 0),
                total_vendido=a_decimal(fila["total_vendido"]),
                total_efectivo=a_decimal(fila["total_efectivo"]),
                total_cambio=a_decimal(fila["total_cambio"]),
            )
            for fila in self._consulta.consultar(sql)
        ]

    def articulos_mas_vendidos(self, limite: int = TOP_VENDIDOS) -> list[ArticuloVendido]:
        """
        Lista los artículos con mayor volumen de ventas (RF12).

        Args:
            limite: Cuántos artículos devolver.

        Returns:
            Artículos ordenados por unidades vendidas, de mayor a menor.
        """
        sql = """
            SELECT p.descripcion,
                   m.nombremarca AS marca,
                   c.nombre AS categoria,
                   SUM(d.cantidad) AS unidades,
                   SUM(d.cantidad * p.precioventa) AS importe
            FROM detalleventa d
            JOIN producto p ON d.idproducto = p.idproducto
            JOIN marca m ON p.idmarca = m.idmarca
            JOIN categoria c ON p.idcategoria = c.idcategoria
            GROUP BY p.descripcion, m.nombremarca, c.nombre
            ORDER BY unidades DESC
            LIMIT ?
        """
        return [
            ArticuloVendido(
                descripcion=fila["descripcion"],
                marca=fila["marca"],
                categoria=fila["categoria"],
                unidades=int(fila["unidades"] or 0),
                importe=a_decimal(fila["importe"]),
            )
            for fila in self._consulta.consultar(sql, (limite,))
        ]

    def niveles_stock(self) -> list[NivelStock]:
        """
        Reporta el stock actual de cada producto para decidir reposiciones (RF13).

        La clasificación en «Crítico», «Bajo» y «Normal» se calcula en Python en
        lugar de con un CASE en SQL: es la misma regla de negocio del RF07 y
        conviene que viva en un solo sitio.

        Returns:
            Productos ordenados de menor a mayor existencia.
        """
        sql = """
            SELECT p.idproducto, p.descripcion,
                   m.nombremarca AS marca, c.nombre AS categoria,
                   p.stock, p.stockminimo
            FROM producto p
            JOIN marca m ON p.idmarca = m.idmarca
            JOIN categoria c ON p.idcategoria = c.idcategoria
            ORDER BY p.stock ASC
        """
        return [
            NivelStock(
                idproducto=fila["idproducto"],
                descripcion=fila["descripcion"],
                marca=fila["marca"],
                categoria=fila["categoria"],
                stock=int(fila["stock"] or 0),
                stockminimo=int(fila["stockminimo"] or 0),
                estado=_clasificar_stock(int(fila["stock"] or 0), int(fila["stockminimo"] or 0)),
            )
            for fila in self._consulta.consultar(sql)
        ]


def _clasificar_stock(stock: int, minimo: int) -> str:
    """
    Clasifica el nivel de existencias de un producto.

    Args:
        stock: Existencias actuales.
        minimo: Umbral de reabastecimiento.

    Returns:
        «Crítico» si llegó o bajó del mínimo, «Bajo» si no supera el doble del
        mínimo, «Normal» en cualquier otro caso.
    """
    if stock <= minimo:
        return ESTADO_CRITICO
    if stock <= minimo * 2:
        return ESTADO_BAJO
    return ESTADO_NORMAL

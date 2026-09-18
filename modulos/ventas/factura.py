"""
Factura imprimible de una venta (RF09, RF11).

Flet 0.86.5 no sabe imprimir: no hay control ni servicio que abra el diálogo de
impresión del sistema. La salida es por tanto un documento HTML que se abre en
el navegador, donde el usuario imprime con Ctrl+P y, si quiere, guarda como
PDF. Se eligió así frente a generar un PDF porque no añade ninguna dependencia
al proyecto y funciona igual en cualquier equipo del local.

El documento está maquetado para una **impresora de tickets**, no para una
hoja: ``@page`` declara el ancho del rollo y alto automático, de modo que el
papel se corta donde termina la factura en vez de expulsar una página entera.
De ahí vienen el resto de las decisiones: una sola columna, tipografía
monoespaciada para que los importes queden alineados, y ni un solo fondo de
color, que en una térmica no se imprime y solo gasta tinta en otras.

El ancho se pasa como parámetro porque los rollos habituales son de 80 mm y de
58 mm, y la maqueta cambia por completo entre uno y otro.

El módulo solo **compone** el documento: no escribe en disco ni abre nada. Eso
lo hace la capa de presentación, y gracias a la separación la factura se puede
comprobar en las pruebas comparando texto, sin abrir ventanas.
"""

from __future__ import annotations

from html import escape
from math import ceil

from modulos.ventas.modelos import DetalleVenta, Venta
from nucleo.formato import FORMATO_FECHA_LARGA, fecha, importe

ANCHO_ROLLO_MM = 80
"""Ancho de rollo por omisión; es el habitual en un punto de venta de mostrador."""

MARGEN_ROLLO_MM = 3
"""Margen a cada lado: las térmicas no imprimen hasta el borde del papel."""

ALTO_BASE_MM = 70
"""
Alto de lo que no depende ni de la venta ni del ancho del rollo.

Cubre la fecha, el vendedor, la cabecera de la tabla, las separaciones, los
cuatro totales, el pie y los márgenes.
"""

ANCHO_CARACTER_TITULO_MM = 2.1
"""Ancho de un carácter del nombre del negocio, que va en cuerpo mayor."""

ALTO_LINEA_MM = 5
"""Alto de una línea de texto de la tabla, con su espaciado."""

ANCHO_CARACTER_MM = 1.75
"""Ancho de un carácter de la tipografía monoespaciada del ticket."""

ANCHO_COLUMNAS_FIJAS_MM = 28
"""Lo que ocupan la cantidad y el importe, que no se ajustan a varias líneas."""


def nombre_archivo(venta: Venta) -> str:
    """
    Propone el nombre del archivo de una factura.

    Lleva el número de venta y la fecha para que las facturas de un mismo día
    no se pisen entre sí y queden ordenadas al listar la carpeta.

    Args:
        venta: Venta a facturar.

    Returns:
        Nombre de archivo, sin carpeta.
    """
    return f"factura_{venta.idventa:05d}_{venta.fechaventa:%Y%m%d_%H%M%S}.html"


def componer_html(venta: Venta, nombre_negocio: str, ancho_mm: int = ANCHO_ROLLO_MM) -> str:
    """
    Arma el documento HTML de la factura, a la medida del rollo.

    Args:
        venta: Venta con sus líneas ya cargadas.
        nombre_negocio: Encabezado del documento.
        ancho_mm: Ancho del rollo de la impresora, en milímetros.

    Returns:
        Documento HTML completo, listo para guardar y abrir.
    """
    return _PLANTILLA.format(
        titulo=escape(f"Factura {venta.idventa}"),
        negocio=escape(nombre_negocio),
        numero=f"{venta.idventa:05d}",
        fecha=escape(fecha(venta.fechaventa, FORMATO_FECHA_LARGA)),
        vendedor=escape(venta.nombreusuario or "—"),
        filas=_filas(venta),
        total=importe(venta.totalventa),
        efectivo=importe(venta.efectivorecibido),
        cambio=importe(venta.cambioentregado),
        articulos=_total_articulos(venta),
        ancho=ancho_mm,
        alto=alto_mm(venta, nombre_negocio, ancho_mm),
        margen=MARGEN_ROLLO_MM,
    )


def alto_mm(venta: Venta, nombre_negocio: str, ancho_mm: int = ANCHO_ROLLO_MM) -> int:
    """
    Calcula el alto de papel que necesita la factura.

    ``@page`` exige una medida concreta: ``size: 80mm auto`` es sintaxis
    inválida —no se puede mezclar una longitud con ``auto``— y el navegador la
    descarta entera, con lo que el ticket saldría en tamaño carta.

    Cuenta las líneas de verdad, no los artículos: un nombre largo se ajusta a
    dos o tres renglones en un papel estrecho. Estimarlo por artículo dejaba la
    página corta y la factura se partía en dos, con lo que el cliente se
    llevaba medio comprobante.

    Se redondea hacia arriba a propósito: pasarse gasta unos milímetros de
    papel, que es el error barato de los dos.

    Args:
        venta: Venta a facturar.
        nombre_negocio: Encabezado del documento; en un rollo estrecho ocupa
            más de un renglón y hay que contarlo. No tiene valor por omisión a
            propósito: omitirlo daba un alto silenciosamente corto.
        ancho_mm: Ancho del rollo, que decide cuánto texto entra por línea.

    Returns:
        El alto en milímetros.
    """
    lineas_titulo = _lineas_de_texto(nombre_negocio, ancho_mm, ANCHO_CARACTER_TITULO_MM, 0)
    lineas_articulos = sum(_lineas_de(detalle, ancho_mm) for detalle in venta.detalles)
    renglones = lineas_titulo + max(lineas_articulos, 2)
    return ALTO_BASE_MM + renglones * ALTO_LINEA_MM


def _lineas_de(detalle: DetalleVenta, ancho_mm: int) -> int:
    """
    Cuenta los renglones que ocupará un artículo en el ticket.

    Args:
        detalle: Línea de la venta.
        ancho_mm: Ancho del rollo.

    Returns:
        Los renglones del nombre más el del precio unitario.
    """
    nombre = detalle.descripcion or "—"
    lineas = _lineas_de_texto(
        nombre, ancho_mm, ANCHO_CARACTER_MM, ANCHO_COLUMNAS_FIJAS_MM
    )
    return lineas + 1


def _lineas_de_texto(texto: str, ancho_mm: int, ancho_caracter_mm: float, ocupado_mm: int) -> int:
    """
    Estima en cuántos renglones se parte un texto dentro del rollo.

    Args:
        texto: Texto a medir.
        ancho_mm: Ancho del rollo.
        ancho_caracter_mm: Ancho de un carácter en el cuerpo que se use.
        ocupado_mm: Ancho que roban otras columnas de la misma fila.

    Returns:
        Los renglones que ocupará, nunca menos de uno.
    """
    disponible_mm = max(ancho_mm - 2 * MARGEN_ROLLO_MM - ocupado_mm, 10)
    por_linea = max(int(disponible_mm / ancho_caracter_mm), 8)
    return max(ceil(len(texto) / por_linea), 1)


def _filas(venta: Venta) -> str:
    """
    Arma las filas de la tabla de artículos.

    Args:
        venta: Venta con sus líneas.

    Returns:
        Las filas en HTML, o una fila de aviso si la venta no trae detalle.
    """
    if not venta.detalles:
        return '<tr><td colspan="3" class="vacio">Esta venta no tiene detalle</td></tr>'

    return "\n".join(
        "<tr>"
        f'<td class="cant">{detalle.cantidad}</td>'
        f"<td>{escape(detalle.descripcion or '—')}"
        f'<br><span class="unitario">{importe(detalle.precioventa)} c/u</span></td>'
        f'<td class="num">{importe(detalle.subtotal)}</td>'
        "</tr>"
        for detalle in venta.detalles
    )


def _total_articulos(venta: Venta) -> str:
    """
    Cuenta las unidades vendidas, no las líneas.

    Args:
        venta: Venta con sus líneas.

    Returns:
        El total de unidades como texto.
    """
    return str(sum(detalle.cantidad for detalle in venta.detalles))


_PLANTILLA = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>{titulo}</title>
<style>
  /* El papel se declara a la medida de esta factura, no de una hoja: asi la
     termica corta donde termina el ticket. El alto lo calcula alto_mm(). */
  @page {{ size: {ancho}mm {alto}mm; margin: 0; }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px; line-height: 1.35; color: #000;
    margin: 0 auto; padding: {margen}mm; width: {ancho}mm;
    background: #fff;
  }}
  h1 {{ font-size: 13px; margin: 0; text-align: center; text-transform: uppercase; }}
  .datos {{ text-align: center; font-size: 11px; margin: 6px 0 10px; }}
  hr {{ border: 0; border-top: 1px dashed #000; margin: 6px 0; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 11px; }}
  th {{ text-align: left; font-weight: 700; padding: 2px 0; font-size: 10px; }}
  td {{ padding: 3px 0; vertical-align: top; }}
  .cant {{ width: 22px; text-align: right; padding-right: 6px; }}
  .num {{ text-align: right; white-space: nowrap; padding-left: 6px; }}
  .unitario {{ font-size: 10px; }}
  .vacio {{ text-align: center; font-style: italic; }}
  .totales {{ width: 100%; font-size: 12px; margin-top: 4px; }}
  .totales div {{ display: flex; justify-content: space-between; padding: 2px 0; }}
  .totales .total {{ font-size: 14px; font-weight: 700; padding: 5px 0; }}
  .pie {{ text-align: center; font-size: 11px; margin: 10px 0 0; }}
  .imprimir {{ text-align: center; margin-bottom: 8px; }}
  button {{ font: inherit; padding: 6px 14px; cursor: pointer; }}
  /* En papel no se imprime ni el boton ni un solo fondo de color: una
     impresora termica no los reproduce y en otra solo gastarian tinta. */
  @media print {{
    body {{ width: auto; padding: 0 {margen}mm; }}
    .imprimir {{ display: none; }}
  }}
</style>
</head>
<body>
  <div class="imprimir"><button onclick="window.print()">Imprimir</button></div>
  <h1>{negocio}</h1>
  <div class="datos">
    Factura N.&ordm; <strong>{numero}</strong><br>
    {fecha}<br>
    Atendido por: {vendedor}
  </div>
  <hr>
  <table>
    <thead>
      <tr><th class="cant">Cant</th><th>Producto</th><th class="num">Importe</th></tr>
    </thead>
    <tbody>
{filas}
    </tbody>
  </table>
  <hr>
  <div class="totales">
    <div><span>Art&iacute;culos</span><span>{articulos}</span></div>
    <div class="total"><span>TOTAL</span><span>{total}</span></div>
    <div><span>Efectivo</span><span>{efectivo}</span></div>
    <div><span>Cambio</span><span>{cambio}</span></div>
  </div>
  <hr>
  <p class="pie">&iexcl;Gracias por su compra!</p>
</body>
</html>
"""

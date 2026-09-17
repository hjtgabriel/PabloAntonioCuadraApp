"""
Factura imprimible de una venta (RF09, RF11).

Flet 0.86.5 no sabe imprimir: no hay control ni servicio que abra el diálogo de
impresión del sistema. La salida es por tanto un documento HTML que se abre en
el navegador, donde el usuario imprime con Ctrl+P y, si quiere, guarda como
PDF. Se eligió así frente a generar un PDF porque no añade ninguna dependencia
al proyecto y funciona igual en cualquier equipo del local.

El módulo solo **compone** el documento: no escribe en disco ni abre nada. Eso
lo hace la capa de presentación, y gracias a la separación la factura se puede
comprobar en las pruebas comparando texto, sin abrir ventanas.
"""

from __future__ import annotations

from decimal import Decimal
from html import escape

from modulos.ventas.modelos import Venta

MONEDA = "C$"
FORMATO_FECHA = "%d/%m/%Y %H:%M"


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


def componer_html(venta: Venta, nombre_negocio: str) -> str:
    """
    Arma el documento HTML de la factura.

    Args:
        venta: Venta con sus líneas ya cargadas.
        nombre_negocio: Encabezado del documento.

    Returns:
        Documento HTML completo, listo para guardar y abrir.
    """
    return _PLANTILLA.format(
        titulo=escape(f"Factura {venta.idventa}"),
        negocio=escape(nombre_negocio),
        numero=f"{venta.idventa:05d}",
        fecha=escape(venta.fechaventa.strftime(FORMATO_FECHA)),
        vendedor=escape(venta.nombreusuario or "—"),
        filas=_filas(venta),
        total=_importe(venta.totalventa),
        efectivo=_importe(venta.efectivorecibido),
        cambio=_importe(venta.cambioentregado),
        articulos=_total_articulos(venta),
    )


def _filas(venta: Venta) -> str:
    """
    Arma las filas de la tabla de artículos.

    Args:
        venta: Venta con sus líneas.

    Returns:
        Las filas en HTML, o una fila de aviso si la venta no trae detalle.
    """
    if not venta.detalles:
        return '<tr><td colspan="4" class="vacio">Esta venta no tiene detalle</td></tr>'

    return "\n".join(
        "<tr>"
        f"<td class=\"num\">{detalle.cantidad}</td>"
        f"<td>{escape(detalle.descripcion or '—')}</td>"
        f"<td class=\"num\">{_importe(detalle.precioventa)}</td>"
        f"<td class=\"num\">{_importe(detalle.subtotal)}</td>"
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


def _importe(valor: Decimal | None) -> str:
    """
    Da formato de moneda a un importe.

    Args:
        valor: Importe a mostrar; None se trata como cero.

    Returns:
        El importe con el símbolo de córdobas y dos decimales.
    """
    return f"{MONEDA} {Decimal(str(valor or 0)):,.2f}"


_PLANTILLA = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>{titulo}</title>
<style>
  :root {{ --tinta: #2b2b2b; --suave: #777; --linea: #d9d2c4; }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: "Segoe UI", Roboto, Arial, sans-serif;
    color: var(--tinta); margin: 0; padding: 32px;
    display: flex; justify-content: center; background: #f4efe4;
  }}
  .factura {{ width: 100%; max-width: 620px; background: #fff; padding: 36px; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; letter-spacing: .5px; }}
  .datos {{ color: var(--suave); font-size: 13px; margin-bottom: 24px; }}
  .datos strong {{ color: var(--tinta); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th {{
    text-align: left; border-bottom: 2px solid var(--linea);
    padding: 8px 6px; font-size: 12px; text-transform: uppercase;
    letter-spacing: .4px; color: var(--suave);
  }}
  td {{ padding: 8px 6px; border-bottom: 1px solid var(--linea); }}
  .num {{ text-align: right; white-space: nowrap; }}
  .vacio {{ text-align: center; color: var(--suave); font-style: italic; }}
  .totales {{ margin-top: 20px; margin-left: auto; width: 260px; font-size: 14px; }}
  .totales div {{ display: flex; justify-content: space-between; padding: 5px 6px; }}
  .totales .total {{
    border-top: 2px solid var(--linea); border-bottom: 1px solid var(--linea);
    margin: 6px 0 8px; padding: 10px 6px; font-size: 17px; font-weight: 700;
  }}
  .pie {{ margin-top: 32px; text-align: center; color: var(--suave); font-size: 12px; }}
  .imprimir {{ text-align: center; margin-bottom: 20px; }}
  button {{
    font: inherit; padding: 9px 22px; cursor: pointer;
    border: 0; border-radius: 6px; background: #7b1020; color: #fff;
  }}
  @media print {{
    body {{ background: #fff; padding: 0; }}
    .factura {{ max-width: none; padding: 0; }}
    .imprimir {{ display: none; }}
  }}
</style>
</head>
<body>
<div class="factura">
  <div class="imprimir"><button onclick="window.print()">Imprimir</button></div>
  <h1>{negocio}</h1>
  <div class="datos">
    Factura N.&ordm; <strong>{numero}</strong><br>
    Fecha: <strong>{fecha}</strong><br>
    Atendido por: <strong>{vendedor}</strong>
  </div>
  <table>
    <thead>
      <tr><th>Cant.</th><th>Producto</th><th class="num">Precio</th><th class="num">Subtotal</th></tr>
    </thead>
    <tbody>
{filas}
    </tbody>
  </table>
  <div class="totales">
    <div><span>Art&iacute;culos</span><span>{articulos}</span></div>
    <div class="total"><span>TOTAL</span><span>{total}</span></div>
    <div><span>Efectivo recibido</span><span>{efectivo}</span></div>
    <div><span>Cambio entregado</span><span>{cambio}</span></div>
  </div>
  <p class="pie">&iexcl;Gracias por su compra!</p>
</div>
</body>
</html>
"""

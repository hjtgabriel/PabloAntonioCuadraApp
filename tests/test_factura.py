"""
Pruebas de la factura imprimible (RF09, RF11).

La factura es un documento que sale del local en manos del cliente, así que lo
que importa es lo que dice: el número de venta, cada artículo con su importe y
unos totales que cuadren. Componer el documento está separado de guardarlo y
abrirlo justamente para poder comprobarlo aquí comparando texto, sin escribir
en disco ni abrir ventanas.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from modulos.ventas.factura import componer_html, nombre_archivo
from modulos.ventas.modelos import DetalleVenta, Venta
from modulos.ventas.servicios import ServicioVentas
from nucleo.documentos import ErrorDocumento, guardar

NEGOCIO = "Librería Pablo Antonio Cuadra"


def venta_de_prueba(detalles: list[DetalleVenta] | None = None) -> Venta:
    """
    Arma una venta completa sin tocar la base de datos.

    Args:
        detalles: Líneas a incluir; si se omite, se usan dos de ejemplo.

    Returns:
        La venta lista para facturar.
    """
    if detalles is None:
        detalles = [
            DetalleVenta(
                iddetalleventa=1,
                idventa=42,
                idproducto=7,
                cantidad=2,
                descripcion="Cuaderno universitario",
                precioventa=Decimal("35.50"),
                subtotal=Decimal("71.00"),
            ),
            DetalleVenta(
                iddetalleventa=2,
                idventa=42,
                idproducto=9,
                cantidad=1,
                descripcion="Folder Manila",
                precioventa=Decimal("96.96"),
                subtotal=Decimal("96.96"),
            ),
        ]
    return Venta(
        idventa=42,
        idusuario=1,
        fechaventa=datetime(2026, 9, 17, 15, 4, 30),
        totalventa=Decimal("167.96"),
        efectivorecibido=Decimal("200.00"),
        cambioentregado=Decimal("32.04"),
        nombreusuario="CarminAd",
        detalles=detalles,
    )


# ── Contenido del documento ─────────────────────────────────────────────


def test_la_factura_lleva_el_numero_la_fecha_y_el_vendedor():
    """Son los datos que permiten localizar la venta después."""
    html = componer_html(venta_de_prueba(), NEGOCIO)

    assert "00042" in html
    assert "17/09/2026 15:04" in html
    assert "CarminAd" in html
    assert NEGOCIO in html


def test_la_factura_detalla_cada_articulo():
    """El cliente revisa línea por línea antes de llevarse el comprobante."""
    html = componer_html(venta_de_prueba(), NEGOCIO)

    assert "Cuaderno universitario" in html
    assert "Folder Manila" in html
    assert "C$ 71.00" in html
    assert "C$ 96.96" in html


def test_la_factura_muestra_los_totales():
    """Total, efectivo y cambio son lo que se coteja contra la caja."""
    html = componer_html(venta_de_prueba(), NEGOCIO)

    assert "C$ 167.96" in html
    assert "C$ 200.00" in html
    assert "C$ 32.04" in html


def test_la_factura_cuenta_unidades_y_no_lineas():
    """Dos cuadernos y un folder son tres artículos, no dos."""
    html = componer_html(venta_de_prueba(), NEGOCIO)

    assert ">3<" in html.replace(" ", "").replace("\n", "")


def test_la_factura_es_un_documento_html_completo():
    """Tiene que abrirse sola en el navegador, no ser un fragmento."""
    html = componer_html(venta_de_prueba(), NEGOCIO)

    assert html.lstrip().startswith("<!DOCTYPE html>")
    assert 'lang="es"' in html
    assert 'charset="utf-8"' in html
    assert html.rstrip().endswith("</html>")


def test_la_factura_trae_su_propio_boton_de_imprimir():
    """Se imprime desde el navegador, así que el botón va en el documento."""
    html = componer_html(venta_de_prueba(), NEGOCIO)

    assert "window.print()" in html
    assert "@media print" in html


def test_una_venta_sin_detalle_no_rompe_la_factura():
    """Un dato incompleto no puede dejar al vendedor sin comprobante."""
    html = componer_html(venta_de_prueba(detalles=[]), NEGOCIO)

    assert "no tiene detalle" in html
    assert "C$ 167.96" in html


def test_la_factura_escapa_lo_que_viene_de_la_base():
    """
    Un nombre con «<» no debe romper el documento ni inyectar etiquetas.

    Los nombres de producto los escribe el usuario, así que pueden traer
    cualquier carácter.
    """
    detalle = DetalleVenta(
        iddetalleventa=1,
        idventa=42,
        idproducto=7,
        cantidad=1,
        descripcion='Lápiz <b>"2B"</b>',
        precioventa=Decimal("10.00"),
        subtotal=Decimal("10.00"),
    )

    html = componer_html(venta_de_prueba(detalles=[detalle]), NEGOCIO)

    assert "<b>" not in html.split("<tbody>")[1].split("</tbody>")[0]
    assert "&lt;b&gt;" in html


def test_un_vendedor_desconocido_no_deja_un_hueco():
    """Si la consulta no trajo el nombre, la factura lo dice con un guion."""
    venta = venta_de_prueba()
    venta.nombreusuario = None

    assert "Atendido por: <strong>—</strong>" in componer_html(venta, NEGOCIO)


# ── Nombre del archivo ──────────────────────────────────────────────────


def test_el_archivo_lleva_numero_y_fecha():
    """Así las facturas de un mismo día no se pisan y quedan ordenadas."""
    assert nombre_archivo(venta_de_prueba()) == "factura_00042_20260917_150430.html"


def test_dos_ventas_distintas_no_comparten_archivo():
    """Guardar una factura nunca debe sobrescribir otra."""
    primera = venta_de_prueba()
    segunda = venta_de_prueba()
    segunda.idventa = 43

    assert nombre_archivo(primera) != nombre_archivo(segunda)


# ── Guardado del documento ──────────────────────────────────────────────


def test_guardar_crea_la_carpeta_si_no_existe(tmp_path):
    """La carpeta de facturas no existe hasta la primera venta."""
    destino = tmp_path / "facturas" / "del-año"

    ruta = guardar("<html></html>", destino, "factura.html")

    assert ruta.exists()
    assert ruta.read_text(encoding="utf-8") == "<html></html>"


def test_guardar_conserva_los_acentos(tmp_path):
    """El documento se escribe en UTF-8: «Librería» no puede salir rota."""
    ruta = guardar(componer_html(venta_de_prueba(), NEGOCIO), tmp_path, "f.html")

    assert "Librería" in ruta.read_text(encoding="utf-8")


def test_guardar_avisa_si_no_puede_escribir(tmp_path):
    """Un fallo de disco debe explicarse, no reventar la interfaz."""
    estorbo = tmp_path / "estorbo"
    estorbo.write_text("no soy una carpeta", encoding="utf-8")

    with pytest.raises(ErrorDocumento):
        guardar("<html></html>", estorbo / "dentro", "factura.html")


# ── Contra la base de datos ─────────────────────────────────────────────


def test_la_factura_de_una_venta_real_cuadra(producto_demo, usuario_admin):
    """
    Los importes de la factura deben coincidir con lo que se cobró (RF09).

    Es la comprobación que une las dos mitades: lo que el servicio registró y
    lo que el cliente se lleva impreso.
    """
    servicio = ServicioVentas()
    comprobante = servicio.registrar(
        usuario_admin, [{"idproducto": producto_demo, "cantidad": 2}], "100.00"
    )
    venta = servicio.obtener_detalle(comprobante.idventa)

    html = componer_html(venta, NEGOCIO)

    assert f"{comprobante.idventa:05d}" in html
    assert f"C$ {comprobante.total:,.2f}" in html
    assert f"C$ {comprobante.cambio:,.2f}" in html
    assert "Cuaderno universitario" in html


# ── Diálogo de la factura en pantalla ───────────────────────────────────


class PaginaFalsa:
    """Sustituto de ``ft.Page`` para construir el diálogo sin ventana."""

    def __init__(self) -> None:
        """Arranca sin diálogos mostrados."""
        self.dialogos_mostrados: list = []

    def show_dialog(self, dialogo) -> None:
        """Registra el diálogo en lugar de dibujarlo."""
        self.dialogos_mostrados.append(dialogo)

    def pop_dialog(self):
        """Descarta el último diálogo registrado."""
        return self.dialogos_mostrados.pop() if self.dialogos_mostrados else None

    def update(self) -> None:
        """No hay ventana que refrescar."""


def textos_de(control) -> list[str]:
    """
    Recoge todos los textos visibles de un árbol de controles.

    Args:
        control: Control raíz a recorrer.

    Returns:
        Los textos encontrados, en orden de aparición.
    """
    import flet as ft

    encontrados: list[str] = []
    pendientes = [control]
    vistos: set[int] = set()
    while pendientes:
        nodo = pendientes.pop(0)
        if id(nodo) in vistos:
            continue
        vistos.add(id(nodo))
        if isinstance(nodo, ft.Text) and isinstance(nodo.value, str):
            encontrados.append(nodo.value)
        for atributo in ("controls", "content", "actions", "title"):
            hijo = getattr(nodo, atributo, None)
            if hijo is None:
                continue
            for elemento in hijo if isinstance(hijo, list) else [hijo]:
                if isinstance(elemento, ft.Control):
                    pendientes.append(elemento)
    return encontrados


def test_el_dialogo_muestra_el_detalle_y_no_solo_los_totales():
    """El cliente revisa los artículos antes de llevarse el comprobante."""
    from vistas.ventas import _factura

    dialogo = _factura(PaginaFalsa(), venta_de_prueba(), lambda _venta: None)
    textos = " ".join(textos_de(dialogo))

    assert "Cuaderno universitario" in textos
    assert "Folder Manila" in textos
    assert "C$ 167.96" in textos
    assert "Factura N.º 00042" in textos


def test_el_dialogo_ofrece_imprimir_la_factura():
    """Sin el botón, la factura se vería pero no se podría imprimir."""
    import flet as ft

    from vistas.ventas import _factura

    dialogo = _factura(PaginaFalsa(), venta_de_prueba(), lambda _venta: None)
    iconos = [getattr(accion, "icon", None) for accion in dialogo.actions]

    assert ft.Icons.PRINT in iconos


def test_imprimir_entrega_la_venta_completa():
    """Quien imprime necesita las líneas, no solo el número de venta."""
    from vistas.ventas import _factura

    impresas: list = []
    dialogo = _factura(PaginaFalsa(), venta_de_prueba(), impresas.append)
    boton = next(a for a in dialogo.actions if getattr(a, "icon", None) is not None)

    boton.on_click(None)

    assert len(impresas) == 1
    assert impresas[0].idventa == 42
    assert len(impresas[0].detalles) == 2


def test_el_total_va_antes_del_efectivo_y_el_cambio():
    """
    El cambio se deriva del total, así que leerlo antes desconcierta.

    Es además el orden que muestra el diálogo en pantalla: las dos vistas de
    la misma venta deben contar lo mismo en el mismo orden.
    """
    html = componer_html(venta_de_prueba(), NEGOCIO)
    totales = html.split('class="totales"')[1]

    assert totales.index("TOTAL") < totales.index("Efectivo recibido")
    assert totales.index("Efectivo recibido") < totales.index("Cambio entregado")

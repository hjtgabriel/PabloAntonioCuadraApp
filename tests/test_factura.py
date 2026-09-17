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

from modulos.ventas.factura import alto_mm, componer_html, nombre_archivo
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

    assert "Atendido por: —" in componer_html(venta, NEGOCIO)


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

    assert totales.index("TOTAL") < totales.index("Efectivo")
    assert totales.index("Efectivo") < totales.index("Cambio")


# ── Formato de impresora de tickets ─────────────────────────────────────


def test_la_factura_se_maqueta_para_el_rollo_y_no_para_una_hoja():
    """
    El papel debe cortarse donde termina la factura, no expulsar una página.

    Eso lo consigue «@page» declarando el ancho del rollo y alto automático.
    Sin esto, una térmica saca metros de papel en blanco tras cada venta.
    """
    html = componer_html(venta_de_prueba(), NEGOCIO)

    assert "@page { size: 80mm " in html
    assert "mm; margin: 0; }" in html
    assert "auto" not in html.split("@page")[1].split("}")[0]


@pytest.mark.parametrize("ancho", [58, 80])
def test_el_ancho_del_rollo_es_configurable(ancho):
    """Los dos rollos habituales son 58 mm y 80 mm; ambos deben salir bien."""
    html = componer_html(venta_de_prueba(), NEGOCIO, ancho)

    assert f"size: {ancho}mm " in html
    assert f"width: {ancho}mm" in html


def test_la_factura_usa_tipografia_monoespaciada():
    """Es lo que alinea los importes en columna sobre papel estrecho."""
    html = componer_html(venta_de_prueba(), NEGOCIO)

    assert "monospace" in html


def test_la_factura_no_lleva_fondos_de_color():
    """
    Una impresora térmica no reproduce fondos, y en otra solo gastan tinta.

    El único color declarado es el blanco del papel y el negro de la tinta.
    """
    html = componer_html(venta_de_prueba(), NEGOCIO)
    estilos = html.split("<style>")[1].split("</style>")[0]

    for color in ("#f4efe4", "#7b1020", "#d9d2c4", "#2b2b2b"):
        assert color not in estilos, f"El ticket no debe llevar el color {color}"


def test_el_boton_de_imprimir_no_sale_en_el_papel():
    """Solo sirve en pantalla; en el ticket sería una caja negra inútil."""
    html = componer_html(venta_de_prueba(), NEGOCIO)
    impresion = html.split("@media print")[1]

    assert ".imprimir { display: none; }" in impresion


def test_cada_articulo_cabe_con_su_precio_unitario():
    """
    En 80 mm no caben cuatro columnas, así que el precio va bajo el nombre.

    Sigue apareciendo: el cliente necesita ver a cuánto se le cobró la unidad.
    """
    html = componer_html(venta_de_prueba(), NEGOCIO)

    assert "C$ 35.50 c/u" in html
    assert "C$ 96.96 c/u" in html


def test_la_tabla_del_ticket_tiene_tres_columnas():
    """Cantidad, producto e importe: es lo que entra en un rollo estrecho."""
    html = componer_html(venta_de_prueba(detalles=[]), NEGOCIO)

    assert 'colspan="3"' in html


def test_el_papel_crece_con_los_articulos():
    """Más artículos exigen más rollo; el alto no puede ser fijo."""
    uno = alto_mm(venta_de_prueba(detalles=venta_de_prueba().detalles[:1]), NEGOCIO)
    dos = alto_mm(venta_de_prueba(), NEGOCIO)

    assert dos > uno


def test_un_nombre_largo_cuenta_como_varios_renglones():
    """
    En un papel estrecho el nombre se ajusta a dos o tres líneas.

    Contarlo como un solo renglón dejaba la página corta y la factura se
    partía en dos, con lo que el cliente se llevaba medio comprobante.
    """
    corto = venta_de_prueba(
        detalles=[
            DetalleVenta(
                iddetalleventa=1, idventa=42, idproducto=1, cantidad=1,
                descripcion="Lápiz", precioventa=Decimal("10"), subtotal=Decimal("10"),
            )
        ]
    )
    largo = venta_de_prueba(
        detalles=[
            DetalleVenta(
                iddetalleventa=1, idventa=42, idproducto=1, cantidad=1,
                descripcion="Cuaderno universitario de cien hojas rayado doble línea",
                precioventa=Decimal("10"), subtotal=Decimal("10"),
            )
        ]
    )

    assert alto_mm(largo, NEGOCIO) > alto_mm(corto, NEGOCIO)


def test_un_rollo_estrecho_necesita_mas_alto_que_uno_ancho():
    """Lo que no cabe a lo ancho se gasta a lo largo."""
    assert alto_mm(venta_de_prueba(), NEGOCIO, 58) > alto_mm(venta_de_prueba(), NEGOCIO, 80)


def test_un_negocio_de_nombre_largo_tambien_alarga_el_papel():
    """El encabezado se ajusta igual que los artículos y hay que contarlo."""
    breve = alto_mm(venta_de_prueba(), "PAC", 58)
    extenso = alto_mm(venta_de_prueba(), "Librería y Papelería Pablo Antonio Cuadra", 58)

    assert extenso > breve


def test_una_venta_sin_detalle_reserva_papel_igualmente():
    """Sin líneas que contar, el ticket no puede quedarse sin alto."""
    assert alto_mm(venta_de_prueba(detalles=[]), NEGOCIO) > 0

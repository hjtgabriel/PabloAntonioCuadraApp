"""
Paleta corporativa y tema visual de la aplicación.

Este archivo es la única fuente de color del sistema: ninguna vista debe
escribir un código hexadecimal a mano. Así, cambiar un color aquí lo cambia en
toda la aplicación, y la interfaz mantiene la sobriedad que pide el RNF03.

Los valores de la paleta no se modifican.
"""

from __future__ import annotations

import flet as ft

# ── Paleta corporativa estricta ─────────────────────────────────────────
FONDO = "#F1E4CC"             # Crema (fondo principal)
TEXTO = "#155E45"             # Verde bosque (texto principal)
TEXTO_SECUNDARIO = "#000000"  # Negro (texto secundario)
ACENTO = "#7B1423"            # Rojo principal (acento principal)
ACENTO_SECUNDARIO = "#D4AF37" # Dorado (acento secundario / detalles)
VARIANTE = "#AC2030"          # Rojo oscuro (variantes / sombras)
APOYO = "#C4B5AF"             # Gris (apoyo)
SUPERFICIE = "#FFFFFF"        # Blanco (superficies / tarjetas)
ERROR = "#AC2030"             # Rojo oscuro (errores / alertas)
EXITO = "#155E45"             # Verde bosque (éxito / confirmaciones)
NAV_BG = "#C4B5AF"            # Gris (barra lateral / navegación)

# ── Colores derivados de la paleta ──────────────────────────────────────
# No son colores nuevos: son los mismos con transparencia, para bordes y
# textos atenuados. Se definen aquí para que las vistas nunca inventen uno.
BORDE = "#C4B5AF"             # APOYO, usado como línea divisoria
TEXTO_ATENUADO = "#7A7A7A"    # Gris medio para textos de apoyo
AVISO = "#D4AF37"             # ACENTO_SECUNDARIO, para advertencias

# ── Medidas de la interfaz ──────────────────────────────────────────────
RADIO_BORDE = 8
RADIO_TARJETA = 12
ESPACIO = 12
ESPACIO_GRANDE = 24
ALTO_FILA = 48

# ── Tamaños de texto ────────────────────────────────────────────────────
TEXTO_TITULO = 24
TEXTO_SUBTITULO = 18
TEXTO_NORMAL = 14
TEXTO_PEQUENO = 12


def obtener_tema() -> ft.Theme:
    """
    Construye el tema de Flet a partir de la paleta corporativa.

    Returns:
        Tema listo para asignar a la página principal.
    """
    return ft.Theme(
        color_scheme_seed=ACENTO,
        color_scheme=ft.ColorScheme(
            primary=ACENTO,
            on_primary=SUPERFICIE,
            secondary=ACENTO_SECUNDARIO,
            surface=SUPERFICIE,
            error=ERROR,
            on_error=SUPERFICIE,
        ),
        font_family="Segoe UI",
    )


def estilo_boton() -> ft.ButtonStyle:
    """
    Estilo uniforme para los botones de acción.

    Returns:
        Estilo con las esquinas redondeadas que usa toda la aplicación.
    """
    return ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=RADIO_BORDE))


def color_estado_stock(stock: int, minimo: int) -> str:
    """
    Elige el color con que mostrar el nivel de existencias (RF07).

    Args:
        stock: Existencias actuales.
        minimo: Umbral de reabastecimiento.

    Returns:
        ``ERROR`` si el stock está en el mínimo o por debajo, ``AVISO`` si no
        supera el doble del mínimo, ``EXITO`` en cualquier otro caso.
    """
    if stock <= minimo:
        return ERROR
    if stock <= minimo * 2:
        return AVISO
    return EXITO

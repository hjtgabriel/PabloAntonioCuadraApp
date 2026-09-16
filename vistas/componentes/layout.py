"""
Piezas de maquetación compartidas.

Encabezados, tarjetas y contenedores que dan a todas las pantallas el mismo
aspecto. Igual que el resto de componentes, toman sus colores de :mod:`tema`.
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from tema import (
    ACENTO,
    BORDE,
    ESPACIO,
    ESPACIO_GRANDE,
    FONDO,
    RADIO_TARJETA,
    SUPERFICIE,
    TEXTO,
    TEXTO_ATENUADO,
    TEXTO_SUBTITULO,
    TEXTO_TITULO,
)


def encabezado(titulo: str, *acciones: ft.Control) -> ft.Container:
    """
    Crea la franja superior de una pantalla, con su título y sus acciones.

    Args:
        titulo: Título de la pantalla.
        *acciones: Controles a alinear a la derecha (búsqueda, botones…).

    Returns:
        Contenedor con el encabezado y su línea divisoria.
    """
    fila = ft.Row(
        [
            ft.Text(titulo, size=TEXTO_TITULO, weight=ft.FontWeight.BOLD, color=TEXTO),
            ft.Container(expand=True),
            *acciones,
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        spacing=ESPACIO,
    )
    return ft.Container(
        content=ft.Column([fila, ft.Divider(height=1, color=BORDE)], spacing=ESPACIO),
        padding=ESPACIO_GRANDE,
    )


def pantalla(titulo: str, cuerpo: ft.Control, *acciones: ft.Control) -> ft.Column:
    """
    Arma una pantalla estándar: encabezado arriba y contenido debajo.

    Args:
        titulo: Título de la pantalla.
        cuerpo: Contenido principal.
        *acciones: Controles del encabezado.

    Returns:
        La pantalla completa.
    """
    return ft.Column(
        [
            encabezado(titulo, *acciones),
            ft.Container(content=cuerpo, padding=ESPACIO_GRANDE, expand=True),
        ],
        expand=True,
        spacing=0,
    )


def pantalla_con_boton(
    titulo: str,
    cuerpo: ft.Control,
    texto_boton: str,
    al_pulsar: Callable[[ft.ControlEvent], None],
    *acciones: ft.Control,
) -> ft.Stack:
    """
    Arma una pantalla con un botón flotante de alta en la esquina inferior.

    Args:
        titulo: Título de la pantalla.
        cuerpo: Contenido principal.
        texto_boton: Ayuda emergente del botón flotante.
        al_pulsar: Acción del botón flotante.
        *acciones: Controles del encabezado.

    El botón se coloca con ``right`` y ``bottom``, es decir, como hijo
    posicionado del ``Stack``. La alternativa evidente —un contenedor con
    ``alignment`` en la esquina— parece equivalente y no lo es: un hijo sin
    posicionar se estira hasta ocupar todo el ``Stack``, de modo que su área
    transparente queda por encima de la pantalla entera y se traga las
    pulsaciones. Con eso, la tabla y la barra de búsqueda se veían pero no
    respondían, y el único control que seguía funcionando era el propio botón,
    porque era el que estaba arriba.

    Returns:
        La pantalla con el botón superpuesto.
    """
    return ft.Stack(
        [
            ft.Container(content=pantalla(titulo, cuerpo, *acciones), expand=True),
            ft.Container(
                content=ft.FloatingActionButton(
                    icon=ft.Icons.ADD,
                    bgcolor=ACENTO,
                    foreground_color=SUPERFICIE,
                    tooltip=texto_boton,
                    on_click=al_pulsar,
                ),
                right=ESPACIO_GRANDE,
                bottom=ESPACIO_GRANDE,
            ),
        ],
        expand=True,
    )


def tarjeta(titulo: str, contenido: ft.Control, icono: str | None = None) -> ft.Card:
    """
    Agrupa contenido dentro de una tarjeta con título.

    Args:
        titulo: Encabezado de la tarjeta.
        contenido: Control a mostrar dentro.
        icono: Icono opcional junto al título.

    Returns:
        La tarjeta lista para colocar.
    """
    cabecera = ft.Row(
        [
            *( [ft.Icon(icono, color=ACENTO)] if icono else [] ),
            ft.Text(titulo, size=TEXTO_SUBTITULO, weight=ft.FontWeight.BOLD, color=TEXTO),
        ],
        spacing=ESPACIO,
    )
    return ft.Card(
        elevation=2,
        content=ft.Container(
            content=ft.Column([cabecera, ft.Divider(height=1, color=BORDE), contenido], spacing=ESPACIO),
            padding=ESPACIO_GRANDE,
            bgcolor=SUPERFICIE,
            border_radius=RADIO_TARJETA,
        ),
    )


def estado_vacio(icono: str, titulo: str, mensaje: str) -> ft.Container:
    """
    Muestra un aviso centrado cuando una sección no tiene nada que mostrar.

    Args:
        icono: Icono grande a mostrar.
        titulo: Frase principal.
        mensaje: Explicación de qué hacer a continuación.

    Returns:
        Contenedor centrado con el aviso.
    """
    return ft.Container(
        content=ft.Column(
            [
                ft.Icon(icono, size=64, color=BORDE),
                ft.Text(titulo, size=TEXTO_SUBTITULO, weight=ft.FontWeight.BOLD, color=TEXTO),
                ft.Text(mensaje, size=14, color=TEXTO_ATENUADO, text_align=ft.TextAlign.CENTER),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=ESPACIO,
        ),
        alignment=ft.Alignment(0, 0),
        expand=True,
    )


def indicador(titulo: str, valor: str, color: str = ACENTO, icono: str | None = None) -> ft.Container:
    """
    Crea un recuadro con una cifra destacada, para los reportes.

    Args:
        titulo: Qué mide la cifra.
        valor: La cifra ya formateada.
        color: Color con que resaltarla.
        icono: Icono opcional.

    Returns:
        El recuadro listo para colocar en una fila de indicadores.
    """
    contenido: list[ft.Control] = []
    if icono:
        contenido.append(ft.Icon(icono, color=color, size=28))
    contenido.extend(
        [
            ft.Text(valor, size=TEXTO_TITULO, weight=ft.FontWeight.BOLD, color=color),
            ft.Text(titulo, size=12, color=TEXTO_ATENUADO, text_align=ft.TextAlign.CENTER),
        ]
    )
    return ft.Container(
        content=ft.Column(
            contenido, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4, tight=True
        ),
        padding=ESPACIO_GRANDE,
        bgcolor=SUPERFICIE,
        border=ft.Border.all(1, BORDE),
        border_radius=RADIO_TARJETA,
        expand=True,
    )


def panel(contenido: ft.Control) -> ft.Container:
    """
    Envuelve contenido con el fondo general de la aplicación.

    Args:
        contenido: Control a envolver.

    Returns:
        Contenedor con el fondo corporativo.
    """
    return ft.Container(content=contenido, bgcolor=FONDO, expand=True)

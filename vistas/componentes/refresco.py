"""
Refresco seguro de controles.

En Flet 0.86.5, la propiedad ``Control.page`` **lanza** ``RuntimeError`` cuando
el control todavía no está montado en la página, en vez de devolver ``None``.
Por eso la comprobación intuitiva ``if control.page is not None`` no sirve como
guarda: revienta justo en el caso que pretendía cubrir.

Este módulo concentra esa particularidad en un solo sitio, para que el resto de
la interfaz pueda pedir un refresco sin preocuparse de si el control ya está en
pantalla.
"""

from __future__ import annotations

import flet as ft


def esta_montado(control: ft.Control) -> bool:
    """
    Indica si el control ya forma parte de la página.

    Args:
        control: Control a comprobar.

    Returns:
        True si está montado y puede refrescarse.
    """
    try:
        return control.page is not None
    except RuntimeError:
        return False


def refrescar(control: ft.Control) -> None:
    """
    Redibuja un control, sin hacer nada si aún no está en pantalla.

    Permite que los componentes actualicen su contenido tanto durante la
    construcción inicial como después, sin duplicar la comprobación.

    Args:
        control: Control a redibujar.
    """
    if esta_montado(control):
        control.update()

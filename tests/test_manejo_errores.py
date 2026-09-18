"""
Pruebas del manejo de fallos imprevistos en la interfaz.

Un error de base de datos arrastra el servidor, el puerto, el nombre de la base
y el usuario de conexión. Eso no puede acabar en la pantalla de un mostrador, y
menos en la de acceso, que se ve antes de autenticar a nadie. A la vez, el
detalle no puede perderse: tiene que quedar en el registro con su traza.
"""

from __future__ import annotations

import ast
import logging
import pathlib

import flet as ft

from nucleo.errores import ErrorConexion
from tests.conftest import PaginaFalsa
from vistas.componentes.notificaciones import MENSAJE_INESPERADO, avisar_fallo_inesperado

FUGA = (
    'connection to server at "192.168.0.7", port 5432 failed: FATAL: '
    'password authentication failed for user "postgres"'
)


def texto_mostrado(pagina: PaginaFalsa) -> str:
    """
    Recoge el texto del último aviso mostrado.

    Args:
        pagina: Página falsa sobre la que se avisó.

    Returns:
        El texto del aviso.
    """
    aviso = pagina.dialogos_mostrados[-1]
    contenido = aviso.content
    return contenido.value if isinstance(contenido, ft.Text) else str(contenido)


def test_el_usuario_no_ve_el_detalle_del_error():
    """Servidor, puerto y usuario de conexión no pueden salir en pantalla."""
    pagina = PaginaFalsa()

    avisar_fallo_inesperado(pagina, "guardar la venta", ErrorConexion(FUGA))

    mostrado = texto_mostrado(pagina)
    assert mostrado == MENSAJE_INESPERADO
    for secreto in ("192.168.0.7", "5432", "postgres", "password"):
        assert secreto not in mostrado, f"El aviso filtró «{secreto}»"


def test_el_detalle_si_queda_en_el_registro(caplog):
    """Lo que se le oculta al usuario tiene que poder diagnosticarlo el técnico."""
    with caplog.at_level(logging.ERROR):
        avisar_fallo_inesperado(PaginaFalsa(), "guardar la venta", ErrorConexion(FUGA))

    registrado = caplog.text
    assert "192.168.0.7" in registrado
    assert "guardar la venta" in registrado
    assert "ErrorConexion" in registrado


def test_el_aviso_dice_donde_buscar_el_detalle():
    """Sin esa pista el usuario no sabe qué reportar."""
    assert "registro" in MENSAJE_INESPERADO.lower()


def test_ningun_except_amplio_muestra_la_excepcion_cruda():
    """
    Un fallo imprevisto nunca debe interpolarse en el aviso al usuario.

    La regla se aplica solo a los ``except Exception``, que atrapan lo que no
    esperábamos: un error de driver, de red o de disco, cuyo texto trae datos
    de infraestructura. Los ``ErrorAplicacion`` sí se muestran tal cual, porque
    su mensaje lo escribimos nosotros para que lo lea el usuario.

    Se comprueba sobre el código y no pantalla por pantalla porque fueron diez
    sitios los que se saltaron la regla a la vez.
    """
    sospechosos = [
        f"{ruta}:{linea}"
        for ruta in pathlib.Path("vistas").rglob("*.py")
        for linea in _avisos_con_excepcion_cruda(ruta)
    ]

    assert not sospechosos, "Muestran la excepción cruda al usuario: " + ", ".join(sospechosos)


def _avisos_con_excepcion_cruda(ruta: pathlib.Path) -> list[int]:
    """
    Busca avisos que interpolen la excepción dentro de un «except» amplio.

    Args:
        ruta: Archivo de vista a revisar.

    Returns:
        Las líneas sospechosas encontradas.
    """
    encontradas: list[int] = []
    for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
        if not isinstance(nodo, ast.ExceptHandler) or not _es_captura_amplia(nodo):
            continue
        encontradas.extend(
            hijo.lineno
            for hijo in ast.walk(nodo)
            if isinstance(hijo, ast.Call) and _muestra_al_usuario(hijo)
        )
    return encontradas


def _es_captura_amplia(manejador: ast.ExceptHandler) -> bool:
    """
    Indica si un «except» atrapa cualquier excepción.

    Args:
        manejador: Bloque «except» a revisar.

    Returns:
        True si captura ``Exception`` o no declara tipo.
    """
    if manejador.type is None:
        return True
    return getattr(manejador.type, "id", "") in ("Exception", "BaseException")


def _muestra_al_usuario(llamada: ast.Call) -> bool:
    """
    Indica si una llamada avisa al usuario interpolando la excepción.

    Args:
        llamada: Llamada a revisar.

    Returns:
        True si mete la variable «error» en el texto del aviso.
    """
    nombre = getattr(llamada.func, "id", "") or getattr(llamada.func, "attr", "")
    if not nombre.startswith(("avisar", "_mostrar_mensaje", "_mostrar_fallo")):
        return False
    return any(_interpola_la_excepcion(argumento) for argumento in llamada.args)


def _interpola_la_excepcion(nodo: ast.AST) -> bool:
    """
    Indica si un texto mete la variable «error» dentro de un f-string.

    Args:
        nodo: Argumento de la llamada a revisar.

    Returns:
        True si el texto interpola la excepción capturada.
    """
    if not isinstance(nodo, ast.JoinedStr):
        return False
    return any(
        isinstance(trozo, ast.FormattedValue)
        and isinstance(trozo.value, ast.Name)
        and trozo.value.id == "error"
        for trozo in nodo.values
    )

"""
Pruebas de las validaciones de entrada en los formularios.

Cubren las dos reglas que pidió la librería: el efectivo recibido solo admite
números positivos, y el teléfono solo dígitos. Ambas deben **avisar** de lo que
está mal, no limitarse a impedir la tecla: un campo que no responde y tampoco
explica por qué deja al usuario sin saber qué hacer.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

LARGO_MAXIMO_AVISO = 46
"""Caracteres que caben bajo un campo estrecho sin que el aviso se corte."""

from vistas.componentes.campos import (  # noqa: E402
    MENSAJE_SOLO_NUMEROS_POSITIVOS,
    MENSAJE_TELEFONO,
    campo_decimal,
    campo_telefono,
    campo_texto,
    encadenar_al_cambiar,
)


def error_al_escribir(campo, texto: str) -> str | None:
    """
    Simula que el usuario escribe un texto y devuelve el error mostrado.

    Args:
        campo: Campo a probar.
        texto: Lo que teclea el usuario.

    Returns:
        El mensaje de error visible, o None si el campo lo aceptó.
    """

    class EventoFalso:
        """Evento mínimo con el control que lo originó."""

        def __init__(self, control) -> None:
            """
            Args:
                control: Campo que disparó el evento.
            """
            self.control = control

    campo.value = texto
    campo.on_change(EventoFalso(campo))
    return campo.error


# ── Efectivo recibido: solo números positivos ───────────────────────────


@pytest.mark.parametrize("texto", ["abc", "mil", "20a", "$50", "cien córdobas"])
def test_el_efectivo_rechaza_texto(texto):
    """Escribir letras debe avisar, no quedarse callado."""
    campo = campo_decimal("Efectivo recibido", valor="", filtrar_entrada=False)

    assert error_al_escribir(campo, texto) == MENSAJE_SOLO_NUMEROS_POSITIVOS


@pytest.mark.parametrize("texto", ["-1", "-100.50", "-0.01"])
def test_el_efectivo_rechaza_negativos(texto):
    """Un cliente no entrega efectivo negativo."""
    campo = campo_decimal("Efectivo recibido", valor="", filtrar_entrada=False)

    assert error_al_escribir(campo, texto) == MENSAJE_SOLO_NUMEROS_POSITIVOS


@pytest.mark.parametrize("texto", ["0", "1", "250", "250.00", "1500.75"])
def test_el_efectivo_acepta_numeros_positivos(texto):
    """Lo válido debe pasar sin estorbar al cajero."""
    campo = campo_decimal("Efectivo recibido", valor="", filtrar_entrada=False)

    assert error_al_escribir(campo, texto) is None


def test_el_aviso_del_efectivo_explica_que_se_espera():
    """Un mensaje que no dice qué hacer no sirve de nada."""
    assert "números positivos" in MENSAJE_SOLO_NUMEROS_POSITIVOS


@pytest.mark.parametrize(
    "mensaje", [MENSAJE_SOLO_NUMEROS_POSITIVOS, MENSAJE_TELEFONO]
)
def test_los_avisos_caben_bajo_el_campo(mensaje):
    """
    Un aviso que se corta no sirve para corregir nada.

    El campo de efectivo mide unos 300 px en el punto de venta, y el primer
    texto que se escribió salía truncado: «…solo se aceptan números p…». Se
    comprobó sobre la aplicación real, no a ojo.
    """
    assert len(mensaje) <= LARGO_MAXIMO_AVISO


def test_el_campo_de_efectivo_deja_escribir_para_poder_avisar():
    """
    Si el filtro bloquea la tecla, el validador nunca llega a explicar nada.

    Era el comportamiento anterior: teclear una letra no hacía absolutamente
    nada y el cajero no sabía por qué.
    """
    campo = campo_decimal("Efectivo recibido", valor="", filtrar_entrada=False)

    assert campo.input_filter is None


# ── El validador no se pierde al conectar otra cosa ─────────────────────


def test_encadenar_conserva_la_validacion():
    """
    Conectar un manejador propio no puede descartar el del campo.

    Asignar «on_change» directamente reemplaza lo que hubiera. Así se perdía la
    validación del efectivo: la pantalla conectaba el cálculo del cambio encima
    y el campo dejaba de avisar.
    """
    campo = campo_decimal("Efectivo recibido", valor="", filtrar_entrada=False)
    llamadas: list[str] = []

    encadenar_al_cambiar(campo, lambda _evento: llamadas.append("cálculo del cambio"))

    assert error_al_escribir(campo, "abc") == MENSAJE_SOLO_NUMEROS_POSITIVOS
    assert llamadas == ["cálculo del cambio"]


def test_encadenar_funciona_en_un_campo_sin_validador():
    """También debe servir para un campo que no traía nada conectado."""
    campo = campo_texto("Nota")
    llamadas: list[str] = []

    encadenar_al_cambiar(campo, lambda _evento: llamadas.append("mío"))
    error_al_escribir(campo, "hola")

    assert llamadas == ["mío"]


# ── Teléfono: solo dígitos ──────────────────────────────────────────────


@pytest.mark.parametrize("texto", ["8676-7203", "505-8676-7203", "86767203"])
def test_el_telefono_acepta_el_guion_como_separador(texto):
    """Es como se anotan los teléfonos en el local."""
    campo = campo_telefono()

    assert error_al_escribir(campo, texto) is None


@pytest.mark.parametrize("texto", ["8676 7203", "+505 86767203", "(505)86767203", "8676.7203"])
def test_el_telefono_rechaza_otros_separadores(texto):
    """
    Se admite el guion y solo el guion.

    Dejar entrar espacios, paréntesis o «+» haría que el mismo número quedara
    guardado de varias formas y nadie pudiera buscarlo después.
    """
    campo = campo_telefono()

    assert error_al_escribir(campo, texto) == MENSAJE_TELEFONO


@pytest.mark.parametrize("texto", ["-86767203", "86767203-", "8676--7203"])
def test_el_telefono_rechaza_guiones_mal_puestos(texto):
    """Un guion separa dos grupos de cifras; suelto o doble es un error."""
    campo = campo_telefono()

    assert error_al_escribir(campo, texto) == MENSAJE_TELEFONO


@pytest.mark.parametrize("texto", ["ocho seis", "86767203a", "abc", "N/A"])
def test_el_telefono_rechaza_letras(texto):
    """Es la regla que pidió la librería: solo números."""
    campo = campo_telefono()

    assert error_al_escribir(campo, texto) == MENSAJE_TELEFONO


@pytest.mark.parametrize("texto", ["86767203", "22334455", "50586767203"])
def test_el_telefono_acepta_solo_digitos(texto):
    """Un número sin separadores también es válido."""
    campo = campo_telefono()

    assert error_al_escribir(campo, texto) is None


def test_los_guiones_no_cuentan_como_digitos():
    """
    «123-45» tiene cinco cifras, no seis: sigue siendo demasiado corto.

    Si el guion contara, un número incompleto pasaría la comprobación solo por
    llevar separadores.
    """
    assert error_al_escribir(campo_telefono(), "123-45") is not None
    assert error_al_escribir(campo_telefono(), "8676-7203") is None


def test_el_telefono_puede_quedar_vacio():
    """No todos los empleados tienen teléfono registrado."""
    assert error_al_escribir(campo_telefono(), "") is None


def test_el_telefono_obligatorio_si_lo_exige_avisa():
    """Cuando se exige, el campo vacío debe reclamarlo."""
    campo = campo_telefono(obligatorio=True)

    assert error_al_escribir(campo, "") is not None


@pytest.mark.parametrize("texto", ["123", "12345"])
def test_el_telefono_rechaza_numeros_demasiado_cortos(texto):
    """Tres dígitos no son un teléfono: es un dato incompleto."""
    campo = campo_telefono()

    assert error_al_escribir(campo, texto) is not None


def test_el_telefono_rechaza_numeros_absurdamente_largos():
    """Un número de veinte cifras es un error de tecleo."""
    assert error_al_escribir(campo_telefono(), "1" * 20) is not None


def test_el_aviso_del_telefono_nombra_lo_que_no_se_admite():
    """El usuario debe entender qué quitar sin adivinar."""
    assert "letras" in MENSAJE_TELEFONO
    assert "guiones" in MENSAJE_TELEFONO


def test_el_telefono_guardado_en_la_libreria_es_valido():
    """
    El formato que ya se usa en el local debe seguir siendo válido.

    La primera versión de esta regla rechazaba el guion, y el teléfono de una
    empleada ya registrada quedaba marcado como inválido al editarla.
    """
    assert error_al_escribir(campo_telefono(), "8676-7203") is None


# ── Los formularios usan el campo validado ──────────────────────────────


def test_el_formulario_de_empleado_valida_el_telefono(base_datos):
    """La validación no sirve si el formulario no la usa."""
    from tests.test_formularios import buscar
    from vistas.personal import _campos_persona

    telefono = buscar(_campos_persona(None), "telefono").control

    assert error_al_escribir(telefono, "ocho seis") == MENSAJE_TELEFONO
    assert error_al_escribir(telefono, "8676-7203") is None


def test_el_punto_de_venta_valida_el_efectivo(base_datos):
    """El campo de la pantalla real debe avisar, no solo el de la fábrica."""
    from tests.conftest import PaginaFalsa
    from vistas.ventas import PuntoDeVenta

    pantalla = PuntoDeVenta(PaginaFalsa(), idusuario=1)

    assert error_al_escribir(pantalla._efectivo, "abc") == MENSAJE_SOLO_NUMEROS_POSITIVOS


def test_el_calculo_del_cambio_sigue_funcionando(base_datos):
    """La validación no puede haber roto lo que el campo ya hacía."""
    from tests.conftest import PaginaFalsa
    from vistas.ventas import PuntoDeVenta

    pantalla = PuntoDeVenta(PaginaFalsa(), idusuario=1)
    error_al_escribir(pantalla._efectivo, "500")

    assert pantalla._efectivo_escrito() == Decimal("500")

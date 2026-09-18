"""
Pruebas del control de acceso (RF01, RNF04).

Cubren las dos reglas que antes existían solo en la intención: que el servicio
no delate qué usuarios están dados de alta, y que el límite de intentos lo
aplique él y no la pantalla.
"""

from __future__ import annotations

import statistics
import time

import pytest

from modulos.auth.servicios import (
    INTENTOS_ANTES_DE_BLOQUEAR,
    ControlDeIntentos,
    ServicioAutenticacion,
)
from modulos.personal.servicios import ServicioUsuarios
from nucleo.errores import ErrorAutenticacion
from nucleo.seguridad import ITERACIONES_MINIMAS, cifrar_contrasena, verificar_contrasena

CLAVE = "clave-segura-1"


@pytest.fixture
def usuario(base_datos) -> int:
    """
    Crea un usuario con credencial conocida.

    Returns:
        Clave del usuario creado.
    """
    return ServicioUsuarios().crear_con_empleado(
        {
            "nombres": "Ana",
            "apellidos": "López",
            "nombreusuario": "ana",
            "contrasena": CLAVE,
            "idrol": 1,
        }
    )


def servicio_aislado() -> ServicioAutenticacion:
    """
    Arma un servicio con su propio contador de intentos.

    Returns:
        Servicio que no arrastra el estado de otras pruebas.
    """
    return ServicioAutenticacion(control=ControlDeIntentos(intentos=9999))


# ── No revelar qué usuarios existen ─────────────────────────────────────


def test_el_mensaje_es_el_mismo_exista_o_no_el_usuario(usuario):
    """Distinguirlos en el texto delataría qué identificadores hay dados de alta."""
    servicio = servicio_aislado()

    with pytest.raises(ErrorAutenticacion) as inexistente:
        servicio.iniciar_sesion("no_existe", "loquesea")
    with pytest.raises(ErrorAutenticacion) as clave_mala:
        servicio.iniciar_sesion("ana", "clave-equivocada")

    assert str(inexistente.value) == str(clave_mala.value)


def test_tarda_lo_mismo_exista_o_no_el_usuario(usuario):
    """
    El reloj no puede decir lo que el mensaje calla.

    Antes, un usuario inexistente se resolvía sin calcular el hash y respondía
    3600 veces más rápido: bastaba cronometrar para enumerar las cuentas. Se
    miden las dos alternativas intercaladas para que una carga pasajera de la
    máquina afecte a ambas por igual.
    """

    def medir(nombre: str) -> float:
        """
        Cronometra un intento fallido de acceso.

        Args:
            nombre: Identificador con el que se intenta entrar.

        Returns:
            Lo que tardó el intento, en segundos.
        """
        inicio = time.perf_counter()
        with pytest.raises(ErrorAutenticacion):
            servicio_aislado().iniciar_sesion(nombre, "clave-equivocada")
        return time.perf_counter() - inicio

    medir("ana")
    medir("no_existe")

    con_usuario = []
    sin_usuario = []
    for _ in range(5):
        con_usuario.append(medir("ana"))
        sin_usuario.append(medir("no_existe"))

    real = statistics.median(con_usuario)
    falso = statistics.median(sin_usuario)
    relacion = max(real, falso) / min(real, falso)

    assert relacion < 1.5, f"El tiempo delata si el usuario existe ({relacion:.1f}x)"


# ── Límite de intentos en el servicio ───────────────────────────────────


def test_el_servicio_bloquea_tras_demasiados_fallos(usuario):
    """
    El límite es del servicio, no de la pantalla.

    Antes vivía en «vistas/login.py», así que quien llamara al servicio desde
    otro sitio tenía intentos ilimitados.
    """
    servicio = ServicioAutenticacion(control=ControlDeIntentos())

    for _ in range(INTENTOS_ANTES_DE_BLOQUEAR):
        with pytest.raises(ErrorAutenticacion):
            servicio.iniciar_sesion("ana", "clave-equivocada")

    with pytest.raises(ErrorAutenticacion, match="Demasiados intentos"):
        servicio.iniciar_sesion("ana", CLAVE)


def test_el_bloqueo_no_alcanza_a_otros_usuarios(usuario):
    """Bloquear a quien teclea mal no puede dejar fuera al resto del personal."""
    control = ControlDeIntentos()
    servicio = ServicioAutenticacion(control=control)

    for _ in range(INTENTOS_ANTES_DE_BLOQUEAR):
        with pytest.raises(ErrorAutenticacion):
            servicio.iniciar_sesion("otro_cajero", "clave-equivocada")

    assert servicio.iniciar_sesion("ana", CLAVE).nombreusuario == "ana"


def test_entrar_bien_borra_los_fallos_anteriores(usuario):
    """Quien se equivocó y luego acertó vuelve a empezar de cero."""
    control = ControlDeIntentos()
    servicio = ServicioAutenticacion(control=control)

    for _ in range(INTENTOS_ANTES_DE_BLOQUEAR - 1):
        with pytest.raises(ErrorAutenticacion):
            servicio.iniciar_sesion("ana", "clave-equivocada")
    servicio.iniciar_sesion("ana", CLAVE)

    for _ in range(INTENTOS_ANTES_DE_BLOQUEAR - 1):
        with pytest.raises(ErrorAutenticacion):
            servicio.iniciar_sesion("ana", "clave-equivocada")
    assert servicio.iniciar_sesion("ana", CLAVE).nombreusuario == "ana"


def test_los_fallos_caducan_con_el_tiempo(usuario):
    """El bloqueo es temporal: pasada la ventana se puede volver a intentar."""
    servicio = ServicioAutenticacion(control=ControlDeIntentos(intentos=2, segundos=0))

    for _ in range(3):
        with pytest.raises(ErrorAutenticacion):
            servicio.iniciar_sesion("ana", "clave-equivocada")

    assert servicio.iniciar_sesion("ana", CLAVE).nombreusuario == "ana"


# ── Robustez del hash ───────────────────────────────────────────────────


def test_un_hash_con_pocas_iteraciones_se_rechaza():
    """
    Las iteraciones viajan dentro del hash y no se pueden creer sin más.

    Quien pudiera escribir en la base rebajaría el coste a una iteración y los
    hashes robados quedarían al alcance de la fuerza bruta.
    """
    autentico = cifrar_contrasena(CLAVE)
    etiqueta, _, sal, resumen = autentico.split("$")
    debilitado = f"{etiqueta}$1${sal}${resumen}"

    assert verificar_contrasena(CLAVE, autentico) is True
    assert verificar_contrasena(CLAVE, debilitado) is False


def test_el_piso_de_iteraciones_es_razonable():
    """Un piso demasiado bajo no protegería de nada."""
    assert ITERACIONES_MINIMAS >= 100_000

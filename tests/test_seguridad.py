"""Pruebas del cifrado de contraseñas (RNF04)."""

from __future__ import annotations

import pytest

from nucleo.seguridad import (
    cifrar_contrasena,
    esta_cifrada,
    validar_fortaleza,
    verificar_contrasena,
)


def test_el_hash_no_contiene_la_contrasena():
    """El texto plano no debe quedar guardado en ninguna parte del hash (RNF04)."""
    hash_guardado = cifrar_contrasena("mi-clave-secreta")
    assert "mi-clave-secreta" not in hash_guardado
    assert hash_guardado.startswith("pbkdf2_sha256$")


def test_la_contrasena_correcta_se_verifica():
    """Una contraseña válida debe pasar la verificación."""
    assert verificar_contrasena("clave-larga-1", cifrar_contrasena("clave-larga-1"))


def test_la_contrasena_incorrecta_se_rechaza():
    """Una contraseña distinta no debe pasar la verificación."""
    assert not verificar_contrasena("otra-clave", cifrar_contrasena("clave-larga-1"))


def test_dos_hashes_de_la_misma_clave_son_distintos():
    """La sal aleatoria debe producir un hash diferente en cada cifrado."""
    primero = cifrar_contrasena("clave-repetida")
    segundo = cifrar_contrasena("clave-repetida")
    assert primero != segundo
    assert verificar_contrasena("clave-repetida", primero)
    assert verificar_contrasena("clave-repetida", segundo)


@pytest.mark.parametrize(
    "hash_invalido",
    [
        "",
        "clave-en-texto-plano",
        "pbkdf2_sha256$mal-formado",
        "md5$1000$aa$bb",
        "pbkdf2_sha256$no-es-numero$aa$bb",
    ],
)
def test_no_existe_comparacion_en_texto_plano(hash_invalido: str):
    """
    Un hash con formato desconocido debe rechazarse siempre.

    Es la regresión del hueco que tenía la versión anterior: si el valor
    almacenado no era un hash, comparaba la contraseña en texto plano.
    """
    assert not verificar_contrasena("clave-en-texto-plano", hash_invalido)


def test_esta_cifrada_reconoce_el_formato():
    """La función auxiliar debe distinguir un hash propio de cualquier otro texto."""
    assert esta_cifrada(cifrar_contrasena("clave-larga-1"))
    assert not esta_cifrada("clave-larga-1")


@pytest.mark.parametrize("debil", ["", "   ", "corta"])
def test_se_rechazan_contrasenas_debiles(debil: str):
    """La validación de fortaleza debe exigir la longitud mínima."""
    with pytest.raises(ValueError):
        validar_fortaleza(debil)


def test_se_acepta_una_contrasena_suficiente():
    """Una contraseña que cumple el mínimo no debe producir error."""
    validar_fortaleza("clave-valida-8")

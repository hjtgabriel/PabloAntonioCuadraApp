"""
Cifrado y verificación de contraseñas (RNF04).

Usa PBKDF2-HMAC-SHA256 con sal aleatoria por contraseña, que forma parte de la
biblioteca estándar de Python y no exige dependencias adicionales.

Formato almacenado::

    pbkdf2_sha256$<iteraciones>$<sal_hex>$<hash_hex>

A diferencia de la versión anterior, aquí NO existe comparación en texto plano:
un hash con formato desconocido se considera inválido siempre. Eso cumple el
RNF04 sin puertas traseras.
"""

from __future__ import annotations

import hashlib
import logging
import secrets

ALGORITMO = "sha256"
ETIQUETA = "pbkdf2_sha256"
ITERACIONES = 240_000
ITERACIONES_MINIMAS = 100_000
"""
Piso de iteraciones aceptado al verificar.

El número de iteraciones viaja dentro del hash almacenado, así que quien
pudiera escribir en la base podría rebajarlo a uno y volver triviales los
ataques por fuerza bruta contra los hashes robados.
"""
BYTES_SAL = 16
LONGITUD_MINIMA = 8

logger = logging.getLogger(__name__)


def cifrar_contrasena(contrasena: str) -> str:
    """
    Genera el hash almacenable de una contraseña.

    Args:
        contrasena: Contraseña en texto plano.

    Returns:
        Cadena con el formato ``pbkdf2_sha256$iteraciones$sal$hash``.

    Raises:
        ValueError: Si la contraseña está vacía.
    """
    if not contrasena:
        raise ValueError("La contraseña no puede estar vacía")

    sal = secrets.token_bytes(BYTES_SAL)
    resumen = hashlib.pbkdf2_hmac(ALGORITMO, contrasena.encode("utf-8"), sal, ITERACIONES)
    return f"{ETIQUETA}${ITERACIONES}${sal.hex()}${resumen.hex()}"


def verificar_contrasena(contrasena: str, hash_guardado: str) -> bool:
    """
    Comprueba una contraseña contra su hash almacenado.

    La comparación usa ``secrets.compare_digest`` para que el tiempo de
    respuesta no dependa de cuántos bytes coinciden.

    Args:
        contrasena: Contraseña en texto plano a verificar.
        hash_guardado: Hash recuperado de la base de datos.

    Returns:
        True solo si la contraseña corresponde al hash. Cualquier formato
        desconocido, corrupto o con menos iteraciones de las exigidas devuelve
        False.
    """
    if not contrasena or not hash_guardado:
        return False

    partes = hash_guardado.split("$")
    if len(partes) != 4 or partes[0] != ETIQUETA:
        return False

    _, iteraciones_txt, sal_hex, resumen_hex = partes
    try:
        iteraciones = int(iteraciones_txt)
        sal = bytes.fromhex(sal_hex)
        resumen_esperado = bytes.fromhex(resumen_hex)
    except ValueError:
        return False

    if iteraciones < ITERACIONES_MINIMAS:
        logger.warning("Hash almacenado con solo %d iteraciones; se rechaza", iteraciones)
        return False

    resumen_calculado = hashlib.pbkdf2_hmac(ALGORITMO, contrasena.encode("utf-8"), sal, iteraciones)
    return secrets.compare_digest(resumen_calculado, resumen_esperado)


def esta_cifrada(valor: str) -> bool:
    """Indica si una cadena ya tiene el formato de hash de este módulo."""
    return bool(valor) and valor.startswith(f"{ETIQUETA}$")


def validar_fortaleza(contrasena: str) -> None:
    """
    Verifica que la contraseña cumpla el mínimo exigido.

    Args:
        contrasena: Contraseña en texto plano.

    Raises:
        ValueError: Si es más corta que ``LONGITUD_MINIMA`` o solo tiene espacios.
    """
    if not contrasena or not contrasena.strip():
        raise ValueError("La contraseña es obligatoria")
    if len(contrasena) < LONGITUD_MINIMA:
        raise ValueError(f"La contraseña debe tener al menos {LONGITUD_MINIMA} caracteres")

"""
Respaldo automático, pensado para el Programador de tareas de Windows.

Se ejecuta sin interfaz, decide por la fecha qué clase de respaldo toca y avisa
al administrador por correo cuando el respaldo consolida la semana o el mes.

Uso::

    python -m herramientas.respaldo_programado              # decide por la fecha
    python -m herramientas.respaldo_programado --tipo semanal
    python -m herramientas.respaldo_programado --sin-correo

Se ejecuta como tarea programada y no dentro de la aplicación porque el
programa de escritorio está cerrado a medianoche: un temporizador interno nunca
se dispararía. Para instalar la tarea, use ``herramientas.instalar_tarea``.

Códigos de salida, para que el Programador de tareas distinga qué pasó:

* ``0`` – respaldo generado y verificado.
* ``1`` – no se pudo generar el respaldo.
* ``2`` – se generó pero no pasó la verificación, o algún destino falló.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from config import obtener_configuracion
from nucleo.correo import enviar_aviso
from nucleo.errores import ErrorRespaldo
from nucleo.registro import configurar_registro
from nucleo.respaldo import (
    ResultadoRespaldo,
    ServicioRespaldo,
    TipoRespaldo,
    tamano_legible,
)

logger = logging.getLogger(__name__)

EXITO = 0
ERROR_GENERACION = 1
ERROR_VERIFICACION = 2


def principal(argumentos: list[str] | None = None) -> int:
    """
    Genera el respaldo que corresponda y avisa por correo si toca.

    Args:
        argumentos: Argumentos de línea de comandos; None para leer ``sys.argv``.

    Returns:
        Código de salida para el Programador de tareas.
    """
    opciones = _leer_argumentos(argumentos)
    configurar_registro()

    clase = TipoRespaldo(opciones.tipo) if opciones.tipo else TipoRespaldo.segun_fecha(date.today())
    logger.info("Respaldo programado: clase «%s»", clase.value)

    try:
        resultado = ServicioRespaldo().ejecutar(clase)
    except ErrorRespaldo as error:
        logger.error("El respaldo no se pudo generar: %s", error)
        _avisar_fallo(clase, str(error), opciones.sin_correo)
        return ERROR_GENERACION

    if clase.consolida and not opciones.sin_correo:
        resultado.correo_enviado = enviar_aviso(
            _asunto(resultado), redactar_informe(resultado)
        )

    _registrar_resumen(resultado)
    return EXITO if resultado.verificado and not resultado.advertencias else ERROR_VERIFICACION


def redactar_informe(resultado: ResultadoRespaldo) -> str:
    """
    Redacta el correo que recibe el administrador.

    Args:
        resultado: Detalle de la corrida de respaldo.

    Returns:
        Texto del mensaje, listo para enviar.
    """
    configuracion = obtener_configuracion()
    lineas = [
        f"Respaldo {resultado.tipo.value.upper()} de la librería Pablo Antonio Cuadra",
        "",
        f"Fecha y hora      : {resultado.momento:%d/%m/%Y %H:%M:%S}",
        f"Base de datos     : {configuracion.db_nombre}",
        f"Tamaño de la base : {tamano_legible(resultado.tamano_base_bytes)}",
        f"Tamaño del archivo: {tamano_legible(resultado.tamano_bytes)}",
        f"Duración          : {resultado.duracion_segundos:.1f} segundos",
        f"Verificación      : {'CORRECTA' if resultado.verificado else 'FALLIDA'}",
        "",
        f"Copias guardadas ({resultado.volcados}):",
        f"  1. {resultado.archivo_origen}",
    ]
    lineas.extend(f"  {numero}. {ruta}" for numero, ruta in enumerate(resultado.copias, start=2))

    lineas += [
        "",
        f"Con la base de datos en uso son {resultado.total_copias} copias en total.",
    ]
    if not resultado.cumple_321:
        lineas.append(
            "AVISO: faltan destinos para alcanzar las 3 copias de la regla 3-2-1."
        )

    if resultado.eliminados:
        lineas += ["", f"Respaldos antiguos descartados ({len(resultado.eliminados)}):"]
        lineas.extend(f"  - {ruta.name}" for ruta in resultado.eliminados)

    if resultado.advertencias:
        lineas += ["", "ADVERTENCIAS:"]
        lineas.extend(f"  - {aviso}" for aviso in resultado.advertencias)

    lineas += [
        "",
        "-" * 60,
        "Mensaje automático del sistema de gestión.",
        "Para restaurar este respaldo:",
        f"  pg_restore --clean --if-exists -d {configuracion.db_nombre} "
        f"{resultado.archivo_origen.name}",
    ]
    return "\n".join(lineas)


def _asunto(resultado: ResultadoRespaldo) -> str:
    """
    Compone el asunto del correo.

    Args:
        resultado: Detalle de la corrida de respaldo.

    Returns:
        Asunto que resume de un vistazo cómo fue.
    """
    estado = "correcto" if resultado.verificado else "CON PROBLEMAS"
    return (
        f"[Librería PAC] Respaldo {resultado.tipo.value} {estado} "
        f"- {resultado.momento:%d/%m/%Y} - Base: {tamano_legible(resultado.tamano_base_bytes)}"
    )


def _avisar_fallo(clase: TipoRespaldo, motivo: str, sin_correo: bool) -> None:
    """
    Informa al administrador de que el respaldo no pudo generarse.

    Args:
        clase: Clase de respaldo que se intentaba generar.
        motivo: Explicación del fallo.
        sin_correo: Si se pidió no enviar correos.
    """
    if sin_correo:
        return
    enviar_aviso(
        f"[Librería PAC] FALLÓ el respaldo {clase.value}",
        f"El respaldo {clase.value} no pudo generarse.\n\nMotivo: {motivo}\n\n"
        "Revise que PostgreSQL esté encendido y que haya espacio en disco.",
    )


def _registrar_resumen(resultado: ResultadoRespaldo) -> None:
    """
    Deja en el registro un resumen de la corrida.

    Args:
        resultado: Detalle de la corrida de respaldo.
    """
    logger.info(
        "Respaldo %s terminado: %d copias, verificado=%s, descartados=%d, avisos=%d",
        resultado.tipo.value,
        resultado.volcados,
        resultado.verificado,
        len(resultado.eliminados),
        len(resultado.advertencias),
    )
    for aviso in resultado.advertencias:
        logger.warning(aviso)


def _leer_argumentos(argumentos: list[str] | None) -> argparse.Namespace:
    """
    Interpreta los argumentos de línea de comandos.

    Args:
        argumentos: Argumentos a interpretar; None para leer ``sys.argv``.

    Returns:
        Opciones ya interpretadas.
    """
    analizador = argparse.ArgumentParser(
        prog="respaldo_programado",
        description="Genera el respaldo que corresponde a la fecha de hoy.",
    )
    analizador.add_argument(
        "--tipo",
        choices=[clase.value for clase in TipoRespaldo],
        help="Fuerza la clase de respaldo en vez de deducirla de la fecha.",
    )
    analizador.add_argument(
        "--sin-correo",
        action="store_true",
        help="No envía el aviso por correo aunque esté configurado.",
    )
    return analizador.parse_args(argumentos)


if __name__ == "__main__":
    sys.exit(principal())

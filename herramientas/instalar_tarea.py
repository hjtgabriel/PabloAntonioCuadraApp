"""
Instalación de la tarea programada de respaldo (RNF05).

Registra en el Programador de tareas de Windows una tarea diaria a medianoche
que ejecuta :mod:`herramientas.respaldo_programado`. La tarea decide sola qué
clase de respaldo toca: diario de lunes a sábado, semanal el domingo y mensual
el día 1.

Uso (hay que abrir la consola **como administrador**)::

    python -m herramientas.instalar_tarea            # instala o actualiza
    python -m herramientas.instalar_tarea --estado   # consulta cómo quedó
    python -m herramientas.instalar_tarea --quitar   # desinstala

Se usa el Programador de tareas y no un temporizador dentro de la aplicación
porque el programa está cerrado a medianoche. La tarea se registra con la
opción de recuperar ejecuciones perdidas, de modo que si el equipo de la
librería estaba apagado, el respaldo se hace al encenderlo.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from config import RAIZ_PROYECTO

NOMBRE_TAREA = "RespaldoLibreriaPAC"
HORA_EJECUCION = "00:00"
EXITO = 0
ERROR = 1

LANZADOR = RAIZ_PROYECTO / "herramientas" / "ejecutar_respaldo.bat"

PLANTILLA_LANZADOR = """@echo off
REM ---------------------------------------------------------------------
REM  Lanzador del respaldo automatico de la libreria Pablo Antonio Cuadra.
REM
REM  Lo genera «python -m herramientas.instalar_tarea» con las rutas de
REM  este equipo. NO lo edite a mano: se reescribe en cada instalacion, y
REM  por eso esta excluido del repositorio.
REM
REM  Existe porque el Programador de tareas invoca la accion a traves de
REM  cmd.exe, y una linea con comillas anidadas —la ruta de Python dentro
REM  de un «cd ... && ...»— hace que cmd descarte el comando y termine
REM  con exito sin ejecutar nada. Un archivo .bat evita ese problema.
REM ---------------------------------------------------------------------
cd /d "{proyecto}"
"{python}" -m herramientas.respaldo_programado %*
exit /b %ERRORLEVEL%
"""


def principal(argumentos: list[str] | None = None) -> int:
    """
    Instala, consulta o desinstala la tarea programada.

    Args:
        argumentos: Argumentos de línea de comandos; None para leer ``sys.argv``.

    Returns:
        0 si la operación salió bien, 1 si falló.
    """
    opciones = _leer_argumentos(argumentos)

    if os.name != "nt":
        print("Esta herramienta solo funciona en Windows.")
        print("En Linux o macOS, use cron:")
        print(f"   0 0 * * *  cd {RAIZ_PROYECTO} && "
              f"{sys.executable} -m herramientas.respaldo_programado")
        return ERROR

    if opciones.estado:
        return _consultar()
    if opciones.quitar:
        return _desinstalar()
    return _instalar()


def _escribir_lanzador() -> None:
    """
    Genera el archivo .bat que ejecutará la tarea programada.

    Se escribe con las rutas absolutas de este equipo, de modo que el
    Programador de tareas solo tenga que invocar un único archivo sin
    argumentos complicados.
    """
    LANZADOR.write_text(
        PLANTILLA_LANZADOR.format(proyecto=RAIZ_PROYECTO, python=sys.executable),
        encoding="utf-8",
    )
    print(f"Lanzador generado: {LANZADOR}")


def _instalar() -> int:
    """
    Registra la tarea diaria en el Programador de tareas.

    Returns:
        0 si se registró y la comprobación posterior salió bien, 1 si falló.
    """
    _escribir_lanzador()

    argumentos = [
        "schtasks", "/Create",
        "/TN", NOMBRE_TAREA,
        "/TR", str(LANZADOR),
        "/SC", "DAILY",
        "/ST", HORA_EJECUCION,
        "/RL", "HIGHEST",
        "/F",
    ]

    print(f"Registrando la tarea «{NOMBRE_TAREA}» para las {HORA_EJECUCION} de cada día…")
    resultado = subprocess.run(argumentos, capture_output=True, text=True, check=False)

    if resultado.returncode != 0:
        print("\n[ERROR] No se pudo registrar la tarea:")
        print("  " + (resultado.stderr or resultado.stdout).strip())
        print("\n¿Abrió la consola como administrador? Hace falta para crear tareas.")
        return ERROR

    print("[LISTO] Tarea registrada.\n")

    if not _comprobar_lanzador():
        return ERROR

    _explicar_rotacion()
    _recordar_ajuste_manual()
    return EXITO


def _comprobar_lanzador() -> bool:
    """
    Ejecuta el lanzador para confirmar que de verdad genera un respaldo.

    Registrar la tarea no basta: el Programador puede dar por buena una acción
    que no llega a ejecutar nada. Esta comprobación corre el lanzador y exige
    que termine correctamente.

    Returns:
        True si el lanzador funcionó.
    """
    print("Comprobando que el lanzador funcione de verdad…")
    resultado = subprocess.run(
        [str(LANZADOR), "--tipo", "diario", "--sin-correo"],
        capture_output=True, text=True, check=False,
    )

    if resultado.returncode != 0:
        print("\n[ERROR] El lanzador no pudo generar el respaldo.")
        print("  " + (resultado.stderr or resultado.stdout).strip()[-400:])
        print("\nLa tarea quedó registrada, pero NO funcionaría. Revise el error.")
        return False

    print("[LISTO] El lanzador genera respaldos correctamente.\n")
    return True


def _desinstalar() -> int:
    """
    Quita la tarea del Programador de tareas.

    Returns:
        0 si se quitó, 1 si falló.
    """
    resultado = subprocess.run(
        ["schtasks", "/Delete", "/TN", NOMBRE_TAREA, "/F"],
        capture_output=True, text=True, check=False,
    )
    if resultado.returncode != 0:
        print("[ERROR] No se pudo quitar la tarea:")
        print("  " + (resultado.stderr or resultado.stdout).strip())
        return ERROR

    LANZADOR.unlink(missing_ok=True)
    print(f"[LISTO] Tarea «{NOMBRE_TAREA}» eliminada.")
    return EXITO


def _consultar() -> int:
    """
    Muestra el estado actual de la tarea.

    Returns:
        0 si la tarea existe, 1 si no está registrada.
    """
    resultado = subprocess.run(
        ["schtasks", "/Query", "/TN", NOMBRE_TAREA, "/V", "/FO", "LIST"],
        capture_output=True, text=True, check=False,
    )
    if resultado.returncode != 0:
        print(f"La tarea «{NOMBRE_TAREA}» no está registrada.")
        print("Instálela con:  python -m herramientas.instalar_tarea")
        return ERROR

    interesantes = (
        "Nombre de tarea", "TaskName",
        "Estado", "Status",
        "Próxima hora de ejecución", "Next Run Time",
        "Última hora de ejecución", "Last Run Time",
        "Último resultado", "Last Result",
    )
    print(f"Estado de la tarea «{NOMBRE_TAREA}»:\n")
    for linea in resultado.stdout.splitlines():
        if any(linea.strip().startswith(clave) for clave in interesantes):
            print("  " + linea.strip())
    return EXITO


def _explicar_rotacion() -> None:
    """Recuerda al operador qué hará la tarea cada día."""
    print("Qué hará cada noche a las 00:00:")
    print("   Días 2 al 31, de lunes a sábado  ->  respaldo DIARIO")
    print("   Domingos                          ->  respaldo SEMANAL")
    print("                                         + verifica el archivo")
    print("                                         + borra los diarios ya cubiertos")
    print("                                         + avisa por correo al administrador")
    print("   Día 1 de cada mes                 ->  respaldo MENSUAL")
    print()
    print("Se conservan: 7 diarios, 4 semanales y 12 mensuales.")
    print()


def _recordar_ajuste_manual() -> None:
    """Explica el ajuste que ``schtasks`` no permite configurar por línea de comandos."""
    print("-" * 64)
    print("AJUSTE RECOMENDADO (un minuto, una sola vez)")
    print()
    print("Si la computadora está apagada a medianoche, el respaldo se pierde.")
    print("Para que se haga al encenderla:")
    print()
    print("  1. Abra el «Programador de tareas» de Windows")
    print("  2. Busque la tarea:", NOMBRE_TAREA)
    print("  3. Clic derecho -> Propiedades -> pestaña «Configuración»")
    print("  4. Marque: «Ejecutar la tarea lo antes posible si se omitió")
    print("     un inicio programado»")
    print("  5. Aceptar")
    print("-" * 64)


def _leer_argumentos(argumentos: list[str] | None) -> argparse.Namespace:
    """
    Interpreta los argumentos de línea de comandos.

    Args:
        argumentos: Argumentos a interpretar; None para leer ``sys.argv``.

    Returns:
        Opciones ya interpretadas.
    """
    analizador = argparse.ArgumentParser(
        prog="instalar_tarea",
        description="Instala la tarea programada de respaldo automático.",
    )
    grupo = analizador.add_mutually_exclusive_group()
    grupo.add_argument("--quitar", action="store_true", help="Desinstala la tarea.")
    grupo.add_argument("--estado", action="store_true", help="Consulta el estado de la tarea.")
    return analizador.parse_args(argumentos)


if __name__ == "__main__":
    sys.exit(principal())

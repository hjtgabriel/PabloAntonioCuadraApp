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
porque el programa está cerrado a medianoche.

La tarea se registra a partir de una definición XML y no con las opciones
sueltas de ``schtasks``, porque los valores por omisión de esa herramienta no
sirven en una laptop:

* «Iniciar solo si el equipo está con corriente alterna» viene **activado**, de
  modo que en un portátil con batería la tarea queda en cola y el respaldo no
  se hace nunca.
* «Detener si el equipo pasa a batería» viene **activado**, con el mismo efecto
  a mitad de ejecución.
* «Ejecutar lo antes posible si se omitió un inicio» viene **desactivado**, así
  que un respaldo perdido por tener el equipo apagado no se recupera.

El XML deja los tres ajustes como corresponde, sin que nadie tenga que
corregirlos a mano después.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
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

PLANTILLA_XML = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Respaldo automatico de la base de datos de la libreria Pablo Antonio Cuadra. Diario de lunes a sabado, semanal el domingo y mensual el dia 1.</Description>
    <URI>\\{nombre}</URI>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{inicio}</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{usuario}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <AllowHardTerminate>true</AllowHardTerminate>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
    <Priority>7</Priority>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{lanzador}</Command>
      <WorkingDirectory>{proyecto}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
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

    archivo_xml = Path(tempfile.gettempdir()) / f"{NOMBRE_TAREA}.xml"
    archivo_xml.write_text(_componer_xml(), encoding="utf-16")

    print(f"Registrando la tarea «{NOMBRE_TAREA}» para las {HORA_EJECUCION} de cada día…")
    resultado = subprocess.run(
        ["schtasks", "/Create", "/TN", NOMBRE_TAREA, "/XML", str(archivo_xml), "/F"],
        capture_output=True, text=True, check=False,
    )
    archivo_xml.unlink(missing_ok=True)

    if resultado.returncode != 0:
        print("\n[ERROR] No se pudo registrar la tarea:")
        print("  " + (resultado.stderr or resultado.stdout).strip())
        print("\n¿Abrió la consola como administrador? Hace falta para crear tareas.")
        return ERROR

    print("[LISTO] Tarea registrada.\n")

    if not _comprobar_lanzador():
        return ERROR
    if not _comprobar_ajustes():
        return ERROR

    _explicar_rotacion()
    return EXITO


def _componer_xml() -> str:
    """
    Arma la definición XML de la tarea con las rutas de este equipo.

    Returns:
        El XML listo para pasar a ``schtasks /XML``.
    """
    manana = datetime.now() + timedelta(days=1)
    inicio = manana.replace(
        hour=int(HORA_EJECUCION[:2]), minute=int(HORA_EJECUCION[3:]), second=0, microsecond=0
    )
    return PLANTILLA_XML.format(
        nombre=NOMBRE_TAREA,
        inicio=inicio.strftime("%Y-%m-%dT%H:%M:%S"),
        usuario=f"{os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}".strip("\\"),
        lanzador=LANZADOR,
        proyecto=RAIZ_PROYECTO,
    )


def _comprobar_ajustes() -> bool:
    """
    Verifica que la tarea quedara con los ajustes que necesita una laptop.

    Si «iniciar solo con corriente alterna» quedara activado, la tarea no se
    ejecutaría nunca mientras el equipo funcione con batería.

    Returns:
        True si los ajustes son los correctos.
    """
    consulta = (
        "$t = Get-ScheduledTask -TaskName '" + NOMBRE_TAREA + "'; "
        "\"$($t.Settings.DisallowStartIfOnBatteries)|"
        "$($t.Settings.StopIfGoingOnBatteries)|$($t.Settings.StartWhenAvailable)\""
    )
    resultado = subprocess.run(
        ["powershell", "-NoProfile", "-Command", consulta],
        capture_output=True, text=True, check=False,
    )
    valores = resultado.stdout.strip().split("|")
    if len(valores) != 3:
        print("[AVISO] No se pudieron comprobar los ajustes de la tarea.\n")
        return True

    sin_bateria, para_con_bateria, recupera = (v.strip().lower() == "true" for v in valores)
    if sin_bateria or para_con_bateria or not recupera:
        print("\n[ERROR] La tarea quedó con ajustes que impedirían el respaldo:")
        if sin_bateria:
            print("  - No arrancaría mientras el equipo esté con batería.")
        if para_con_bateria:
            print("  - Se detendría al pasar a batería.")
        if not recupera:
            print("  - No recuperaría un respaldo perdido por tener el equipo apagado.")
        return False

    print("[LISTO] La tarea funciona con batería y recupera ejecuciones perdidas.\n")
    return True


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

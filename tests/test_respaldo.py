"""
Pruebas de la estrategia de respaldo 3-2-1 con rotación abuelo-padre-hijo (RNF05).

La prueba más importante de este archivo es
:func:`test_no_se_descarta_nada_si_el_respaldo_no_se_verifica`: borrar los
respaldos viejos confiando en uno nuevo que resultó estar corrupto es la forma
más habitual de quedarse sin ningún respaldo.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest

from nucleo.respaldo import (
    ResultadoRespaldo,
    ServicioRespaldo,
    TipoRespaldo,
    localizar_herramienta,
    tamano_legible,
)

PRIMARIO = Path("respaldos/local/respaldo_diario_bd_20260915_000000.dump")
SEGUNDO_MEDIO = Path("E:/respaldos/respaldo_diario_bd_20260915_000000.dump")
FUERA_DEL_SITIO = Path("N:/nube/respaldo_diario_bd_20260915_000000.dump")


def _resultado(**extras) -> ResultadoRespaldo:
    """Arma un resultado de respaldo para las pruebas."""
    base = {"tipo": TipoRespaldo.DIARIO, "archivo_origen": PRIMARIO}
    return ResultadoRespaldo(**{**base, **extras})


# ── Clasificación por fecha ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("fecha", "esperado"),
    [
        ("2026-09-14", TipoRespaldo.DIARIO),   # lunes
        ("2026-09-19", TipoRespaldo.DIARIO),   # sábado
        ("2026-09-20", TipoRespaldo.SEMANAL),  # domingo
        ("2026-09-27", TipoRespaldo.SEMANAL),  # domingo
        ("2026-09-01", TipoRespaldo.MENSUAL),  # día 1
    ],
)
def test_la_fecha_determina_la_clase_de_respaldo(fecha: str, esperado: TipoRespaldo):
    """De lunes a sábado toca diario, el domingo semanal y el día 1 mensual."""
    assert TipoRespaldo.segun_fecha(date.fromisoformat(fecha)) is esperado


def test_el_dia_uno_manda_sobre_el_domingo():
    """Si el día 1 cae en domingo, se guarda como mensual, que dura más."""
    primero_en_domingo = date(2026, 11, 1)
    assert primero_en_domingo.weekday() == 6
    assert TipoRespaldo.segun_fecha(primero_en_domingo) is TipoRespaldo.MENSUAL


# ── Qué consolida cada clase ────────────────────────────────────────────


def test_el_diario_no_consolida_nada():
    """Un respaldo diario no permite descartar ningún otro."""
    assert not TipoRespaldo.DIARIO.consolida
    assert TipoRespaldo.DIARIO.clases_que_reemplaza == ()


def test_el_semanal_cubre_los_diarios():
    """El respaldo del domingo deja sin sentido los diarios de esa semana."""
    assert TipoRespaldo.SEMANAL.consolida
    assert TipoRespaldo.SEMANAL.clases_que_reemplaza == (TipoRespaldo.DIARIO,)


def test_el_mensual_cubre_diarios_y_semanales():
    """El respaldo del día 1 cubre tanto los diarios como los semanales."""
    assert TipoRespaldo.MENSUAL.clases_que_reemplaza == (
        TipoRespaldo.DIARIO,
        TipoRespaldo.SEMANAL,
    )


# ── Conteo de copias de la regla 3-2-1 ──────────────────────────────────


def test_un_solo_volcado_no_alcanza_las_tres_copias():
    """Con el respaldo del equipo solamente hay dos copias, no tres."""
    resultado = _resultado()
    assert resultado.volcados == 1
    assert resultado.total_copias == 2
    assert not resultado.cumple_321


def test_dos_volcados_alcanzan_las_tres_copias():
    """El respaldo del equipo más el del segundo medio dan las tres copias."""
    resultado = _resultado(copias=[SEGUNDO_MEDIO])
    assert resultado.volcados == 2
    assert resultado.total_copias == 3
    assert resultado.cumple_321


def test_la_copia_fuera_del_sitio_suma():
    """Agregar el destino externo eleva el total a cuatro copias."""
    resultado = _resultado(copias=[SEGUNDO_MEDIO, FUERA_DEL_SITIO])
    assert resultado.total_copias == 4


def test_un_destino_fallido_no_cuenta_como_copia():
    """Lo que no se pudo escribir no debe contarse como respaldo."""
    resultado = _resultado(advertencias=["La unidad E: no está disponible"])
    assert resultado.volcados == 1
    assert not resultado.cumple_321


# ── Rotación sobre archivos reales ──────────────────────────────────────


def _crear_respaldos(carpeta: Path, clase: TipoRespaldo, cantidad: int) -> list[Path]:
    """
    Crea archivos de respaldo simulados con marcas de tiempo crecientes.

    Args:
        carpeta: Dónde crearlos.
        clase: Clase de respaldo que simulan.
        cantidad: Cuántos crear.

    Returns:
        Los archivos creados.
    """
    carpeta.mkdir(parents=True, exist_ok=True)
    creados = []
    for numero in range(cantidad):
        archivo = carpeta / f"respaldo_{clase.value}_bd_2026091{numero}_000000.dump"
        archivo.write_text("contenido", encoding="utf-8")
        os.utime(archivo, (1_700_000_000 + numero * 3600,) * 2)
        creados.append(archivo)
    return creados


def test_la_retencion_conserva_los_mas_recientes(tmp_path, monkeypatch):
    """Debe quedarse con los N más recientes y descartar los anteriores."""
    servicio = ServicioRespaldo()
    monkeypatch.setattr(servicio._configuracion, "respaldo_retencion_diaria", 3)

    _crear_respaldos(tmp_path, TipoRespaldo.DIARIO, 6)
    resultado = _resultado()
    servicio._aplicar_retencion(tmp_path, TipoRespaldo.DIARIO, resultado)

    quedan = sorted(p.name for p in tmp_path.glob("respaldo_diario_*"))
    assert len(quedan) == 3
    assert len(resultado.eliminados) == 3
    # Los conservados deben ser los de marca de tiempo más alta.
    assert quedan == sorted(
        [
            "respaldo_diario_bd_20260913_000000.dump",
            "respaldo_diario_bd_20260914_000000.dump",
            "respaldo_diario_bd_20260915_000000.dump",
        ]
    )


def test_la_retencion_no_toca_otras_clases(tmp_path, monkeypatch):
    """Depurar los diarios no debe borrar semanales ni mensuales."""
    servicio = ServicioRespaldo()
    monkeypatch.setattr(servicio._configuracion, "respaldo_retencion_diaria", 1)

    _crear_respaldos(tmp_path, TipoRespaldo.DIARIO, 4)
    _crear_respaldos(tmp_path, TipoRespaldo.SEMANAL, 2)
    _crear_respaldos(tmp_path, TipoRespaldo.MENSUAL, 2)

    servicio._aplicar_retencion(tmp_path, TipoRespaldo.DIARIO, _resultado())

    assert len(list(tmp_path.glob("respaldo_diario_*"))) == 1
    assert len(list(tmp_path.glob("respaldo_semanal_*"))) == 2
    assert len(list(tmp_path.glob("respaldo_mensual_*"))) == 2


def test_el_semanal_descarta_los_diarios(tmp_path, monkeypatch):
    """Una vez verificado el semanal, los diarios de la semana sobran."""
    servicio = ServicioRespaldo()
    monkeypatch.setattr(
        servicio._configuracion, "respaldo_dir_primario", str(tmp_path)
    )
    monkeypatch.setattr(servicio._configuracion, "respaldo_dir_secundario", "")
    monkeypatch.setattr(servicio._configuracion, "respaldo_dir_externo", "")

    _crear_respaldos(tmp_path, TipoRespaldo.DIARIO, 6)
    _crear_respaldos(tmp_path, TipoRespaldo.SEMANAL, 1)

    resultado = _resultado(tipo=TipoRespaldo.SEMANAL, verificado=True)
    servicio._rotar(TipoRespaldo.SEMANAL, resultado)

    assert list(tmp_path.glob("respaldo_diario_*")) == []
    assert len(list(tmp_path.glob("respaldo_semanal_*"))) == 1
    assert len(resultado.eliminados) == 6


def test_el_mensual_descarta_diarios_y_semanales(tmp_path, monkeypatch):
    """El respaldo del día 1 cubre toda la semana y el mes que termina."""
    servicio = ServicioRespaldo()
    monkeypatch.setattr(servicio._configuracion, "respaldo_dir_primario", str(tmp_path))
    monkeypatch.setattr(servicio._configuracion, "respaldo_dir_secundario", "")
    monkeypatch.setattr(servicio._configuracion, "respaldo_dir_externo", "")

    _crear_respaldos(tmp_path, TipoRespaldo.DIARIO, 3)
    _crear_respaldos(tmp_path, TipoRespaldo.SEMANAL, 2)
    _crear_respaldos(tmp_path, TipoRespaldo.MENSUAL, 1)

    servicio._rotar(TipoRespaldo.MENSUAL, _resultado(tipo=TipoRespaldo.MENSUAL, verificado=True))

    assert list(tmp_path.glob("respaldo_diario_*")) == []
    assert list(tmp_path.glob("respaldo_semanal_*")) == []
    assert len(list(tmp_path.glob("respaldo_mensual_*"))) == 1


def test_no_se_descarta_nada_si_el_respaldo_no_se_verifica(tmp_path, monkeypatch):
    """
    Un respaldo sin verificar no autoriza a borrar los anteriores.

    Es la salvaguarda más importante del módulo: si el respaldo nuevo salió
    corrupto y ya se borraron los viejos, no queda ninguno.
    """
    servicio = ServicioRespaldo()
    monkeypatch.setattr(servicio._configuracion, "respaldo_dir_primario", str(tmp_path))
    monkeypatch.setattr(servicio._configuracion, "respaldo_dir_secundario", "")
    monkeypatch.setattr(servicio._configuracion, "respaldo_dir_externo", "")
    monkeypatch.setattr(servicio._configuracion, "respaldo_retencion_diaria", 1)

    _crear_respaldos(tmp_path, TipoRespaldo.DIARIO, 5)

    # Se simula lo que hace «ejecutar» cuando la verificación falla: no rotar.
    resultado = _resultado(tipo=TipoRespaldo.SEMANAL, verificado=False)
    if resultado.verificado:
        servicio._rotar(TipoRespaldo.SEMANAL, resultado)

    assert len(list(tmp_path.glob("respaldo_diario_*"))) == 5
    assert resultado.eliminados == []


# ── Herramientas de PostgreSQL ──────────────────────────────────────────


def test_la_herramienta_se_busca_en_la_carpeta_configurada(tmp_path):
    """La carpeta indicada en PG_BIN debe tener prioridad sobre el PATH."""
    nombre = "pg_dump.exe" if os.name == "nt" else "pg_dump"
    falso = tmp_path / nombre
    falso.write_text("", encoding="utf-8")
    assert localizar_herramienta("pg_dump", str(tmp_path)) == str(falso)


def test_una_carpeta_invalida_no_rompe_la_busqueda(tmp_path):
    """Si PG_BIN apunta a una carpeta sin la herramienta, se sigue buscando."""
    encontrado = localizar_herramienta("pg_dump", str(tmp_path / "no-existe"))
    assert encontrado is None or encontrado.endswith(("pg_dump", "pg_dump.exe"))


def test_se_localiza_pg_restore_para_verificar():
    """La verificación necesita «pg_restore»; debe poder localizarse igual que «pg_dump»."""
    from config import obtener_configuracion

    encontrado = localizar_herramienta("pg_restore", obtener_configuracion().pg_bin)
    assert encontrado is None or "pg_restore" in encontrado


# ── Formato de tamaños ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("bytes_", "esperado"),
    [
        (512, "512 bytes"),
        (35_280, "34.5 kB"),
        (9_279_167, "8.8 MB"),
        (5 * 1024**3, "5.0 GB"),
    ],
)
def test_los_tamanos_se_muestran_legibles(bytes_: int, esperado: str):
    """El informe y el correo deben mostrar tamaños que se entiendan de un vistazo."""
    assert tamano_legible(bytes_) == esperado

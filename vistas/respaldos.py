"""
Pantalla de respaldos (RNF05).

Explica la estrategia al usuario, permite lanzar un respaldo a mano y muestra
el estado de la automatización: si la tarea programada está instalada y si el
aviso por correo funciona.
"""

from __future__ import annotations

import threading

import flet as ft

from config import obtener_configuracion
from nucleo.correo import probar_configuracion
from nucleo.errores import ErrorRespaldo
from nucleo.respaldo import ResultadoRespaldo, ServicioRespaldo, tamano_legible
from tema import (
    ACENTO,
    AVISO,
    ERROR,
    ESPACIO,
    EXITO,
    SUPERFICIE,
    TEXTO,
    TEXTO_ATENUADO,
    estilo_boton,
)
from vistas.componentes.layout import pantalla, tarjeta
from vistas.componentes.notificaciones import avisar_error, avisar_exito

EXPLICACION = (
    "Todos los respaldos son completos: para restaurar basta un solo archivo, "
    "sin depender de respaldos anteriores. Lo que cambia entre ellos es cuánto "
    "tiempo se conservan."
)

ROTACION = (
    ("Lunes a sábado", "Respaldo diario", "Se conservan 7"),
    ("Domingo 00:00", "Respaldo semanal", "Se conservan 4; descarta los diarios"),
    ("Día 1 del mes", "Respaldo mensual", "Se conservan 12; descarta diarios y semanales"),
)

AVISO_VERIFICACION = (
    "Los respaldos antiguos solo se descartan después de comprobar que el nuevo "
    "se puede leer. Si la comprobación falla, no se borra nada."
)


class PantallaRespaldos:
    """Pantalla de generación, seguimiento y diagnóstico de respaldos."""

    def __init__(self, pagina: ft.Page) -> None:
        """
        Args:
            pagina: Página de Flet sobre la que se dibuja.
        """
        self._pagina = pagina
        self._configuracion = obtener_configuracion()
        self._resultado = ft.Column(spacing=4, tight=True)
        self._progreso = ft.ProgressRing(visible=False, width=20, height=20)
        self._boton = ft.Button(
            "Generar respaldo ahora",
            icon=ft.Icons.BACKUP,
            bgcolor=ACENTO,
            color=SUPERFICIE,
            style=estilo_boton(),
            on_click=self._generar,
        )
        self._boton_correo = ft.Button(
            "Probar el correo",
            icon=ft.Icons.MAIL,
            bgcolor=SUPERFICIE,
            color=TEXTO,
            style=estilo_boton(),
            on_click=self._probar_correo,
        )

    def construir(self) -> ft.Control:
        """
        Arma la pantalla de respaldos.

        Returns:
            El control raíz de la pantalla.
        """
        cuerpo = ft.Column(
            [
                tarjeta("Cómo funciona", self._explicacion(), ft.Icons.SHIELD),
                tarjeta("Rotación automática", self._tabla_rotacion(), ft.Icons.EVENT_REPEAT),
                tarjeta("Destinos configurados", self._destinos(), ft.Icons.FOLDER_COPY),
                tarjeta("Aviso por correo", self._estado_correo(), ft.Icons.MAIL),
                tarjeta(
                    "Respaldo manual",
                    ft.Column(
                        [ft.Row([self._boton, self._progreso], spacing=ESPACIO), self._resultado],
                        spacing=ESPACIO,
                    ),
                    ft.Icons.PLAY_CIRCLE,
                ),
            ],
            spacing=ESPACIO,
            scroll=ft.ScrollMode.AUTO,
        )
        return pantalla("Respaldos", cuerpo)

    # ── Secciones informativas ──────────────────────────────────

    def _explicacion(self) -> ft.Control:
        """Arma el texto que explica la estrategia al usuario."""
        return ft.Column(
            [
                ft.Text(EXPLICACION, color=TEXTO, size=14),
                ft.Row(
                    [
                        ft.Icon(ft.Icons.VERIFIED, color=EXITO, size=18),
                        ft.Text(AVISO_VERIFICACION, color=TEXTO, size=13, expand=True),
                    ],
                    spacing=ESPACIO,
                ),
            ],
            spacing=ESPACIO,
            tight=True,
        )

    def _tabla_rotacion(self) -> ft.Control:
        """Muestra qué respaldo se genera cada día y cuántos se conservan."""
        filas = [
            ft.Row(
                [
                    ft.Text(cuando, color=TEXTO, weight=ft.FontWeight.W_500, width=150),
                    ft.Text(que, color=ACENTO, weight=ft.FontWeight.BOLD, width=160),
                    ft.Text(retencion, color=TEXTO_ATENUADO, size=13, expand=True),
                ],
                spacing=ESPACIO,
            )
            for cuando, que, retencion in ROTACION
        ]
        filas.append(
            ft.Text(
                "La tarea programada de Windows la instala el administrador con: "
                "python -m herramientas.instalar_tarea",
                size=12,
                color=TEXTO_ATENUADO,
                selectable=True,
            )
        )
        return ft.Column(filas, spacing=ESPACIO, tight=True)

    def _destinos(self) -> ft.Control:
        """Enumera los destinos configurados y su papel en la regla 3-2-1."""
        destinos = [
            ("Copia en el equipo", self._configuracion.respaldo_dir_primario, True),
            ("Segundo medio (USB o red)", self._configuracion.respaldo_dir_secundario, True),
            ("Fuera del local (nube)", self._configuracion.respaldo_dir_externo, False),
        ]
        return ft.Column(
            [self._renglon_destino(n, r, o) for n, r, o in destinos],
            spacing=4,
            tight=True,
        )

    def _renglon_destino(self, nombre: str, ruta: str, obligatorio: bool) -> ft.Row:
        """
        Arma el renglón de un destino de respaldo.

        Args:
            nombre: Papel que cumple el destino.
            ruta: Carpeta configurada; puede estar vacía.
            obligatorio: Si su ausencia impide cumplir la regla.

        Returns:
            El renglón con su icono de estado.
        """
        configurado = bool(ruta)
        if configurado:
            icono, color = ft.Icons.CHECK_CIRCLE, EXITO
        else:
            icono, color = (ft.Icons.ERROR, ERROR) if obligatorio else (ft.Icons.WARNING, AVISO)

        return ft.Row(
            [
                ft.Icon(icono, color=color, size=18),
                ft.Text(f"{nombre}:", color=TEXTO, weight=ft.FontWeight.W_500),
                ft.Text(
                    ruta or "sin configurar (defínalo en el archivo .env)",
                    color=TEXTO_ATENUADO if configurado else color,
                    size=13,
                    expand=True,
                ),
            ],
            spacing=ESPACIO,
        )

    def _estado_correo(self) -> ft.Control:
        """Muestra si el aviso por correo está configurado y permite probarlo."""
        if self._configuracion.correo_configurado:
            icono, color = ft.Icons.CHECK_CIRCLE, EXITO
            texto = (
                f"Los avisos del respaldo semanal irán a "
                f"{self._configuracion.correo_destinatario}"
            )
        else:
            icono, color = ft.Icons.WARNING, AVISO
            texto = "Sin configurar. Complete las variables CORREO_* en el archivo .env"

        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(icono, color=color, size=18),
                        ft.Text(texto, color=TEXTO, size=13, expand=True),
                    ],
                    spacing=ESPACIO,
                ),
                ft.Text(
                    "Con Gmail hay que usar una «contraseña de aplicación», no la de la cuenta.",
                    size=12,
                    color=TEXTO_ATENUADO,
                ),
                self._boton_correo,
            ],
            spacing=ESPACIO,
            tight=True,
        )

    # ── Acciones ────────────────────────────────────────────────

    def _generar(self, _evento: ft.ControlEvent) -> None:
        """Lanza el respaldo en segundo plano para no congelar la ventana."""
        self._ocupado(True)
        self._resultado.controls = []
        self._pagina.update()

        threading.Thread(target=self._ejecutar_respaldo, daemon=True).start()

    def _ejecutar_respaldo(self) -> None:
        """Ejecuta el respaldo y vuelca el resultado en la pantalla."""
        try:
            resultado = ServicioRespaldo().ejecutar()
        except ErrorRespaldo as error:
            self._mostrar_fallo(str(error))
            return
        except Exception as error:  # noqa: BLE001 - último recurso para no tumbar la interfaz
            self._mostrar_fallo(f"Ocurrió un problema inesperado: {error}")
            return

        self._mostrar_resultado(resultado)

    def _probar_correo(self, _evento: ft.ControlEvent) -> None:
        """Comprueba las credenciales de correo sin enviar ningún mensaje."""
        self._ocupado(True)
        self._pagina.update()
        threading.Thread(target=self._ejecutar_prueba_correo, daemon=True).start()

    def _ejecutar_prueba_correo(self) -> None:
        """Ejecuta la prueba de correo y muestra el resultado."""
        funciona, mensaje = probar_configuracion()
        self._ocupado(False)
        if funciona:
            avisar_exito(self._pagina, mensaje)
        else:
            avisar_error(self._pagina, mensaje)

    # ── Presentación del resultado ──────────────────────────────

    def _mostrar_resultado(self, resultado: ResultadoRespaldo) -> None:
        """
        Muestra en pantalla qué se generó y dónde quedó cada copia.

        Args:
            resultado: Detalle de la corrida de respaldo.
        """
        renglones: list[ft.Control] = [self._resumen(resultado)]

        renglones.append(self._renglon(ft.Icons.CHECK_CIRCLE, EXITO, str(resultado.archivo_origen)))
        renglones.extend(
            self._renglon(ft.Icons.CHECK_CIRCLE, EXITO, str(copia)) for copia in resultado.copias
        )

        if resultado.eliminados:
            renglones.append(
                self._renglon(
                    ft.Icons.DELETE_SWEEP,
                    TEXTO_ATENUADO,
                    f"{len(resultado.eliminados)} respaldos antiguos descartados por rotación",
                )
            )

        renglones.extend(
            self._renglon(ft.Icons.WARNING, AVISO, aviso) for aviso in resultado.advertencias
        )

        self._resultado.controls = renglones
        self._ocupado(False)
        avisar_exito(self._pagina, f"Respaldo {resultado.tipo.value} generado")

    def _resumen(self, resultado: ResultadoRespaldo) -> ft.Control:
        """
        Arma la línea de cabecera con el estado general del respaldo.

        Args:
            resultado: Detalle de la corrida de respaldo.

        Returns:
            Texto de resumen con su color según el estado.
        """
        if not resultado.verificado:
            color = ERROR
            estado = "no pasó la verificación; no se descartó ningún respaldo antiguo"
        elif resultado.cumple_321:
            color = EXITO
            estado = "verificado. Compruebe que el segundo destino esté en otra unidad"
        else:
            color = AVISO
            estado = "verificado, pero faltan destinos para las 3 copias"

        return ft.Column(
            [
                ft.Text(
                    f"Respaldo {resultado.tipo.value} {estado}",
                    color=color,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Text(
                    f"Base de datos: {tamano_legible(resultado.tamano_base_bytes)}  ·  "
                    f"Archivo: {tamano_legible(resultado.tamano_bytes)}  ·  "
                    f"Duración: {resultado.duracion_segundos:.1f} s  ·  "
                    f"{resultado.total_copias} copias en total",
                    color=TEXTO_ATENUADO,
                    size=12,
                ),
            ],
            spacing=2,
            tight=True,
        )

    def _mostrar_fallo(self, mensaje: str) -> None:
        """
        Muestra el motivo por el que no se pudo respaldar.

        Args:
            mensaje: Explicación del fallo.
        """
        self._resultado.controls = [self._renglon(ft.Icons.ERROR, ERROR, mensaje)]
        self._ocupado(False)
        avisar_error(self._pagina, mensaje)

    @staticmethod
    def _renglon(icono: str, color: str, texto: str) -> ft.Row:
        """
        Arma un renglón del informe de resultado.

        Args:
            icono: Icono de estado.
            color: Color del icono.
            texto: Ruta o mensaje a mostrar.

        Returns:
            El renglón listo para la lista de resultados.
        """
        return ft.Row(
            [
                ft.Icon(icono, color=color, size=16),
                ft.Text(texto, color=TEXTO, size=13, selectable=True, expand=True),
            ],
            spacing=ESPACIO,
        )

    def _ocupado(self, activo: bool) -> None:
        """
        Bloquea o libera los botones mientras hay una operación en curso.

        Args:
            activo: True mientras se trabaja, False al terminar.
        """
        self._boton.disabled = activo
        self._boton_correo.disabled = activo
        self._progreso.visible = activo
        self._pagina.update()


def pantalla_respaldos(pagina: ft.Page) -> ft.Control:
    """
    Arma la pantalla de respaldos.

    Args:
        pagina: Página de Flet sobre la que se dibuja.

    Returns:
        El control raíz de la pantalla.
    """
    return PantallaRespaldos(pagina).construir()

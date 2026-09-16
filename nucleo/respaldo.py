"""
Respaldos con la estrategia 3-2-1 y rotación abuelo-padre-hijo (RNF05).

La regla 3-2-1 pide **3 copias** de los datos, en **2 medios distintos**, con
**1 copia fuera del sitio**:

* Copia 1 — la base de datos en uso.
* Copia 2 — ``RESPALDO_DIR_PRIMARIO``: volcado en el disco del equipo.
* Copia 3 — ``RESPALDO_DIR_SECUNDARIO``: segundo medio (USB, disco externo o
  unidad de red), que satisface el «2» de la regla.
* Fuera del sitio — ``RESPALDO_DIR_EXTERNO``: carpeta sincronizada con la nube.

Sobre esa distribución se monta una **rotación abuelo-padre-hijo**: respaldos
diarios de lunes a sábado, uno semanal el domingo y uno mensual el día 1. Cada
clase tiene su propia retención, así que se conservan muchos puntos de
recuperación recientes y unos pocos antiguos.

**Todos los respaldos son completos.** ``pg_dump`` no genera incrementales, y a
la escala de esta librería tampoco convendrían: un volcado completo tarda menos
de un segundo y, sobre todo, para restaurar hace falta **un solo archivo**, sin
depender de una cadena de respaldos previos.

**Nunca se borra un respaldo viejo antes de verificar el nuevo.** Un respaldo
que no se ha comprobado no es un respaldo.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path

from config import RAIZ_PROYECTO, obtener_configuracion
from nucleo.errores import ErrorRespaldo

logger = logging.getLogger(__name__)

TIEMPO_LIMITE_SEGUNDOS = 600
TIEMPO_LIMITE_VERIFICACION = 120

DOMINGO = 6
PRIMER_DIA_DEL_MES = 1

CARPETAS_HABITUALES_WINDOWS = (
    r"C:\Program Files\PostgreSQL",
    r"C:\Program Files (x86)\PostgreSQL",
)
CARPETAS_HABITUALES_UNIX = (
    "/usr/lib/postgresql",
    "/usr/local/pgsql/bin",
    "/opt/homebrew/bin",
)


class TipoRespaldo(str, Enum):
    """
    Clase de respaldo dentro de la rotación abuelo-padre-hijo.

    Los tres son volcados completos; lo que cambia es cuánto tiempo se
    conservan y si al terminar consolidan los respaldos de clase inferior.
    """

    DIARIO = "diario"
    SEMANAL = "semanal"
    MENSUAL = "mensual"

    @classmethod
    def segun_fecha(cls, momento: date) -> "TipoRespaldo":
        """
        Decide qué clase de respaldo toca en una fecha dada.

        El día 1 manda sobre el domingo: si ambos coinciden, el respaldo se
        guarda como mensual, que es el de mayor permanencia.

        Args:
            momento: Fecha del respaldo.

        Returns:
            La clase que corresponde a esa fecha.
        """
        if momento.day == PRIMER_DIA_DEL_MES:
            return cls.MENSUAL
        if momento.weekday() == DOMINGO:
            return cls.SEMANAL
        return cls.DIARIO

    @property
    def consolida(self) -> bool:
        """
        Indica si esta clase resume a las inferiores y permite descartarlas.

        Un semanal cubre la semana que termina, y un mensual cubre además las
        semanas de ese mes.
        """
        return self is not TipoRespaldo.DIARIO

    @property
    def clases_que_reemplaza(self) -> tuple["TipoRespaldo", ...]:
        """Clases de respaldo que quedan cubiertas por esta una vez verificada."""
        if self is TipoRespaldo.MENSUAL:
            return (TipoRespaldo.DIARIO, TipoRespaldo.SEMANAL)
        if self is TipoRespaldo.SEMANAL:
            return (TipoRespaldo.DIARIO,)
        return ()


@dataclass(slots=True)
class ResultadoRespaldo:
    """
    Qué se logró en una corrida de respaldo.

    Attributes:
        tipo: Clase de respaldo generado.
        archivo_origen: Volcado escrito en el destino primario.
        copias: Rutas donde quedó replicado el volcado.
        advertencias: Destinos o pasos que fallaron, con su motivo.
        verificado: Si el volcado pasó la comprobación de integridad.
        eliminados: Respaldos antiguos que se descartaron tras verificar.
        tamano_bytes: Tamaño del archivo de respaldo.
        tamano_base_bytes: Tamaño que ocupa la base de datos.
        momento: Fecha y hora en que se generó.
        duracion_segundos: Cuánto tardó el volcado.
        correo_enviado: Si se avisó al administrador por correo.
    """

    tipo: TipoRespaldo
    archivo_origen: Path
    copias: list[Path] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)
    verificado: bool = False
    eliminados: list[Path] = field(default_factory=list)
    tamano_bytes: int = 0
    tamano_base_bytes: int = 0
    momento: datetime = field(default_factory=datetime.now)
    duracion_segundos: float = 0.0
    correo_enviado: bool = False

    @property
    def volcados(self) -> int:
        """Cantidad de archivos de respaldo escritos: el primario más sus réplicas."""
        return 1 + len(self.copias)

    @property
    def total_copias(self) -> int:
        """
        Cantidad total de copias de la información.

        Cuenta la base de datos en uso, que es la primera de las tres copias
        que pide la regla, más cada volcado escrito.
        """
        return 1 + self.volcados

    @property
    def cumple_321(self) -> bool:
        """
        Indica si la corrida alcanzó las tres copias que pide la regla.

        Atención: que haya tres copias no garantiza por sí solo que estén en
        **dos medios distintos**. Eso depende de que la carpeta del segundo
        destino apunte de verdad a otra unidad, y solo puede comprobarlo quien
        configuró el sistema.
        """
        return self.volcados >= 2


class ServicioRespaldo:
    """Genera, verifica, distribuye y rota los respaldos de la base de datos."""

    def __init__(self) -> None:
        self._configuracion = obtener_configuracion()

    # ── Operación principal ─────────────────────────────────────

    def ejecutar(self, tipo: TipoRespaldo | None = None) -> ResultadoRespaldo:
        """
        Genera un respaldo completo, lo verifica, lo replica y rota los antiguos.

        El orden importa: primero se verifica el respaldo nuevo y solo después
        se descartan los viejos. Si la verificación falla, no se borra nada.

        Args:
            tipo: Clase de respaldo a generar. Si es None se deduce de la fecha
                de hoy según la rotación abuelo-padre-hijo.

        Returns:
            Detalle de lo ocurrido: copias hechas, verificación, archivos
            descartados y tamaños.

        Raises:
            ErrorRespaldo: Si no se pudo generar el volcado inicial.
        """
        clase = tipo or TipoRespaldo.segun_fecha(date.today())
        carpeta_primaria = self._preparar_directorio(self._configuracion.respaldo_dir_primario)
        archivo = carpeta_primaria / self._nombre_archivo(clase)

        inicio = datetime.now()
        self._generar_volcado(archivo)
        duracion = (datetime.now() - inicio).total_seconds()

        resultado = ResultadoRespaldo(
            tipo=clase,
            archivo_origen=archivo,
            tamano_bytes=archivo.stat().st_size,
            tamano_base_bytes=self.tamano_base_datos(),
            duracion_segundos=duracion,
        )
        logger.info(
            "Respaldo %s generado en %.2f s: %s (%s)",
            clase.value, duracion, archivo, _tamano_legible(resultado.tamano_bytes),
        )

        resultado.verificado = self._verificar(archivo, resultado)
        for etiqueta, ruta in self._destinos_secundarios():
            self._replicar(archivo, ruta, etiqueta, resultado)

        if resultado.verificado:
            self._rotar(clase, resultado)
        else:
            resultado.advertencias.append(
                "No se descartó ningún respaldo antiguo porque el nuevo no pudo verificarse."
            )

        return resultado

    def tamano_base_datos(self) -> int:
        """
        Consulta cuánto ocupa la base de datos en disco.

        Returns:
            Tamaño en bytes; 0 si no se pudo consultar.
        """
        if self._configuracion.usa_sqlite:
            ruta = self._configuracion.ruta_sqlite
            return ruta.stat().st_size if ruta.exists() else 0

        from nucleo.base_datos import obtener_motor

        try:
            with obtener_motor().conexion() as conexion:
                return int(
                    conexion.consultar_escalar(
                        "SELECT pg_database_size(current_database())"
                    ) or 0
                )
        except Exception as error:  # noqa: BLE001 - el tamaño es informativo, no crítico
            logger.warning("No se pudo consultar el tamaño de la base: %s", error)
            return 0

    # ── Generación ──────────────────────────────────────────────

    def _generar_volcado(self, destino: Path) -> None:
        """
        Ejecuta ``pg_dump`` para volcar la base de datos completa.

        Args:
            destino: Archivo donde escribir el volcado.

        Raises:
            ErrorRespaldo: Si ``pg_dump`` no está instalado, se agota el tiempo
                o termina con error.
        """
        if self._configuracion.usa_sqlite:
            self._copiar_archivo_sqlite(destino)
            return

        herramienta = localizar_herramienta("pg_dump", self._configuracion.pg_bin)
        if herramienta is None:
            raise ErrorRespaldo(
                "No se encontró «pg_dump». Indique la carpeta «bin» de PostgreSQL "
                "en la variable PG_BIN del archivo .env, o agréguela al PATH."
            )

        comando = [
            herramienta,
            "--host", self._configuracion.db_host,
            "--port", str(self._configuracion.db_puerto),
            "--username", self._configuracion.db_usuario,
            "--dbname", self._configuracion.db_nombre,
            "--format", "custom",
            "--file", str(destino),
        ]

        try:
            proceso = subprocess.run(
                comando,
                capture_output=True,
                text=True,
                timeout=TIEMPO_LIMITE_SEGUNDOS,
                env=self._entorno_con_password(),
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise ErrorRespaldo("El respaldo superó el tiempo límite") from error

        if proceso.returncode != 0:
            raise ErrorRespaldo(f"pg_dump falló: {proceso.stderr.strip()}")

    def _copiar_archivo_sqlite(self, destino: Path) -> None:
        """
        Respalda una base SQLite copiando su archivo.

        Args:
            destino: Archivo donde dejar la copia.

        Raises:
            ErrorRespaldo: Si el archivo de base de datos no existe.
        """
        origen = self._configuracion.ruta_sqlite
        if not origen.exists():
            raise ErrorRespaldo(f"No existe la base de datos SQLite en {origen}")
        shutil.copy2(origen, destino)

    # ── Verificación ────────────────────────────────────────────

    def _verificar(self, archivo: Path, resultado: ResultadoRespaldo) -> bool:
        """
        Comprueba que el respaldo se pueda leer antes de fiarse de él.

        Usa ``pg_restore --list``, que recorre el índice del archivo sin
        restaurar nada. Si el volcado está truncado o corrupto, falla aquí.

        Args:
            archivo: Volcado a comprobar.
            resultado: Objeto donde anotar la advertencia si falla.

        Returns:
            True si el respaldo es legible.
        """
        if archivo.stat().st_size == 0:
            resultado.advertencias.append("El archivo de respaldo quedó vacío.")
            return False

        if self._configuracion.usa_sqlite:
            return True

        herramienta = localizar_herramienta("pg_restore", self._configuracion.pg_bin)
        if herramienta is None:
            resultado.advertencias.append(
                "No se encontró «pg_restore»: el respaldo no pudo verificarse."
            )
            return False

        try:
            proceso = subprocess.run(
                [herramienta, "--list", str(archivo)],
                capture_output=True,
                text=True,
                timeout=TIEMPO_LIMITE_VERIFICACION,
                check=False,
            )
        except subprocess.TimeoutExpired:
            resultado.advertencias.append("La verificación del respaldo superó el tiempo límite.")
            return False

        if proceso.returncode != 0:
            resultado.advertencias.append(
                f"El respaldo no pasó la verificación: {proceso.stderr.strip()}"
            )
            return False

        logger.info("Respaldo verificado correctamente: %s", archivo.name)
        return True

    # ── Distribución ────────────────────────────────────────────

    def _destinos_secundarios(self) -> list[tuple[str, str]]:
        """Devuelve los destinos de réplica configurados, con su etiqueta."""
        destinos = [("segundo medio", self._configuracion.respaldo_dir_secundario)]
        if self._configuracion.respaldo_dir_externo:
            destinos.append(("fuera del sitio", self._configuracion.respaldo_dir_externo))
        return [(etiqueta, ruta) for etiqueta, ruta in destinos if ruta]

    def _replicar(
        self, archivo: Path, destino: str, etiqueta: str, resultado: ResultadoRespaldo
    ) -> None:
        """
        Copia el volcado a un destino, anotando el fallo si no se puede.

        Args:
            archivo: Volcado a replicar.
            destino: Carpeta destino tal como viene de la configuración.
            etiqueta: Nombre legible del destino para los mensajes.
            resultado: Objeto donde registrar el éxito o la advertencia.
        """
        try:
            carpeta = self._preparar_directorio(destino)
            copia = carpeta / archivo.name
            shutil.copy2(archivo, copia)
            resultado.copias.append(copia)
            logger.info("Copia «%s» replicada en %s", etiqueta, copia)
        except OSError as error:
            aviso = f"No se pudo escribir la copia «{etiqueta}» en {destino}: {error}"
            resultado.advertencias.append(aviso)
            logger.warning(aviso)

    # ── Rotación abuelo-padre-hijo ──────────────────────────────

    def _rotar(self, clase: TipoRespaldo, resultado: ResultadoRespaldo) -> None:
        """
        Descarta respaldos que ya no hacen falta, en todos los destinos.

        Se ejecuta solo después de verificar el respaldo nuevo. Hace dos cosas:
        consolidar —un semanal verificado deja sin sentido los diarios de esa
        semana— y aplicar el límite de retención de cada clase.

        Args:
            clase: Clase del respaldo recién generado.
            resultado: Objeto donde anotar los archivos descartados.
        """
        carpetas = [self._configuracion.respaldo_dir_primario]
        carpetas.extend(ruta for _etiqueta, ruta in self._destinos_secundarios())

        for ruta in carpetas:
            carpeta = Path(ruta)
            if not carpeta.is_absolute():
                carpeta = RAIZ_PROYECTO / carpeta
            if not carpeta.is_dir():
                continue

            for reemplazada in clase.clases_que_reemplaza:
                self._borrar_todos(carpeta, reemplazada, resultado)

            for tipo in TipoRespaldo:
                self._aplicar_retencion(carpeta, tipo, resultado)

    def _borrar_todos(
        self, carpeta: Path, clase: TipoRespaldo, resultado: ResultadoRespaldo
    ) -> None:
        """
        Borra todos los respaldos de una clase, ya cubiertos por otro superior.

        Args:
            carpeta: Carpeta a depurar.
            clase: Clase de respaldo a descartar.
            resultado: Objeto donde anotar los archivos descartados.
        """
        for archivo in self._listar(carpeta, clase):
            self._borrar(archivo, resultado)

    def _aplicar_retencion(
        self, carpeta: Path, clase: TipoRespaldo, resultado: ResultadoRespaldo
    ) -> None:
        """
        Conserva solo los respaldos más recientes de una clase.

        Args:
            carpeta: Carpeta a depurar.
            clase: Clase de respaldo cuya retención aplicar.
            resultado: Objeto donde anotar los archivos descartados.
        """
        limite = self._retencion_de(clase)
        for sobrante in self._listar(carpeta, clase)[limite:]:
            self._borrar(sobrante, resultado)

    def _retencion_de(self, clase: TipoRespaldo) -> int:
        """
        Devuelve cuántas copias conservar de una clase.

        Args:
            clase: Clase de respaldo.

        Returns:
            Número de copias a conservar.
        """
        return {
            TipoRespaldo.DIARIO: self._configuracion.respaldo_retencion_diaria,
            TipoRespaldo.SEMANAL: self._configuracion.respaldo_retencion_semanal,
            TipoRespaldo.MENSUAL: self._configuracion.respaldo_retencion_mensual,
        }[clase]

    @staticmethod
    def _listar(carpeta: Path, clase: TipoRespaldo) -> list[Path]:
        """
        Lista los respaldos de una clase, del más reciente al más antiguo.

        Args:
            carpeta: Carpeta donde buscar.
            clase: Clase de respaldo a listar.

        Returns:
            Archivos ordenados por fecha de modificación descendente.
        """
        return sorted(
            carpeta.glob(f"respaldo_{clase.value}_*"),
            key=lambda ruta: ruta.stat().st_mtime,
            reverse=True,
        )

    @staticmethod
    def _borrar(archivo: Path, resultado: ResultadoRespaldo) -> None:
        """
        Borra un archivo de respaldo dejando constancia.

        Args:
            archivo: Archivo a borrar.
            resultado: Objeto donde anotar el descarte o el fallo.
        """
        try:
            archivo.unlink()
            resultado.eliminados.append(archivo)
            logger.info("Respaldo descartado por rotación: %s", archivo.name)
        except OSError as error:
            resultado.advertencias.append(f"No se pudo borrar {archivo.name}: {error}")

    # ── Apoyo interno ───────────────────────────────────────────

    def _nombre_archivo(self, clase: TipoRespaldo) -> str:
        """
        Compone el nombre del volcado con su clase y marca de tiempo.

        Args:
            clase: Clase de respaldo.

        Returns:
            Nombre de archivo, por ejemplo
            ``respaldo_semanal_PabloAntonioCuadraBD_20260920_000000.dump``.
        """
        marca = datetime.now().strftime("%Y%m%d_%H%M%S")
        extension = "db" if self._configuracion.usa_sqlite else "dump"
        return f"respaldo_{clase.value}_{self._configuracion.db_nombre}_{marca}.{extension}"

    def _entorno_con_password(self) -> dict[str, str]:
        """Devuelve el entorno del proceso con la contraseña para ``pg_dump``."""
        return {**os.environ, "PGPASSWORD": self._configuracion.db_password}

    @staticmethod
    def _preparar_directorio(ruta: str) -> Path:
        """
        Resuelve una ruta de la configuración y se asegura de que exista.

        Args:
            ruta: Ruta absoluta o relativa a la raíz del proyecto.

        Returns:
            La carpeta creada y lista para escribir.
        """
        carpeta = Path(ruta)
        if not carpeta.is_absolute():
            carpeta = RAIZ_PROYECTO / carpeta
        carpeta.mkdir(parents=True, exist_ok=True)
        return carpeta


# ── Localización de las herramientas de PostgreSQL ──────────────────────


def localizar_herramienta(nombre: str, carpeta_configurada: str = "") -> str | None:
    """
    Busca un ejecutable de PostgreSQL en el sistema.

    En Windows, el instalador no agrega su carpeta «bin» al PATH, así que
    buscarlo solo ahí haría fallar los respaldos en la mayoría de equipos. Se
    prueba, en orden: la carpeta indicada en la configuración, el PATH y las
    rutas de instalación habituales.

    Args:
        nombre: Nombre del ejecutable, por ejemplo «pg_dump» o «pg_restore».
        carpeta_configurada: Carpeta «bin» indicada en la variable PG_BIN.

    Returns:
        Ruta completa del ejecutable, o None si no se encontró.
    """
    archivo = f"{nombre}.exe" if os.name == "nt" else nombre

    if carpeta_configurada:
        candidato = Path(carpeta_configurada) / archivo
        if candidato.is_file():
            return str(candidato)

    del_path = shutil.which(nombre)
    if del_path:
        return del_path

    return _buscar_en_carpetas_habituales(archivo)


def localizar_pg_dump(carpeta_configurada: str = "") -> str | None:
    """
    Busca el ejecutable ``pg_dump``.

    Args:
        carpeta_configurada: Carpeta «bin» indicada en la variable PG_BIN.

    Returns:
        Ruta completa del ejecutable, o None si no se encontró.
    """
    return localizar_herramienta("pg_dump", carpeta_configurada)


def _buscar_en_carpetas_habituales(archivo: str) -> str | None:
    """
    Recorre las rutas donde el instalador de PostgreSQL suele dejar sus binarios.

    Cuando hay varias versiones instaladas se toma la más reciente.

    Args:
        archivo: Nombre del ejecutable con su extensión.

    Returns:
        Ruta completa del ejecutable, o None si no se encontró.
    """
    raices = CARPETAS_HABITUALES_WINDOWS if os.name == "nt" else CARPETAS_HABITUALES_UNIX
    encontrados: list[Path] = []

    for raiz in raices:
        base = Path(raiz)
        if not base.is_dir():
            continue
        directo = base / archivo
        if directo.is_file():
            encontrados.append(directo)
        encontrados.extend(
            candidato
            for version in base.iterdir()
            if version.is_dir()
            if (candidato := version / "bin" / archivo).is_file()
        )

    if not encontrados:
        return None
    return str(sorted(encontrados, key=lambda ruta: ruta.parts, reverse=True)[0])


def tamano_legible(bytes_: int) -> str:
    """
    Convierte un tamaño en bytes a la unidad más cómoda de leer.

    Args:
        bytes_: Tamaño en bytes.

    Returns:
        El tamaño con su unidad, por ejemplo «34.5 kB» u «8.8 MB».
    """
    if bytes_ < 1024:
        return f"{bytes_} bytes"

    tamano = float(bytes_)
    for unidad in ("kB", "MB", "GB"):
        tamano /= 1024
        if tamano < 1024:
            return f"{tamano:.1f} {unidad}"
    return f"{tamano:.1f} TB"


_tamano_legible = tamano_legible
"""Nombre interno conservado para las llamadas dentro de este módulo."""

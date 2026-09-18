"""
Autenticación de usuarios (RF01, RNF04).

El servicio valida la credencial contra el hash almacenado y, solo si coincide,
arma los datos de sesión. Ante un fallo devuelve siempre el mismo mensaje, sin
distinguir «usuario inexistente» de «contraseña incorrecta».

Dos decisiones que parecen detalles y no lo son:

* **Tarda lo mismo exista o no el usuario.** Antes, si el usuario no existía se
  saltaba el cálculo del hash por cortocircuito y la respuesta llegaba en
  microsegundos, frente a los ~220 ms de un usuario real. Medido, esa
  diferencia era de 3600 veces: el mensaje era idéntico, pero el reloj delataba
  qué identificadores estaban dados de alta. Ahora se verifica siempre, contra
  un hash señuelo cuando hace falta.

* **El límite de intentos vive aquí y no en la pantalla.** Estaba en
  ``vistas/login.py`` como un contador en memoria de la ventana, así que
  reiniciar la aplicación lo reiniciaba y cualquier otro llamador del servicio
  —un script, otra interfaz— tenía intentos ilimitados. Una regla de seguridad
  no puede depender de que la interfaz coopere.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from threading import Lock

from modulos.personal.modelos import UsuarioAutenticado
from modulos.personal.repositorio import UsuarioRepositorio
from nucleo.base_datos import Conexion
from nucleo.errores import ErrorAutenticacion
from nucleo.seguridad import cifrar_contrasena, verificar_contrasena

logger = logging.getLogger(__name__)

MENSAJE_CREDENCIALES = "Usuario o contraseña incorrectos"

INTENTOS_ANTES_DE_BLOQUEAR = 5
"""Fallos seguidos que se toleran antes de cerrar el acceso a ese usuario."""

SEGUNDOS_BLOQUEO = 30
"""Cuánto dura el bloqueo, y también la ventana en que se cuentan los fallos."""

_HASH_SENUELO = cifrar_contrasena("senuelo-para-igualar-el-tiempo-de-respuesta")
"""
Hash contra el que se compara cuando el usuario no existe.

No corresponde a ninguna contraseña utilizable: su único trabajo es que
verificar un usuario inexistente cueste lo mismo que verificar uno real.
"""


class ControlDeIntentos:
    """
    Cuenta los intentos fallidos por usuario y bloquea cuando se pasan.

    Guarda el estado en memoria del proceso, que es lo que corresponde a una
    aplicación de un solo terminal (RNF01). Si el sistema creciera a varios
    puestos, esta es la pieza que habría que llevar a la base de datos, y está
    aislada precisamente para que ese cambio no toque nada más.
    """

    def __init__(
        self,
        intentos: int = INTENTOS_ANTES_DE_BLOQUEAR,
        segundos: int = SEGUNDOS_BLOQUEO,
    ) -> None:
        """
        Args:
            intentos: Fallos tolerados dentro de la ventana.
            segundos: Duración del bloqueo y de la ventana de conteo.
        """
        self._intentos = intentos
        self._segundos = segundos
        self._fallos: dict[str, list[float]] = defaultdict(list)
        self._candado = Lock()

    def comprobar(self, usuario: str) -> None:
        """
        Rechaza el intento si el usuario está bloqueado.

        Args:
            usuario: Identificador de acceso.

        Raises:
            ErrorAutenticacion: Si aún no ha pasado el tiempo de bloqueo.
        """
        with self._candado:
            recientes = self._recientes(usuario)
            if len(recientes) < self._intentos:
                return
            espera = int(self._segundos - (time.monotonic() - recientes[0])) + 1

        logger.warning("Acceso bloqueado para «%s»: faltan %d s", usuario, espera)
        raise ErrorAutenticacion(f"Demasiados intentos fallidos. Espere {espera} segundos.")

    def anotar_fallo(self, usuario: str) -> None:
        """
        Registra un intento fallido.

        Args:
            usuario: Identificador de acceso.
        """
        with self._candado:
            self._recientes(usuario).append(time.monotonic())

    def limpiar(self, usuario: str) -> None:
        """
        Olvida los fallos de un usuario que acaba de entrar.

        Args:
            usuario: Identificador de acceso.
        """
        with self._candado:
            self._fallos.pop(usuario, None)

    def _recientes(self, usuario: str) -> list[float]:
        """
        Descarta los intentos caducados y devuelve los que siguen contando.

        Args:
            usuario: Identificador de acceso.

        Returns:
            Marcas de tiempo de los fallos vigentes.
        """
        limite = time.monotonic() - self._segundos
        vigentes = [marca for marca in self._fallos[usuario] if marca > limite]
        self._fallos[usuario] = vigentes
        return vigentes


_intentos = ControlDeIntentos()


class ServicioAutenticacion:
    """Valida credenciales y produce los datos de sesión."""

    def __init__(
        self,
        repositorio: UsuarioRepositorio | None = None,
        conexion: Conexion | None = None,
        control: ControlDeIntentos | None = None,
    ) -> None:
        """
        Args:
            repositorio: Repositorio a usar; útil para inyectar uno falso en pruebas.
            conexion: Conexión de una transacción en curso, si la hay.
            control: Contador de intentos a usar. Por omisión, el compartido
                por toda la aplicación; las pruebas inyectan el suyo para no
                arrastrar el estado de una a otra.
        """
        self._repositorio = repositorio or UsuarioRepositorio(conexion)
        self._control = control or _intentos

    def iniciar_sesion(self, nombreusuario: str, contrasena: str) -> UsuarioAutenticado:
        """
        Valida las credenciales y devuelve los datos de sesión (RF01).

        Args:
            nombreusuario: Identificador de acceso.
            contrasena: Contraseña en texto plano.

        Returns:
            Datos del usuario autenticado, incluido su rol (RF02).

        Raises:
            ErrorAutenticacion: Si falta un campo, si las credenciales no
                coinciden o si se agotaron los intentos. El mensaje no permite
                distinguir un usuario inexistente de una contraseña errónea.
        """
        usuario_limpio = (nombreusuario or "").strip()
        if not usuario_limpio or not contrasena:
            raise ErrorAutenticacion(MENSAJE_CREDENCIALES)

        self._control.comprobar(usuario_limpio)

        credencial = self._repositorio.obtener_credencial(usuario_limpio)
        hash_guardado = credencial.hash_contrasena if credencial else _HASH_SENUELO
        coincide = verificar_contrasena(contrasena, hash_guardado)

        if credencial is None or not coincide:
            self._control.anotar_fallo(usuario_limpio)
            logger.warning("Intento de acceso fallido para el usuario «%s»", usuario_limpio)
            raise ErrorAutenticacion(MENSAJE_CREDENCIALES)

        self._control.limpiar(usuario_limpio)
        logger.info(
            "Inicio de sesión de «%s» con rol «%s»",
            credencial.sesion.nombreusuario,
            credencial.sesion.rol,
        )
        return credencial.sesion

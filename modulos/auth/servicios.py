"""
Autenticación de usuarios (RF01, RNF04).

El servicio valida la credencial contra el hash almacenado y, solo si coincide,
arma los datos de sesión. Ante un fallo devuelve siempre el mismo mensaje, sin
distinguir «usuario inexistente» de «contraseña incorrecta», para no revelar
qué identificadores existen.
"""

from __future__ import annotations

import logging

from modulos.personal.modelos import UsuarioAutenticado
from modulos.personal.repositorio import UsuarioRepositorio
from nucleo.base_datos import Conexion
from nucleo.errores import ErrorAutenticacion
from nucleo.seguridad import verificar_contrasena

logger = logging.getLogger(__name__)

MENSAJE_CREDENCIALES = "Usuario o contraseña incorrectos"


class ServicioAutenticacion:
    """Valida credenciales y produce los datos de sesión."""

    def __init__(self, repositorio: UsuarioRepositorio | None = None, conexion: Conexion | None = None) -> None:
        """
        Args:
            repositorio: Repositorio a usar; útil para inyectar uno falso en pruebas.
            conexion: Conexión de una transacción en curso, si la hay.
        """
        self._repositorio = repositorio or UsuarioRepositorio(conexion)

    def iniciar_sesion(self, nombreusuario: str, contrasena: str) -> UsuarioAutenticado:
        """
        Valida las credenciales y devuelve los datos de sesión (RF01).

        Args:
            nombreusuario: Identificador de acceso.
            contrasena: Contraseña en texto plano.

        Returns:
            Datos del usuario autenticado, incluido su rol (RF02).

        Raises:
            ErrorAutenticacion: Si falta algún campo o las credenciales no
                coinciden. El mensaje es idéntico en todos los casos.
        """
        usuario_limpio = (nombreusuario or "").strip()
        if not usuario_limpio or not contrasena:
            raise ErrorAutenticacion(MENSAJE_CREDENCIALES)

        usuario = self._repositorio.buscar_por_nombre(usuario_limpio)
        if usuario is None or not verificar_contrasena(contrasena, usuario.contrasena):
            logger.warning("Intento de acceso fallido para el usuario «%s»", usuario_limpio)
            raise ErrorAutenticacion(MENSAJE_CREDENCIALES)

        sesion = self._repositorio.obtener_autenticado(usuario_limpio)
        if sesion is None:
            logger.error("El usuario «%s» existe pero no tiene empleado o rol asociado", usuario_limpio)
            raise ErrorAutenticacion(MENSAJE_CREDENCIALES)

        logger.info("Inicio de sesión de «%s» con rol «%s»", sesion.nombreusuario, sesion.rol)
        return sesion

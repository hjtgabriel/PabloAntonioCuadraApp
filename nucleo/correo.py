"""
Envío de avisos por correo electrónico.

Lo usa el respaldo semanal para informar al administrador (RNF05). Está
separado del módulo de respaldo a propósito: enviar un correo es una operación
de red que puede fallar por motivos ajenos al respaldo —no hay internet, el
servidor rechaza la clave, el destinatario está mal escrito— y **un fallo aquí
nunca debe dar por fallido un respaldo que sí se hizo bien**.

Por eso :func:`enviar_aviso` no lanza excepciones: devuelve si pudo enviar y
deja el motivo en el registro de eventos.

Con Gmail, la contraseña debe ser una «contraseña de aplicación» generada desde
la cuenta con la verificación en dos pasos activada; la contraseña normal no
funciona desde programas.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from config import obtener_configuracion

logger = logging.getLogger(__name__)

TIEMPO_LIMITE_SEGUNDOS = 30


def enviar_aviso(asunto: str, cuerpo: str) -> bool:
    """
    Envía un aviso al administrador, sin propagar errores.

    Args:
        asunto: Asunto del mensaje.
        cuerpo: Texto del mensaje.

    Returns:
        True si el correo salió; False si no estaba configurado o falló el
        envío. El motivo del fallo queda en el registro de eventos.
    """
    configuracion = obtener_configuracion()

    if not configuracion.correo_configurado:
        logger.info("Aviso por correo desactivado o incompleto; no se envía nada")
        return False

    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = configuracion.correo_usuario
    mensaje["To"] = configuracion.correo_destinatario
    mensaje.set_content(cuerpo)

    try:
        _entregar(mensaje, configuracion)
    except (smtplib.SMTPException, OSError) as error:
        logger.warning("No se pudo enviar el aviso por correo: %s", error)
        return False

    logger.info("Aviso enviado a %s", configuracion.correo_destinatario)
    return True


def _entregar(mensaje: EmailMessage, configuracion) -> None:
    """
    Entrega el mensaje al servidor de correo.

    Usa SMTPS directo en el puerto 465 y STARTTLS en cualquier otro, que es lo
    que esperan los servidores más comunes.

    Args:
        mensaje: Mensaje ya compuesto.
        configuracion: Configuración con los datos del servidor.

    Raises:
        smtplib.SMTPException: Si el servidor rechaza la conexión o las credenciales.
        OSError: Si no hay conexión de red.
    """
    servidor = configuracion.correo_servidor
    puerto = configuracion.correo_puerto

    if puerto == 465:
        with smtplib.SMTP_SSL(servidor, puerto, timeout=TIEMPO_LIMITE_SEGUNDOS) as sesion:
            sesion.login(configuracion.correo_usuario, configuracion.correo_password)
            sesion.send_message(mensaje)
        return

    with smtplib.SMTP(servidor, puerto, timeout=TIEMPO_LIMITE_SEGUNDOS) as sesion:
        sesion.starttls()
        sesion.login(configuracion.correo_usuario, configuracion.correo_password)
        sesion.send_message(mensaje)


def probar_configuracion() -> tuple[bool, str]:
    """
    Comprueba que el servidor acepte las credenciales, sin enviar ningún correo.

    Sirve para que el administrador valide la configuración desde la pantalla de
    respaldos antes de confiar en que los avisos van a llegar.

    Returns:
        Par (funcionó, mensaje explicativo).
    """
    configuracion = obtener_configuracion()

    if not configuracion.correo_activo:
        return False, "El aviso por correo está desactivado (CORREO_ACTIVO=false)"
    if not configuracion.correo_configurado:
        return False, "Faltan datos de correo en el archivo .env"

    try:
        if configuracion.correo_puerto == 465:
            with smtplib.SMTP_SSL(
                configuracion.correo_servidor, configuracion.correo_puerto,
                timeout=TIEMPO_LIMITE_SEGUNDOS,
            ) as sesion:
                sesion.login(configuracion.correo_usuario, configuracion.correo_password)
        else:
            with smtplib.SMTP(
                configuracion.correo_servidor, configuracion.correo_puerto,
                timeout=TIEMPO_LIMITE_SEGUNDOS,
            ) as sesion:
                sesion.starttls()
                sesion.login(configuracion.correo_usuario, configuracion.correo_password)
    except smtplib.SMTPAuthenticationError:
        return False, (
            "El servidor rechazó el usuario o la contraseña. Con Gmail hay que "
            "usar una «contraseña de aplicación», no la de la cuenta."
        )
    except (smtplib.SMTPException, OSError) as error:
        return False, f"No se pudo conectar con {configuracion.correo_servidor}: {error}"

    return True, f"Conexión correcta. Los avisos irán a {configuracion.correo_destinatario}"

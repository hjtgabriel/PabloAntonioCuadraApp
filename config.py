"""
Configuración centralizada de la aplicación.

Todos los valores se leen de variables de entorno o del archivo «.env».
Ningún secreto está escrito en el código: la contraseña de la base de datos no
tiene valor por omisión, de modo que una instalación mal configurada falla al
arrancar en vez de intentar conectarse con una credencial incrustada.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_PROYECTO = Path(__file__).resolve().parent

MOTORES_SOPORTADOS = ("postgresql", "sqlite")


class Configuracion(BaseSettings):
    """Parámetros de ejecución de la aplicación."""

    model_config = SettingsConfigDict(
        env_file=RAIZ_PROYECTO / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Aplicación ──────────────────────────────────────────────
    nombre_app: str = "Librería Pablo Antonio Cuadra"
    depurar: bool = Field(default=False, alias="DEBUG")
    nivel_log: str = Field(default="INFO", alias="LOG_LEVEL")

    # ── Base de datos ───────────────────────────────────────────
    db_motor: str = Field(default="postgresql", alias="DB_MOTOR")
    db_host: str = Field(default="localhost", alias="DB_HOST")
    db_puerto: int = Field(default=5432, alias="DB_PORT")
    db_nombre: str = Field(default="PabloAntonioCuadraBD", alias="DB_NAME")
    db_usuario: str = Field(default="postgres", alias="DB_USER")
    db_password: str = Field(default="", alias="DB_PASSWORD")
    db_pool_min: int = Field(default=2, ge=1, alias="DB_POOL_MIN")
    db_pool_max: int = Field(default=10, ge=1, alias="DB_POOL_MAX")
    pg_bin: str = Field(default="", alias="PG_BIN")
    """Carpeta «bin» de PostgreSQL; solo hace falta si «pg_dump» no está en el PATH."""

    # ── Respaldos 3-2-1 (RNF05) ─────────────────────────────────
    respaldo_dir_primario: str = Field(default="respaldos/local", alias="RESPALDO_DIR_PRIMARIO")
    respaldo_dir_secundario: str = Field(default="respaldos/externo", alias="RESPALDO_DIR_SECUNDARIO")
    respaldo_dir_externo: str = Field(default="", alias="RESPALDO_DIR_EXTERNO")

    # Rotación abuelo-padre-hijo: cuántas copias conservar de cada clase.
    respaldo_retencion_diaria: int = Field(default=7, ge=1, alias="RESPALDO_RETENCION_DIARIA")
    respaldo_retencion_semanal: int = Field(default=4, ge=1, alias="RESPALDO_RETENCION_SEMANAL")
    respaldo_retencion_mensual: int = Field(default=12, ge=1, alias="RESPALDO_RETENCION_MENSUAL")

    # ── Aviso por correo del respaldo semanal (RNF05) ───────────
    correo_activo: bool = Field(default=False, alias="CORREO_ACTIVO")
    correo_servidor: str = Field(default="smtp.gmail.com", alias="CORREO_SERVIDOR")
    correo_puerto: int = Field(default=587, alias="CORREO_PUERTO")
    correo_usuario: str = Field(default="", alias="CORREO_USUARIO")
    correo_password: str = Field(default="", alias="CORREO_PASSWORD")
    """Con Gmail debe ser una «contraseña de aplicación», no la contraseña de la cuenta."""
    correo_destinatario: str = Field(default="", alias="CORREO_DESTINATARIO")

    @property
    def correo_configurado(self) -> bool:
        """Indica si hay datos suficientes para intentar enviar el aviso."""
        return bool(
            self.correo_activo
            and self.correo_servidor
            and self.correo_usuario
            and self.correo_password
            and self.correo_destinatario
        )

    @field_validator("db_motor")
    @classmethod
    def _validar_motor(cls, valor: str) -> str:
        """Rechaza motores que la aplicación no sabe manejar."""
        motor = valor.strip().lower()
        if motor not in MOTORES_SOPORTADOS:
            admitidos = ", ".join(MOTORES_SOPORTADOS)
            raise ValueError(f"Motor de base de datos no soportado: {valor!r}. Use uno de: {admitidos}")
        return motor

    @field_validator("nivel_log")
    @classmethod
    def _validar_nivel_log(cls, valor: str) -> str:
        """Normaliza el nivel de registro a mayúsculas."""
        return valor.strip().upper()

    @property
    def usa_sqlite(self) -> bool:
        """True si el motor configurado es SQLite."""
        return self.db_motor == "sqlite"

    @property
    def ruta_sqlite(self) -> Path:
        """Ruta del archivo SQLite (solo aplica cuando el motor es sqlite)."""
        nombre = self.db_nombre
        if nombre in (":memory:", ""):
            return Path(":memory:")
        return RAIZ_PROYECTO / f"{nombre}.db"


@lru_cache
def obtener_configuracion() -> Configuracion:
    """
    Devuelve la configuración como instancia única.

    Se memoriza con ``lru_cache`` para no releer el archivo «.env» en cada
    llamada. Las pruebas pueden limpiar la caché con
    ``obtener_configuracion.cache_clear()``.
    """
    return Configuracion()

"""Pruebas del control de acceso y de la gestión de personal (RF01, RF02, RNF04)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from modulos.auth.servicios import ServicioAutenticacion
from modulos.personal.repositorio import UsuarioRepositorio
from modulos.personal.servicios import ServicioEmpleados, ServicioUsuarios
from modulos.ventas.servicios import ServicioVentas
from nucleo.errores import (
    ErrorAutenticacion,
    ErrorDuplicado,
    ErrorEnUso,
    ErrorNoEncontrado,
    ErrorValidacion,
)

DATOS_USUARIO = {
    "nombres": "Carlos",
    "apellidos": "López",
    "direccion": "Managua",
    "telefono": "88776655",
    "nombreusuario": "clopez",
    "contrasena": "clave-segura-1",
    "idrol": 2,
}


# ── Autenticación (RF01) ────────────────────────────────────────────────


def test_el_ingreso_con_credenciales_validas_funciona(usuario_admin):
    """Un usuario con credenciales correctas debe poder entrar (RF01)."""
    sesion = ServicioAutenticacion().iniciar_sesion("admin", "clave-segura-1")
    assert sesion.nombreusuario == "admin"


def test_la_sesion_trae_el_rol(usuario_admin):
    """La sesión debe informar el rol para armar el menú (RF02)."""
    sesion = ServicioAutenticacion().iniciar_sesion("admin", "clave-segura-1")
    assert sesion.rol == "Administrador"
    assert sesion.es_administrador


def test_el_vendedor_no_es_administrador(base_datos):
    """Un vendedor no debe tener privilegios de administración (RF02)."""
    ServicioUsuarios().crear_con_empleado(DATOS_USUARIO)
    sesion = ServicioAutenticacion().iniciar_sesion("clopez", "clave-segura-1")
    assert not sesion.es_administrador


def test_la_contrasena_incorrecta_se_rechaza(usuario_admin):
    """Una contraseña errónea no debe dar acceso."""
    with pytest.raises(ErrorAutenticacion):
        ServicioAutenticacion().iniciar_sesion("admin", "clave-equivocada")


def test_el_usuario_inexistente_se_rechaza(base_datos):
    """Un usuario que no existe no debe dar acceso."""
    with pytest.raises(ErrorAutenticacion):
        ServicioAutenticacion().iniciar_sesion("fantasma", "lo-que-sea")


def test_el_mensaje_de_error_no_revela_si_el_usuario_existe(usuario_admin):
    """
    El mensaje debe ser idéntico en ambos casos.

    Si difiriera, alguien podría averiguar qué identificadores existen probando
    nombres al azar.
    """
    servicio = ServicioAutenticacion()

    with pytest.raises(ErrorAutenticacion) as sin_usuario:
        servicio.iniciar_sesion("no-existe", "x")
    with pytest.raises(ErrorAutenticacion) as clave_mala:
        servicio.iniciar_sesion("admin", "x")

    assert str(sin_usuario.value) == str(clave_mala.value)


@pytest.mark.parametrize(("usuario", "clave"), [("", "x"), ("admin", ""), ("", "")])
def test_los_campos_vacios_se_rechazan(usuario_admin, usuario: str, clave: str):
    """No debe intentarse autenticar con campos en blanco."""
    with pytest.raises(ErrorAutenticacion):
        ServicioAutenticacion().iniciar_sesion(usuario, clave)


# ── Alta de usuarios (RNF04) ────────────────────────────────────────────


def test_la_contrasena_se_guarda_cifrada(base_datos):
    """La base de datos nunca debe contener la contraseña en texto plano (RNF04)."""
    ServicioUsuarios().crear_con_empleado(DATOS_USUARIO)
    guardado = UsuarioRepositorio().buscar_por_nombre("clopez")
    assert guardado is not None
    assert guardado.contrasena != "clave-segura-1"
    assert guardado.contrasena.startswith("pbkdf2_sha256$")


def test_el_listado_de_usuarios_no_expone_la_contrasena(usuario_admin):
    """El listado que ve la interfaz no debe incluir la columna de contraseña."""
    for fila in ServicioUsuarios().listar():
        assert "contrasena" not in fila


def test_no_se_repite_el_nombre_de_usuario(base_datos):
    """El identificador de acceso debe ser único."""
    ServicioUsuarios().crear_con_empleado(DATOS_USUARIO)
    with pytest.raises(ErrorDuplicado):
        ServicioUsuarios().crear_con_empleado(DATOS_USUARIO)


def test_se_rechaza_una_contrasena_corta(base_datos):
    """Una contraseña por debajo del mínimo debe rechazarse (RNF04)."""
    with pytest.raises(ErrorValidacion):
        ServicioUsuarios().crear_con_empleado({**DATOS_USUARIO, "contrasena": "123"})


def test_un_alta_fallida_no_deja_empleado_huerfano(base_datos):
    """
    Si falla la creación del usuario, tampoco debe quedar el empleado.

    Es la regresión del defecto que tenía la versión anterior, donde empleado y
    usuario se insertaban en transacciones distintas.
    """
    ServicioUsuarios().crear_con_empleado(DATOS_USUARIO)
    empleados_antes = len(ServicioEmpleados().listar())

    with pytest.raises(ErrorDuplicado):
        ServicioUsuarios().crear_con_empleado({**DATOS_USUARIO, "nombres": "Otro"})

    assert len(ServicioEmpleados().listar()) == empleados_antes


def test_se_rechaza_un_usuario_sin_rol(base_datos):
    """El rol es obligatorio para poder aplicar el RF02."""
    with pytest.raises(ErrorValidacion, match="rol"):
        ServicioUsuarios().crear_con_empleado({**DATOS_USUARIO, "idrol": ""})


# ── Modificación y baja ─────────────────────────────────────────────────


def test_actualizar_sin_contrasena_conserva_la_actual(base_datos):
    """Dejar el campo de contraseña vacío no debe cambiarla."""
    idusuario = ServicioUsuarios().crear_con_empleado(DATOS_USUARIO)
    hash_original = UsuarioRepositorio().buscar_por_nombre("clopez").contrasena

    ServicioUsuarios().actualizar(idusuario, {"nombres": "Carlos Alberto", "contrasena": ""})

    assert UsuarioRepositorio().buscar_por_nombre("clopez").contrasena == hash_original
    assert ServicioAutenticacion().iniciar_sesion("clopez", "clave-segura-1")


def test_actualizar_con_contrasena_nueva_la_cambia(base_datos):
    """Escribir una contraseña nueva debe reemplazar la anterior."""
    idusuario = ServicioUsuarios().crear_con_empleado(DATOS_USUARIO)

    ServicioUsuarios().actualizar(idusuario, {"contrasena": "otra-clave-9"})

    assert ServicioAutenticacion().iniciar_sesion("clopez", "otra-clave-9")
    with pytest.raises(ErrorAutenticacion):
        ServicioAutenticacion().iniciar_sesion("clopez", "clave-segura-1")


def test_eliminar_un_usuario_borra_su_empleado(base_datos):
    """Usuario y empleado se dan de baja juntos."""
    idusuario = ServicioUsuarios().crear_con_empleado(DATOS_USUARIO)
    ServicioUsuarios().eliminar(idusuario)
    assert ServicioEmpleados().listar() == []


def test_no_se_elimina_un_usuario_con_ventas(usuario_admin, producto_demo):
    """Borrar un vendedor con ventas rompería la trazabilidad del RF11."""
    ServicioVentas().registrar(
        usuario_admin, [{"idproducto": producto_demo, "cantidad": 1}], Decimal("50.00")
    )
    with pytest.raises(ErrorEnUso):
        ServicioUsuarios().eliminar(usuario_admin)


def test_eliminar_un_usuario_inexistente_falla(base_datos):
    """Borrar algo que no existe debe avisar con claridad."""
    with pytest.raises(ErrorNoEncontrado):
        ServicioUsuarios().eliminar(6666)


# ── Empleados ───────────────────────────────────────────────────────────


def test_el_empleado_sin_usuario_aparece_en_su_listado(base_datos):
    """Debe poder saberse qué empleados aún no tienen credencial."""
    ServicioEmpleados().crear({"nombres": "Rosa", "apellidos": "Díaz"})
    sin_usuario = ServicioEmpleados().listar_sin_usuario()
    assert [empleado.nombre_completo for empleado in sin_usuario] == ["Rosa Díaz"]


def test_el_empleado_con_usuario_no_aparece_en_ese_listado(base_datos):
    """Quien ya tiene credencial no debe figurar como pendiente."""
    ServicioUsuarios().crear_con_empleado(DATOS_USUARIO)
    assert ServicioEmpleados().listar_sin_usuario() == []


@pytest.mark.parametrize("campo", ["nombres", "apellidos"])
def test_nombres_y_apellidos_son_obligatorios(base_datos, campo: str):
    """Un empleado sin nombre o sin apellido no debe guardarse."""
    with pytest.raises(ErrorValidacion):
        ServicioEmpleados().crear({"nombres": "Rosa", "apellidos": "Díaz", campo: ""})


def test_la_busqueda_de_empleados_filtra(base_datos):
    """El listado de empleados debe filtrarse por texto (RF08)."""
    servicio = ServicioEmpleados()
    servicio.crear({"nombres": "Rosa", "apellidos": "Díaz"})
    servicio.crear({"nombres": "Pedro", "apellidos": "Gómez"})

    encontrados = servicio.listar("rosa")
    assert [fila["nombres"] for fila in encontrados] == ["Rosa"]


# ── Alta de usuario sobre un empleado existente ─────────────────────────


def test_dar_credencial_a_un_empleado_existente(base_datos):
    """El alta normal reutiliza los datos personales que ya están guardados."""
    idempleado = ServicioEmpleados().crear(
        {"nombres": "Rosa", "apellidos": "Díaz", "telefono": "88112233"}
    )

    idusuario = ServicioUsuarios().crear_para_empleado(
        {
            "idempleado": idempleado,
            "nombreusuario": "rdiaz",
            "contrasena": "clave-segura-1",
            "idrol": 2,
        }
    )

    usuario = [u for u in ServicioUsuarios().listar() if u["idusuario"] == idusuario][0]
    assert usuario["nombreusuario"] == "rdiaz"
    assert usuario["nombres"] == "Rosa"
    assert usuario["apellidos"] == "Díaz"


def test_no_se_crea_un_empleado_nuevo_al_dar_la_credencial(base_datos):
    """Dar acceso a un empleado no debe duplicarlo en la tabla de empleados."""
    idempleado = ServicioEmpleados().crear({"nombres": "Rosa", "apellidos": "Díaz"})
    antes = len(ServicioEmpleados().listar())

    ServicioUsuarios().crear_para_empleado(
        {
            "idempleado": idempleado,
            "nombreusuario": "rdiaz",
            "contrasena": "clave-segura-1",
            "idrol": 2,
        }
    )

    assert len(ServicioEmpleados().listar()) == antes


def test_un_empleado_no_puede_tener_dos_credenciales(base_datos):
    """Si el empleado ya tiene usuario, el alta debe rechazarse."""
    idempleado = ServicioEmpleados().crear({"nombres": "Rosa", "apellidos": "Díaz"})
    datos = {
        "idempleado": idempleado,
        "nombreusuario": "rdiaz",
        "contrasena": "clave-segura-1",
        "idrol": 2,
    }
    ServicioUsuarios().crear_para_empleado(datos)

    with pytest.raises(ErrorDuplicado):
        ServicioUsuarios().crear_para_empleado({**datos, "nombreusuario": "rdiaz2"})


def test_no_se_puede_dar_credencial_a_un_empleado_inexistente(base_datos):
    """Una clave de empleado que no existe debe rechazarse."""
    with pytest.raises(ErrorNoEncontrado):
        ServicioUsuarios().crear_para_empleado(
            {
                "idempleado": 9999,
                "nombreusuario": "fantasma",
                "contrasena": "clave-segura-1",
                "idrol": 2,
            }
        )


def test_hay_que_elegir_un_empleado(base_datos):
    """Dejar el empleado sin elegir debe dar un error claro."""
    with pytest.raises(ErrorValidacion, match="empleado"):
        ServicioUsuarios().crear_para_empleado(
            {
                "idempleado": "",
                "nombreusuario": "alguien",
                "contrasena": "clave-segura-1",
                "idrol": 2,
            }
        )


def test_el_empleado_con_credencial_sale_de_la_lista_de_disponibles(base_datos):
    """Quien ya tiene usuario no debe ofrecerse para recibir otro."""
    idempleado = ServicioEmpleados().crear({"nombres": "Rosa", "apellidos": "Díaz"})
    assert idempleado in [e.idempleado for e in ServicioEmpleados().listar_sin_usuario()]

    ServicioUsuarios().crear_para_empleado(
        {
            "idempleado": idempleado,
            "nombreusuario": "rdiaz",
            "contrasena": "clave-segura-1",
            "idrol": 2,
        }
    )

    assert idempleado not in [e.idempleado for e in ServicioEmpleados().listar_sin_usuario()]


def test_la_credencial_creada_sirve_para_entrar(base_datos):
    """El usuario recién creado debe poder iniciar sesión (RF01)."""
    idempleado = ServicioEmpleados().crear({"nombres": "Rosa", "apellidos": "Díaz"})
    ServicioUsuarios().crear_para_empleado(
        {
            "idempleado": idempleado,
            "nombreusuario": "rdiaz",
            "contrasena": "clave-segura-1",
            "idrol": 2,
        }
    )

    sesion = ServicioAutenticacion().iniciar_sesion("rdiaz", "clave-segura-1")
    assert sesion.nombre_completo == "Rosa Díaz"

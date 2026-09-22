# Librería Pablo Antonio Cuadra — Sistema de gestión y venta

Aplicación de escritorio para administrar el catálogo, el inventario y las
ventas de la librería. Funciona por completo en el equipo del local, sin
necesidad de servidor ni de conexión a internet (RNF01, RNF02).

- **Interfaz:** Flet 0.86.5
- **Base de datos:** PostgreSQL
- **Arquitectura:** monolito modular

---

## 1. Instalación

### 1.1. Requisitos

- Python 3.11 o superior
- PostgreSQL 13 o superior
- Las herramientas de línea de comandos de PostgreSQL (`psql`, `pg_dump`),
  necesarias para los respaldos

### 1.2. Pasos

```bash
# 1. Instalar las dependencias
pip install -r requirements.txt

# 2. Crear la base de datos
createdb PabloAntonioCuadraBD

# 3. Cargar el esquema, los índices y los roles iniciales
psql -d PabloAntonioCuadraBD -f docs/esquema_postgresql.sql

# 4. Configurar las credenciales
copy .env.example .env      # en Windows
cp .env.example .env        # en Linux o macOS
```

Abra el archivo `.env` y escriba la contraseña de PostgreSQL en `DB_PASSWORD`.

> El archivo `.env` contiene la contraseña de la base de datos y **nunca** debe
> subirse al repositorio. Ya está excluido en `.gitignore`.

```bash
# 5. Si actualiza desde una versión anterior, aplique las migraciones
psql -d PabloAntonioCuadraBD -f docs/migracion_001_precio_y_rol.sql

# 6. Crear el primer usuario administrador
python -m herramientas.crear_admin

# 7. Iniciar la aplicación
python main.py
```

---

## 2. Manual de usuario

### 2.1. Entrar al sistema

Escriba su usuario y su contraseña y pulse **Iniciar sesión**. Tras tres
intentos fallidos el acceso se bloquea durante 30 segundos.

Lo que vea en el menú depende de su rol:

| Sección | Vendedor | Administrador |
|---|:---:|:---:|
| Punto de venta | ✔ | ✔ |
| Productos | ✔ | ✔ |
| Inventario | ✔ | ✔ |
| Categorías, Marcas, Proveedores | ✔ | ✔ |
| Historial de precios e inventario | ✔ | ✔ |
| Reportes | — | ✔ |
| Usuarios, Empleados, Roles | — | ✔ |
| Respaldos | — | ✔ |

Al entrar, si algún producto llegó a su stock mínimo, aparece un aviso con los
nombres.

### 2.1.1. Ocultar el menú

El botón **☰** de la barra superior pliega el menú lateral, y la sección
abierta pasa a ocupar el ancho completo de la ventana. Viene bien en las
pantallas de tablas anchas, como el catálogo de productos. El botón se queda a
la vista para volver a mostrarlo.

### 2.2. Vender

1. Abra **Punto de venta**.
2. Escriba parte del nombre del producto en el buscador.
3. Pulse **Agregar** en cada producto. Ajuste las cantidades con **+** y **−**.
4. Escriba el efectivo que le entregó el cliente. El cambio se calcula solo.
5. Pulse **Cobrar**.

Aparecerá el comprobante con el número de venta, el total, el efectivo y el
cambio a entregar. El stock se descuenta automáticamente.

No se piden datos del cliente ni se aplican descuentos: la venta se cobra tal
cual.

**Si algo no cuadra:**

- *«Solo hay N unidades»*: el carrito supera las existencias. Baje la cantidad
  o registre una entrada de inventario.
- *«El efectivo recibido es menor que el total»*: revise el monto escrito.
- *«El carrito está vacío»*: agregue al menos un producto antes de cobrar.

### 2.2. Validaciones al escribir

Los campos avisan en el momento, debajo del propio campo y en rojo:

- **Efectivo recibido.** Solo admite números positivos. Si escribe letras o un
  importe negativo, aparece «Formato inválido: solo números positivos». El
  campo deja escribir para poder explicar qué está mal: bloquear la tecla en
  silencio no le dice al cajero por qué no pasa nada.
- **Teléfono** (empleados, usuarios y proveedores). Admite dígitos y el guion
  como separador, entre 7 y 15 cifras: `8676-7203` y `86767203` son válidos.
  Si escribe letras, espacios, paréntesis o el signo `+`, aparece «Solo números
  y guiones, sin letras ni símbolos».

> Se admite el guion y solo el guion. Permitir además espacios o paréntesis
> haría que el mismo número quedara guardado de varias formas y nadie pudiera
> buscarlo después.

### 2.2.1. La factura

Al cobrar aparece la factura de la venta, con cada artículo, su precio y su
subtotal, además del total, el efectivo recibido y el cambio.

El botón **Imprimir factura** guarda el documento en la carpeta `facturas/` y
lo abre en el navegador, donde se imprime con **Ctrl+P**. Desde esa misma
ventana se puede elegir «Guardar como PDF» en lugar de una impresora.

Cada factura queda guardada con su número y su fecha (por ejemplo
`factura_00042_20260917_150430.html`), así que puede volver a abrirse e
imprimirse más tarde sin pasar por el sistema.

La factura está maquetada para una **impresora de tickets**, no para una hoja:
el documento declara el ancho del rollo y el alto justo que ocupa la venta, de
modo que el papel se corta donde termina el ticket y no se expulsa una página
entera. Va en una sola columna, con tipografía monoespaciada para que los
importes queden alineados, y sin fondos de color, que una térmica no imprime.

Si su impresora usa otro rollo, cambie una línea en el archivo `.env`:

```
FACTURA_ANCHO_MM=80     # 80 para mostrador, 58 para portátiles
```

> Flet no incluye impresión propia, por eso la factura sale por el navegador.
> Es también lo que permite imprimir desde cualquier equipo sin instalar nada
> más.

### 2.3. Administrar productos

En **Productos** puede buscar, agregar, editar y eliminar artículos.

Marca, categoría, proveedor, descripción y precio de venta son obligatorios.

El **stock inicial** solo se pide al crear el producto. Después, las existencias
se mueven únicamente desde **Inventario** o mediante una venta, para que el
historial siempre explique de dónde salió cada unidad.

La columna **Stock** se colorea sola: rojo si llegó al mínimo, ámbar si está
cerca, verde si hay de sobra.

Un producto que ya se vendió no puede eliminarse, porque los reportes
históricos dejarían de cuadrar.

### 2.3.1. Filtrar por marca y categoría

En **Productos**, **Inventario**, **Historial de precios** e **Historial de
inventario** hay dos listas desplegables junto a la búsqueda: **Categoría** y
**Marca**.

- Los dos criterios se **suman**: elegir «Articulos escolares» y la marca
  «Pointer» deja solo los productos que cumplen ambas cosas.
- El filtro también se suma a lo que escriba en la búsqueda, en vez de
  reemplazarlo.
- Cuando hay algún filtro puesto aparece el botón **⊘** para quitarlos de una
  vez y volver a verlo todo.

En los dos historiales el filtro se aplica sobre los datos del producto al que
pertenece cada movimiento o cada cambio de precio.

### 2.4. Mover inventario

1. Abra **Inventario** y pulse una fila del catálogo.
2. A la derecha aparecerán sus existencias y su historial.
3. Elija el tipo de movimiento y la cantidad, y pulse **Registrar movimiento**.

| Tipo | Qué hace | Qué escribir en «Cantidad» |
|---|---|---|
| Entrada | Suma unidades | Cuántas ingresan |
| Salida | Resta unidades | Cuántas salen |
| Ajuste | Fija el stock exacto | **El stock final que debe quedar** |

Use **Ajuste** después de un conteo físico: si contó 37 unidades, escriba 37,
no la diferencia.

### 2.5. Historial de precios

Cada vez que cambia el precio de venta de un producto, el sistema lo anota solo.
En **Historial de precios** puede filtrar por producto y ver cuánto subió o
bajó cada vez.

### 2.6. Reportes

Solo para administración. Hay tres:

- **Ventas de la semana** — ventas de los últimos 7 días, con el total recibido
  en efectivo y el cambio entregado.
- **Artículos más vendidos** — ranking por unidades vendidas.
- **Nivel de stock** — existencias de cada producto, clasificadas en Crítico,
  Bajo o Normal, con las unidades sugeridas a reponer.

### 2.7. Usuarios y empleados

Solo para administración.

El alta va en dos pasos, y en este orden:

1. En **Empleados**, registre a la persona con sus nombres, apellidos, teléfono
   y dirección.
2. En **Usuarios**, pulse el botón de agregar y **elija a ese empleado** en la
   lista. Solo tendrá que escribir el nombre de usuario, la contraseña y el rol:
   los datos personales ya están en el sistema y no se repiten.

La lista solo ofrece empleados que todavía no tienen credencial, así que nadie
puede terminar con dos usuarios. Si el empleado que busca no aparece, o ya tiene
acceso, o falta registrarlo en **Empleados**.

Al **editar** un usuario sí aparecen sus datos personales, porque desde ahí se
corrigen los del empleado. Deje el campo de contraseña **en blanco** si no
quiere cambiarla: solo se reemplaza si escribe una nueva.

No se puede eliminar un usuario que ya registró ventas: el historial debe
conservar quién las hizo.

**Quién administra** lo decide la columna `administra` del rol, no cómo se
llame. Para dar permisos de administración a un rol nuevo:

```sql
UPDATE rol SET administra = TRUE WHERE nombrerol = 'Gerencia';
```

Antes se deducía de que el nombre empezara por «admin», de modo que renombrar
el rol dejaba a esa persona sin permisos sin ningún aviso.

### 2.8. Respaldos

Solo para administración. Pulse **Generar respaldo ahora** y el sistema copiará
la base de datos a los destinos configurados. Consulte la sección 3.

---

## 3. Respaldos (RNF05)

### 3.1. Qué tipo de respaldo hace

Un respaldo **lógico, completo, en caliente y consistente**, generado con
`pg_dump --format custom`.

| Característica | Valor | Qué significa |
|---|---|---|
| Lógico | sí | Exporta datos y estructura, no los archivos binarios del disco. Se puede restaurar en otra máquina o versión de PostgreSQL. |
| Completo | sí | Cada archivo contiene toda la base. **Para restaurar basta un solo archivo.** |
| Incremental | no | `pg_dump` no genera incrementales. A esta escala tampoco convienen: el volcado completo tarda menos de un segundo. |
| En caliente | sí | No hay que cerrar la aplicación ni detener el servidor. |
| Consistente | sí | Toma una foto transaccional: una venta hecha durante el respaldo queda dentro o fuera por completo, nunca a medias. |
| Comprimido | sí | El formato *custom* reduce mucho el tamaño. |

### 3.2. La regla 3-2-1

Pide **3 copias**, en **2 medios distintos**, con **1 fuera del local**.

| Copia | Dónde | Se configura en |
|---|---|---|
| 1 | La base de datos en uso | — |
| 2 | Disco del equipo | `RESPALDO_DIR_PRIMARIO` |
| 3 | USB, disco externo o unidad de red | `RESPALDO_DIR_SECUNDARIO` |
| Fuera del local | Carpeta sincronizada con la nube | `RESPALDO_DIR_EXTERNO` |

Para cumplir la regla de verdad, `RESPALDO_DIR_SECUNDARIO` debe apuntar a un
**medio físico distinto** (por ejemplo `E:/respaldos` en una memoria USB), no a
otra carpeta del mismo disco. El programa cuenta las copias, pero no puede
comprobar que estén en unidades diferentes: eso depende de cómo lo configure.

### 3.3. Rotación automática (abuelo-padre-hijo)

Una tarea programada corre **cada día a las 00:00** y decide sola qué toca:

| Cuándo | Qué genera | Qué hace además | Se conservan |
|---|---|---|---|
| Lunes a sábado | Respaldo **diario** | — | 7 |
| **Domingo** | Respaldo **semanal** | Verifica, descarta los diarios y **avisa por correo** | 4 |
| Día 1 del mes | Respaldo **mensual** | Verifica, descarta diarios y semanales | 12 |

**Ningún respaldo antiguo se borra sin antes verificar el nuevo.** La
comprobación se hace con `pg_restore --list`, que recorre el índice del archivo
sin restaurar nada. Si falla, no se descarta absolutamente nada.

### 3.4. Instalar la tarea programada

Abra la consola **como administrador** y ejecute:

```bash
python -m herramientas.instalar_tarea            # instala o actualiza
python -m herramientas.instalar_tarea --estado   # consulta cómo quedó
python -m herramientas.instalar_tarea --quitar   # desinstala
```

Después, un ajuste de un minuto que `schtasks` no permite hacer por línea de
comandos: abra el **Programador de tareas**, busque `RespaldoLibreriaPAC`, clic
derecho → **Propiedades** → pestaña **Configuración**, y marque **«Ejecutar la
tarea lo antes posible si se omitió un inicio programado»**. Sin eso, si la
computadora está apagada a medianoche, ese respaldo se pierde.

También puede lanzarlo a mano en cualquier momento:

```bash
python -m herramientas.respaldo_programado                # decide por la fecha
python -m herramientas.respaldo_programado --tipo semanal # fuerza la clase
python -m herramientas.respaldo_programado --sin-correo   # sin aviso
```

### 3.5. Aviso por correo

Tras el respaldo semanal o mensual, el administrador recibe un correo con la
fecha, **el tamaño de la base de datos**, el tamaño del archivo, la duración, el
resultado de la verificación, dónde quedó cada copia y qué respaldos se
descartaron.

Configúrelo en el `.env`:

```
CORREO_ACTIVO=true
CORREO_SERVIDOR=smtp.gmail.com
CORREO_PUERTO=587
CORREO_USUARIO=sucorreo@gmail.com
CORREO_PASSWORD=          # contraseña de aplicación, NO la de la cuenta
CORREO_DESTINATARIO=admin@ejemplo.com
```

> **Con Gmail**, la contraseña normal no funciona desde programas. Active la
> verificación en dos pasos y genere una **«contraseña de aplicación»** de 16
> caracteres en la configuración de seguridad de su cuenta de Google.

Puede comprobar que funciona sin enviar nada: en la pantalla **Respaldos**,
botón **«Probar el correo»**.

Si el correo falla (sin internet, clave mal puesta), **el respaldo sigue siendo
válido**: el aviso es informativo y nunca da por fallido un respaldo correcto.

### 3.6. ¿Afectan al rendimiento?

En la práctica, no. `pg_dump` toma un bloqueo `ACCESS SHARE`, que **no bloquea**
consultas ni ventas; solo impide operaciones de estructura (`ALTER TABLE`,
`VACUUM FULL`) que no ocurren durante el uso normal. El coste es momentáneo y
proporcional al tamaño de la base, y la tarea corre a medianoche, cuando no hay
nadie usando el sistema.

### 3.7. Restaurar un respaldo

```bash
pg_restore --clean --if-exists -d PabloAntonioCuadraBD respaldos/local/respaldo_semanal_XXXX.dump
```

`--clean` borra los objetos existentes antes de recrearlos, de modo que la base
queda exactamente como estaba en el momento del respaldo.

---

## 4. Estructura del proyecto

```
main.py                  Punto de entrada
config.py                Configuración leída de .env
tema.py                  Paleta corporativa y tema visual

nucleo/                  Infraestructura compartida
  errores.py             Excepciones propias
  seguridad.py           Cifrado de contraseñas (RNF04)
  dialecto.py            Diferencias entre motores de base de datos
  base_datos.py          Conexiones y transacciones
  repositorio.py         Repositorios base y de catálogo
  servicio.py            Servicio genérico de catálogos
  registro.py            Registro de eventos
  documentos.py          Guardado y apertura de documentos
  respaldo.py            Estrategia 3-2-1 (RNF05)

modulos/                 Lógica de negocio, un módulo por capacidad
  auth/                  Inicio de sesión
  catalogos/             Roles, categorías y marcas
  personal/              Empleados y usuarios
  proveedores/
  productos/             Catálogo e historial de precios
  inventario/            Movimientos de stock
  ventas/                Punto de venta y factura imprimible (RF11)
  reportes/

vistas/                  Interfaz
  componentes/           Piezas reutilizables
    campos.py            Fábrica de campos con validación
    dialogos.py          Formularios y confirmaciones
    tablas.py            Tabla con paginación y acciones
    registros.py         Lectura de registros y precarga de formularios
    filtros.py           Filtro por marca y categoría (RF08)
  crud.py                Pantalla de mantenimiento genérica
  dashboard.py           Panel principal y menú por rol (RF02)
  *.py                   Una pantalla por sección

herramientas/            Utilidades de instalación
docs/                    Esquema SQL
tests/                   Pruebas automatizadas
```

Cada módulo de negocio se divide en `modelos.py` (entidades),
`repositorio.py` (acceso a datos) y `servicios.py` (reglas de negocio). Ninguna
pantalla habla directamente con la base de datos.

---

## 5. Desarrollo

### Ejecutar las pruebas

```bash
python -m pytest
```

Las pruebas corren sobre SQLite en memoria, así que no hace falta tener
PostgreSQL levantado.

### Comprobaciones de calidad

Antes de confirmar un cambio conviene pasar las tres comprobaciones:

```bash
python -m pytest                       # las pruebas, todas en verde
python -m ruff check .                 # linter, sin avisos
python -m pytest --cov=. --cov-report=term-missing   # cobertura
```

El linter se configura en `pyproject.toml` (reglas `E`, `F`, `W`, `I`, `UP`,
`B`, `SIM`, `D`, línea de 100). `python -m ruff check . --fix` corrige solo lo
que puede arreglar sin cambiar el comportamiento.

Las reglas `D` exigen docstring en todo módulo, clase y función, con la
convención de Google (`Args:`, `Returns:`, `Raises:`). Así la documentación
interna no se degrada sin que nadie lo note. Hay tres excepciones declaradas:

- El largo de línea lo fija `line-length`, no la regla `E501`.
- El resumen de un docstring va en la línea siguiente a las comillas (`D212`).
- El `__init__` puede empezar directamente por `Args:`, porque el resumen ya
  está en el docstring de la clase (`D205`).

### Cómo se declaran los formularios

Un campo de un formulario se declara una sola vez, con
`definir_campo(clave, etiqueta, fabrica, ...)`:

```python
definir_campo(
    "descripcion",
    "Descripción",
    obligatorio=True,
    valor=valor("descripcion"),
    icono=ft.Icons.DESCRIPTION,
)
```

- `clave` es el nombre con el que el valor llega al servicio.
- `etiqueta` se usa a la vez para el rótulo y para los mensajes de error, de
  modo que nunca puedan quedar diciendo cosas distintas.
- `fabrica` es la función de `vistas/componentes/campos.py` que crea el control
  (`campo_texto` si se omite, o `campo_decimal`, `campo_entero`,
  `campo_seleccion`, `campo_contrasena`).
- `obligatorio` marca el asterisco del rótulo y activa la validación, en una
  sola declaración.

Para precargar un formulario al editar se usa `lector(registro)` o
`lector_de_texto(registro)` de `vistas/componentes/registros.py`: en un alta el
registro es `None` y cada campo sale con su valor inicial, sin repetir un
condicional por campo.

### Cambiar de motor de base de datos

Todo el SQL se escribe con marcadores `?` y pide al *dialecto* lo que varía
entre motores (búsqueda sin distinguir mayúsculas, recuperación de la clave
generada, operaciones con fechas). Para añadir un motor:

1. Cree una subclase de `DialectoSQL` en `nucleo/dialecto.py`.
2. Cree una subclase de `Motor` en `nucleo/base_datos.py`.
3. Regístrelo en el diccionario `DIALECTOS` y en `obtener_motor()`.

No hay que tocar ningún repositorio, servicio ni pantalla. SQLite ya está
implementado y sirve de ejemplo.

Esto no es una promesa: `tests/test_portabilidad_bd.py` inventa un motor que no
existía al escribir ninguno de los módulos y recorre con él el negocio
completo —acceso, catálogo, búsqueda, filtros, inventario, venta, factura y
reportes—. Además revisa el código en busca de consultas que se aten a un motor
(`ILIKE`, `INTERVAL`, `SERIAL`) o que interpolen valores en vez de pasarlos
como parámetros.

---

## 6. Requerimientos cubiertos

| Requerimiento | Dónde se cumple |
|---|---|
| RF01 Inicio de sesión | `modulos/auth`, `vistas/login.py` |
| RF02 Dos roles con permisos distintos | `vistas/dashboard.py` (tabla `SECCIONES`) |
| RF03 Alta y consulta de productos | `modulos/productos`, `vistas/productos.py` |
| RF04 Descuento automático de stock | `modulos/ventas/servicios.py` |
| RF05 Historial de inventario | `modulos/inventario` |
| RF06 Historial de precios | `modulos/productos/servicios.py` |
| RF07 Alerta de stock mínimo | `vistas/dashboard.py`, `modulos/inventario` |
| RF08 Búsqueda rápida por nombre | `BarraBusqueda` + `comparar_texto` del dialecto |
| RF09 Cálculo automático del total | `modulos/ventas/servicios.py` |
| RF10 Venta sin datos del cliente | `modulos/ventas/servicios.py` |
| RF11 Reporte semanal con efectivo y cambio | `modulos/reportes/servicios.py` |
| RF12 Artículos más vendidos | `modulos/reportes/servicios.py` |
| RF13 Reporte de nivel de stock | `modulos/reportes/servicios.py` |
| RNF01 Instalación local | PostgreSQL local, sin servicios externos |
| RNF02 Sin servidor dedicado | Aplicación de escritorio |
| RNF03 Interfaz sobria y legible | `tema.py`, paleta única |
| RNF04 Contraseñas cifradas | `nucleo/seguridad.py` (PBKDF2-SHA256) |
| RNF05 Respaldos 3-2-1 | `nucleo/respaldo.py`, `vistas/respaldos.py` |
| RNF06 Venta en menos de 3 s | Reserva de conexiones; prueba de tiempo incluida |
| RNF07 Más de 1.000 productos | Índices en el esquema y paginación en las tablas |
| RNF08 Manual de usuario | La sección 2 de este documento |

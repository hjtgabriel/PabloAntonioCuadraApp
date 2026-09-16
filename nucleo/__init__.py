"""
Núcleo compartido del monolito modular.

Aquí vive todo lo que no pertenece a un dominio concreto y que los módulos de
negocio reutilizan:

* :mod:`nucleo.errores` – jerarquía de excepciones propias.
* :mod:`nucleo.seguridad` – cifrado y verificación de contraseñas (RNF04).
* :mod:`nucleo.dialecto` – diferencias de sintaxis entre motores de base de datos.
* :mod:`nucleo.base_datos` – conexiones, transacciones y motores.
* :mod:`nucleo.repositorio` – repositorios base y de catálogo.
* :mod:`nucleo.servicio` – servicio genérico de catálogos.
* :mod:`nucleo.registro` – configuración del registro de eventos.
* :mod:`nucleo.respaldo` – estrategia de respaldo 3-2-1 (RNF05).

Ningún módulo de negocio importa el driver de base de datos: todo pasa por aquí.
"""

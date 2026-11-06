"""
Servicios de integración externa para el módulo de usuarios.

Funciones de verificación contra sistemas externos (ERP, SASA, etc.).
"""
import logging

logger = logging.getLogger(__name__)


def verificar_cliente_sasa(numero_cliente):
    """
    Verifica un número de cliente contra el sistema SASA.

    Placeholder: actualmente retorna datos simulados.
    Cuando se implemente la integración real, esta función consultará
    el servicio externo y retornará los datos del cliente.

    Args:
        numero_cliente (str): Número de cliente o ID SASA a verificar.

    Returns:
        dict: {
            "valido": bool,
            "razon_social": str,
            "cif_nit": str,
            "representante_legal": str,
            "email": str,
            "telefono": str,
            "direccion": str,
            "error": str | None,
        }
    """
    logger.info("Verificando cliente SASA: %s", numero_cliente)

    # --- PLACEHOLDER: simulación de respuesta ---
    # En el futuro, aquí irá la llamada al servicio real.
    clientes_simulados = {
        "SASA001": {
            "valido": True,
            "razon_social": "Autopartes del Caribe S.A.",
            "cif_nit": "123456789",
            "representante_legal": "Juan Pérez García",
            "email": "contacto@autopartescaribe.com",
            "telefono": "555-1234",
            "direccion": "Calle 12 #4-56, La Habana",
        },
        "SASA002": {
            "valido": True,
            "razon_social": "Distribuidora Oriental S.R.L.",
            "cif_nit": "987654321",
            "representante_legal": "María López Rodríguez",
            "email": "info@distoriental.com",
            "telefono": "555-5678",
            "direccion": "Avenida 5 #302, Santiago de Cuba",
        },
        "SASA003": {
            "valido": True,
            "razon_social": "Talleres Mecánicos Unidos C.A.",
            "cif_nit": "456789123",
            "representante_legal": "Carlos Martínez Soto",
            "email": "ventas@talleresunidos.com",
            "telefono": "555-9012",
            "direccion": "Carretera Central km 12, Santa Clara",
        },
    }

    resultado = clientes_simulados.get(numero_cliente.strip().upper())

    if resultado is None:
        return {
            "valido": False,
            "cliente_id": numero_cliente.strip(),
            "razon_social": "",
            "cif_nit": "",
            "representante_legal": "",
            "email": "",
            "telefono": "",
            "direccion": "",
            "error": "No se encontró un cliente con ese número en el sistema SASA.",
        }

    resultado["cliente_id"] = numero_cliente.strip()
    resultado["error"] = None
    return resultado

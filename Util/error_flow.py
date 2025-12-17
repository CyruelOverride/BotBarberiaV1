"""
Módulo centralizado para manejo de errores críticos.
Gestiona notificaciones, respuestas automáticas y flujo de respuesta del responsable.
"""

import os
import traceback
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from whatsapp_api import enviar_mensaje_whatsapp

# Variables de configuración
# Para testing: ambos números son el mismo
NUM_DESARROLLADOR = os.getenv("NUM_DESARROLLADOR", "59891453663")
NUM_RESPONSABLE = os.getenv("NUM_RESPONSABLE", "59891453663")

# Almacenamiento en memoria de errores activos
# Estructura: {error_id: {numero_cliente, numero_responsable, mensaje_cliente, message_id_responsable, timestamp, resuelto}}
ERROR_CONTEXT: Dict[str, Dict[str, Any]] = {}


def handle_critical_exception(
    error: Exception,
    mensaje_cliente: str,
    numero_cliente: str,
    contexto: str = ""
) -> None:
    """
    Función principal que orquesta el flujo completo de manejo de errores críticos.
    
    Args:
        error: Excepción capturada
        mensaje_cliente: Mensaje original del cliente que causó el error
        numero_cliente: Número del cliente
        contexto: Contexto adicional (ej: "chat.handle_text", "webhook_server")
    """
    # 1. Notificar al desarrollador
    notify_developer(error, mensaje_cliente, numero_cliente, contexto)
    
    # 2. Notificar al responsable y obtener message_id
    message_id_responsable = notify_responsable(mensaje_cliente, numero_cliente)
    
    # 3. Responder automáticamente al cliente
    respond_to_client(numero_cliente)
    
    # 4. Registrar contexto del error en memoria
    if message_id_responsable:
        error_id = register_error_context(
            numero_cliente=numero_cliente,
            numero_responsable=NUM_RESPONSABLE,
            message_id_responsable=message_id_responsable,
            mensaje_cliente=mensaje_cliente
        )
        print(f"✅ Error registrado con ID: {error_id}")


def notify_developer(
    error: Exception,
    mensaje_cliente: str,
    numero_cliente: str,
    contexto: str = ""
) -> None:
    """
    Envía mensaje técnico al desarrollador con detalles completos del error.
    
    Args:
        error: Excepción capturada
        mensaje_cliente: Mensaje original del cliente
        numero_cliente: Número del cliente
        contexto: Contexto donde ocurrió el error
    """
    if NUM_DESARROLLADOR == "<NUMERO>":
        print("⚠️ NUM_DESARROLLADOR no está configurado")
        return
    
    error_type = type(error).__name__
    error_msg = str(error)
    traceback_completo = traceback.format_exc()
    
    # Construir mensaje técnico
    mensaje = (
        f"🔴 *Error técnico en bot*\n\n"
        f"👤 Cliente: {numero_cliente}\n"
        f"💬 Mensaje original: {mensaje_cliente}\n"
        f"📍 Contexto: {contexto}\n"
        f"❌ Error: {error_type}\n"
        f"📝 Detalle: {error_msg}\n\n"
        f"📋 *Traceback completo:*\n"
        f"```\n{traceback_completo}\n```"
    )
    
    # Enviar mensaje
    resultado = enviar_mensaje_whatsapp(NUM_DESARROLLADOR, mensaje)
    if resultado.get("success"):
        print(f"📤 Mensaje de error enviado a desarrollador ({NUM_DESARROLLADOR})")
    else:
        print(f"⚠️ Error al enviar mensaje a desarrollador: {resultado.get('error')}")


def notify_responsable(
    mensaje_cliente: str,
    numero_cliente: str
) -> Optional[str]:
    """
    Envía mensaje al responsable operativo con instrucciones para responder.
    
    Args:
        mensaje_cliente: Mensaje original del cliente
        numero_cliente: Número del cliente
        
    Returns:
        message_id del mensaje enviado al responsable (si se pudo obtener)
    """
    if NUM_RESPONSABLE == "<NUMERO>":
        print("⚠️ NUM_RESPONSABLE no está configurado")
        return None
    
    # Construir mensaje para responsable
    mensaje = (
        f"⚠️ Error atendiendo a un cliente\n\n"
        f"Cliente: {numero_cliente}\n"
        f"Mensaje: {mensaje_cliente}\n\n"
        f"Respondé a este mensaje para contestarle al cliente."
    )
    
    # Enviar mensaje y obtener message_id
    resultado = enviar_mensaje_whatsapp(NUM_RESPONSABLE, mensaje)
    
    # Intentar extraer message_id de la respuesta
    message_id = None
    if resultado.get("success"):
        # WhatsApp API retorna message_id en el campo "message_id" del resultado
        message_id = resultado.get("message_id")
        # Si no está en message_id, intentar desde messages
        if not message_id and resultado.get("messages"):
            message_id = resultado.get("messages", [{}])[0].get("id") if resultado.get("messages") else None
    
    if message_id:
        print(f"📤 Mensaje de error enviado a responsable ({NUM_RESPONSABLE}), message_id: {message_id}")
    else:
        print(f"📤 Mensaje de error enviado a responsable ({NUM_RESPONSABLE}), pero no se pudo obtener message_id")
    
    return message_id


def respond_to_client(numero_cliente: str) -> None:
    """
    Envía mensaje automático al cliente indicando que se le responderá pronto.
    
    Args:
        numero_cliente: Número del cliente
    """
    mensaje = "Bro ando atendiendo un cliente enseguida te respondo"
    
    resultado = enviar_mensaje_whatsapp(numero_cliente, mensaje)
    if resultado.get("success"):
        print(f"📤 Mensaje automático enviado al cliente ({numero_cliente})")
    else:
        print(f"⚠️ Error al enviar mensaje automático al cliente: {resultado.get('error')}")


def register_error_context(
    numero_cliente: str,
    numero_responsable: str,
    message_id_responsable: str,
    mensaje_cliente: str
) -> str:
    """
    Guarda la relación error-cliente en memoria.
    
    Args:
        numero_cliente: Número del cliente
        numero_responsable: Número del responsable
        message_id_responsable: ID del mensaje enviado al responsable
        mensaje_cliente: Mensaje original del cliente
        
    Returns:
        error_id: ID único del error registrado
    """
    error_id = str(uuid.uuid4())
    
    ERROR_CONTEXT[error_id] = {
        "numero_cliente": numero_cliente,
        "numero_responsable": numero_responsable,
        "mensaje_cliente": mensaje_cliente,
        "message_id_responsable": message_id_responsable,
        "timestamp": datetime.now(),
        "resuelto": False
    }
    
    print(f"📝 Error registrado: {error_id} para cliente {numero_cliente}")
    return error_id


def get_error_by_message_id(message_id: str) -> Optional[Dict[str, Any]]:
    """
    Busca un error activo por message_id del mensaje enviado al responsable.
    
    Args:
        message_id: ID del mensaje al que el responsable está respondiendo
        
    Returns:
        Dict con información del error o None si no se encuentra
    """
    for error_id, error_data in ERROR_CONTEXT.items():
        if (error_data.get("message_id_responsable") == message_id and 
            not error_data.get("resuelto", False)):
            return {"error_id": error_id, **error_data}
    
    return None


def get_last_error_by_responsable(numero_responsable: str) -> Optional[Dict[str, Any]]:
    """
    Busca el último error activo para un responsable específico.
    Útil cuando el responsable responde sin hacer reply al mensaje.
    
    Args:
        numero_responsable: Número del responsable
        
    Returns:
        Dict con información del último error activo o None
    """
    errores_activos = [
        {"error_id": error_id, **error_data}
        for error_id, error_data in ERROR_CONTEXT.items()
        if (error_data.get("numero_responsable") == numero_responsable and 
            not error_data.get("resuelto", False))
    ]
    
    if not errores_activos:
        return None
    
    # Ordenar por timestamp (más reciente primero)
    errores_activos.sort(key=lambda x: x.get("timestamp", datetime.min), reverse=True)
    return errores_activos[0]


def handle_responsable_reply(
    numero_responsable: str,
    mensaje_responsable: str,
    replied_message_id: Optional[str] = None
) -> bool:
    """
    Maneja la respuesta del responsable y la reenvía al cliente afectado.
    
    Args:
        numero_responsable: Número del responsable que está respondiendo
        mensaje_responsable: Mensaje del responsable
        replied_message_id: ID del mensaje al que está respondiendo (opcional)
        
    Returns:
        True si se procesó correctamente, False si no se encontró error asociado
    """
    # Buscar error asociado
    error_data = None
    
    if replied_message_id:
        # Buscar por message_id (método preferido)
        error_data = get_error_by_message_id(replied_message_id)
    else:
        # Buscar último error activo del responsable
        error_data = get_last_error_by_responsable(numero_responsable)
    
    if not error_data:
        print(f"⚠️ No se encontró error activo para responsable {numero_responsable}")
        return False
    
    numero_cliente = error_data.get("numero_cliente")
    error_id = error_data.get("error_id")
    
    if not numero_cliente:
        print(f"⚠️ Error activo {error_id} no tiene número de cliente")
        return False
    
    # Reenviar EXACTAMENTE el mensaje del responsable al cliente
    resultado = enviar_mensaje_whatsapp(numero_cliente, mensaje_responsable)
    
    if resultado.get("success"):
        print(f"✅ Mensaje del responsable reenviado al cliente {numero_cliente}")
        # Marcar error como resuelto
        mark_error_resolved(error_id)
        return True
    else:
        print(f"⚠️ Error al reenviar mensaje al cliente: {resultado.get('error')}")
        return False


def mark_error_resolved(error_id: str) -> None:
    """
    Marca un error como resuelto.
    
    Args:
        error_id: ID del error a marcar como resuelto
    """
    if error_id in ERROR_CONTEXT:
        ERROR_CONTEXT[error_id]["resuelto"] = True
        print(f"✅ Error {error_id} marcado como resuelto")
    else:
        print(f"⚠️ Error {error_id} no encontrado en contexto")


def is_responsable(numero: str) -> bool:
    """
    Verifica si un número pertenece al responsable operativo.
    
    Args:
        numero: Número a verificar
        
    Returns:
        True si es el responsable, False en caso contrario
    """
    if NUM_RESPONSABLE == "<NUMERO>":
        return False
    
    # Normalizar ambos números para comparación
    from whatsapp_api import normalizar_numero_telefono
    numero_normalizado = normalizar_numero_telefono(numero)
    responsable_normalizado = normalizar_numero_telefono(NUM_RESPONSABLE)
    
    # Comparar números normalizados y también sin normalizar (por si acaso)
    return (numero_normalizado == responsable_normalizado or 
            numero == NUM_RESPONSABLE or
            numero_normalizado == NUM_RESPONSABLE or
            numero == responsable_normalizado)


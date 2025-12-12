"""
Utilidades para manejo de errores y registro de mensajes.
"""

import traceback
from whatsapp_api import enviar_mensaje_whatsapp

# Variables de configuración (hardcodear después)
num_desarrollador = "<NUMERO>"
num_empleado = "<NUMERO>"


def registrar_mensaje(numero_cliente, mensaje):
    """
    Registra un mensaje en consola sin guardar en base de datos.
    
    Args:
        numero_cliente: Número de teléfono del cliente
        mensaje: Contenido del mensaje
    """
    print(f"📨 Mensaje recibido de {numero_cliente}: {mensaje}")


def manejar_error(error, mensaje, numero_cliente, contexto_adicional: str = ""):
    """
    Maneja errores enviando notificaciones diferenciadas a empleado, desarrollador y número de notificación.
    
    Args:
        error: Excepción capturada
        mensaje: Mensaje original que provocó el error
        numero_cliente: Número de teléfono del cliente
        contexto_adicional: Contexto adicional sobre dónde ocurrió el error (opcional)
    """
    error_type = type(error).__name__
    error_msg = str(error)
    traceback_completo = traceback.format_exc()
    
    # Extraer información del contexto del traceback
    contexto_general = contexto_adicional
    if not contexto_general:
        # Intentar extraer el nombre de la función del traceback
        lineas_traceback = traceback_completo.split('\n')
        for linea in lineas_traceback:
            if 'File' in linea and '.py' in linea:
                # Extraer nombre del archivo y función si es posible
                if 'in ' in linea:
                    partes = linea.split('in ')
                    if len(partes) > 1:
                        contexto_general = f"Error en: {partes[1].strip()}"
                break
    
    # Mensaje para empleado (información básica)
    mensaje_empleado = (
        f"⚠️ *Error en conversación*\n\n"
        f"👤 Cliente: {numero_cliente}\n"
        f"💬 Mensaje: {mensaje}\n\n"
        f"Por favor, contacta al cliente para asistirlo."
    )
    
    # Mensaje para desarrollador (información completa con traceback)
    mensaje_desarrollador = (
        f"🔴 *Error técnico en bot*\n\n"
        f"👤 Cliente: {numero_cliente}\n"
        f"💬 Mensaje original: {mensaje}\n"
        f"❌ Error: {error_type}\n"
        f"📝 Detalle: {error_msg}\n\n"
        f"📋 *Traceback completo:*\n"
        f"```\n{traceback_completo}\n```"
    )
    
    # Mensaje para número de notificación (59891453663)
    mensaje_notificacion = (
        f"⚠️ *Error en el bot de barbería*\n\n"
        f"👤 *Cliente:* {numero_cliente}\n"
        f"💬 *Último mensaje del cliente:*\n{mensaje}\n\n"
        f"📋 *Contexto general:*\n"
        f"Tipo de error: {error_type}\n"
        f"Detalle: {error_msg}\n"
    )
    if contexto_general:
        mensaje_notificacion += f"Ubicación: {contexto_general}\n"
    
    # Enviar mensajes
    if num_empleado and num_empleado != "<NUMERO>":
        enviar_mensaje_whatsapp(num_empleado, mensaje_empleado)
        print(f"📤 Mensaje de error enviado a empleado ({num_empleado})")
    else:
        print("⚠️ num_empleado no está configurado")
    
    if num_desarrollador and num_desarrollador != "<NUMERO>":
        enviar_mensaje_whatsapp(num_desarrollador, mensaje_desarrollador)
        print(f"📤 Mensaje de error enviado a desarrollador ({num_desarrollador})")
    else:
        print("⚠️ num_desarrollador no está configurado")
    
    # Enviar mensaje a número de notificación (59891453663)
    numero_notificacion = "+59891453663"
    enviar_mensaje_whatsapp(numero_notificacion, mensaje_notificacion)
    print(f"📤 Mensaje de error enviado a número de notificación ({numero_notificacion})")
    
    # También imprimir en consola para debugging
    print(f"⚠️ Error capturado: {error_type} - {error_msg}")
    print(f"📋 Traceback:\n{traceback_completo}")


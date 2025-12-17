"""
Handlers específicos para cada tipo de mensaje.
Cada handler maneja la lógica específica de su tipo de mensaje.
"""

from typing import Optional, Dict, Any
from Util.policy_engine import aplicar_politica, obtener_mensaje_segun_estado
from Util.politicas_respuestas import detectar_aviso_demora, normalizar_datos_demora
from Util.precios_barberia import obtener_info_precios_para_prompt
from Util.informacion_barberia import get_info_por_intencion
from Util.procesar_texto_gemini import generar_respuesta_barberia


def handle_demora(texto: str, link_agenda: str = "", chat_instance: Any = None) -> Optional[str]:
    """
    Handler específico para avisos de demora.
    Flujo: Detectar → Extraer datos → Aplicar política → Obtener mensaje
    
    Args:
        texto: Mensaje del usuario
        link_agenda: Link de agenda para incluir en mensajes de cancelación
        chat_instance: Instancia de Chat para acceso a servicios (opcional)
        
    Returns:
        Mensaje de respuesta o None si no es un aviso de demora
    """
    # 1. Detectar (regex/keywords) → código
    if not detectar_aviso_demora(texto):
        return None
    
    # 2. Extraer datos (Gemini mini prompt) → solo extracción
    datos = normalizar_datos_demora(texto)
    
    if not datos:
        # Si no se pueden extraer datos, respuesta genérica
        return "Bro, no pasa nada. Ya le avisamos al barbero con el cual agendaste tu turno."
    
    # CASO ESPECIAL: Si solo hay hora_llegada pero no hora_turno, preguntar primero
    if datos.get("hora_llegada") and not datos.get("hora_turno") and not datos.get("minutos_demora"):
        # Guardar hora_llegada en estado y preguntar por hora_turno
        if chat_instance:
            numero = chat_instance.id_chat.replace("chat_", "") if chat_instance.id_chat else ""
            from Util.estado import set_waiting_for
            set_waiting_for(numero, "demora_hora_turno", {
                "hora_llegada": datos.get("hora_llegada"),
                "texto_original": texto
            })
            return "Bro, ¿a qué hora tenías reservado el turno? Así calculo la demora y te digo qué hacer."
    
    # CASO: Si estamos esperando hora_turno y el usuario responde
    if chat_instance:
        numero = chat_instance.id_chat.replace("chat_", "") if chat_instance.id_chat else ""
        from Util.estado import get_waiting_for, get_estado, clear_waiting_for
        waiting = get_waiting_for(numero)
        
        if waiting == "demora_hora_turno":
            # El usuario está respondiendo con la hora del turno
            estado = get_estado(numero)
            context_data = estado.get("context_data", {})
            hora_llegada = context_data.get("hora_llegada")
            
            # Intentar extraer hora del turno del mensaje actual
            import re
            patron_hora = r'\b(\d{1,2}):?(\d{2})?\b'
            horas_encontradas = re.findall(patron_hora, texto)
            
            if horas_encontradas:
                # Tomar la primera hora encontrada como hora_turno
                hora_parts = horas_encontradas[0]
                if len(hora_parts[1]) == 2:  # Tiene minutos
                    hora_turno = f"{int(hora_parts[0]):02d}:{hora_parts[1]}"
                else:  # Solo hora, asumir :00
                    hora_turno = f"{int(hora_parts[0]):02d}:00"
                
                # Reconstruir datos completos
                datos["hora_turno"] = hora_turno
                datos["hora_llegada"] = hora_llegada
                
                # Calcular minutos de demora
                try:
                    turno_parts = hora_turno.split(":")
                    llegada_parts = hora_llegada.split(":")
                    turno_minutos = int(turno_parts[0]) * 60 + int(turno_parts[1])
                    llegada_minutos = int(llegada_parts[0]) * 60 + int(llegada_parts[1])
                    minutos_demora = llegada_minutos - turno_minutos
                    if minutos_demora > 0:
                        datos["minutos_demora"] = minutos_demora
                except:
                    pass
                
                # Limpiar estado de espera
                clear_waiting_for(numero)
    
    # 3. Decidir política (código) → policy_engine
    resultado_politica = aplicar_politica("aviso_demora", datos)
    estado = resultado_politica["estado"]
    
    # 4. Redactar (texto fijo según estado) → policy_engine
    contexto = {"link_agenda": link_agenda}
    mensaje = obtener_mensaje_segun_estado(estado, contexto)
    
    return mensaje


def handle_derivacion(numero_derivacion: str) -> str:
    """
    Handler para derivación a humano.
    
    Args:
        numero_derivacion: Número de contacto para derivación
        
    Returns:
        Mensaje de derivación
    """
    return (
        f"Te voy a derivar con un asistente humano que te va a poder ayudar mejor. "
        f"En breve te contactará alguien de nuestro equipo.\n\n"
        f"Contacto: {numero_derivacion}"
    )


def handle_link_agenda(
    texto: str,
    link_agenda: str,
    chat_service: Any = None,
    id_chat: str = None,
    ya_hay_contexto: bool = True
) -> Optional[str]:
    """
    Handler para envío de link de agenda.
    Usa Gemini para redactar pero SIEMPRE incluye el link.
    
    Args:
        texto: Mensaje del usuario
        link_agenda: Link de agenda
        chat_service: Servicio de chat (opcional)
        id_chat: ID del chat (opcional)
        ya_hay_contexto: Si ya hay contexto de conversación
        
    Returns:
        Mensaje con link de agenda
    """
    respuesta = generar_respuesta_barberia(
        intencion="link_agenda",
        texto_usuario=texto,
        info_relevante="",
        link_agenda=link_agenda,
        link_maps="",
        ya_hay_contexto=ya_hay_contexto,
        chat_service=chat_service,
        id_chat=id_chat,
        respuesta_predefinida=None
    )
    
    if not respuesta:
        return None
    
    # FORZAR link SIEMPRE al final si no está presente
    if link_agenda and link_agenda not in respuesta:
        respuesta = f"{respuesta}\n\n{link_agenda}"
    
    return respuesta


def handle_precios(
    texto: str,
    chat_service: Any = None,
    id_chat: str = None,
    ya_hay_contexto: bool = True
) -> Optional[str]:
    """
    Handler para consultas de precios.
    Usa el util de precios para obtener información específica.
    
    Args:
        texto: Mensaje del usuario
        chat_service: Servicio de chat (opcional)
        id_chat: ID del chat (opcional)
        ya_hay_contexto: Si ya hay contexto de conversación
        
    Returns:
        Mensaje con información de precios
    """
    # Obtener info de precios usando el util
    info_precios = obtener_info_precios_para_prompt(texto)
    
    # Generar respuesta con Gemini usando la info de precios
    respuesta = generar_respuesta_barberia(
        intencion="precios",
        texto_usuario=texto,
        info_relevante=info_precios,
        link_agenda="",
        link_maps="",
        ya_hay_contexto=ya_hay_contexto,
        chat_service=chat_service,
        id_chat=id_chat,
        respuesta_predefinida=None
    )
    
    return respuesta


def handle_gemini_response(
    intencion: str,
    texto: str,
    info_relevante: str,
    link_agenda: str,
    link_maps: str,
    ya_hay_contexto: bool,
    chat_service: Any = None,
    id_chat: str = None,
    respuesta_predefinida: Optional[str] = None
) -> Optional[str]:
    """
    Handler genérico para respuestas con Gemini.
    
    Args:
        intencion: Intención detectada
        texto: Mensaje del usuario
        info_relevante: Información relevante para el prompt
        link_agenda: Link de agenda
        link_maps: Link de maps
        ya_hay_contexto: Si ya hay contexto de conversación
        chat_service: Servicio de chat (opcional)
        id_chat: ID del chat (opcional)
        respuesta_predefinida: Respuesta predefinida (opcional)
        
    Returns:
        Mensaje generado por Gemini o None si hay error
    """
    return generar_respuesta_barberia(
        intencion=intencion,
        texto_usuario=texto,
        info_relevante=info_relevante,
        link_agenda=link_agenda,
        link_maps=link_maps,
        ya_hay_contexto=ya_hay_contexto,
        chat_service=chat_service,
        id_chat=id_chat,
        respuesta_predefinida=respuesta_predefinida
    )


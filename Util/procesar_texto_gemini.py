import os
import json
import re
from typing import Optional
from google import genai
from google.genai import types
from Util.respuestas_barberia import get_respuesta_predefinida, reemplazar_links
from Util.intents import detectar_intencion
from Util.informacion_barberia import get_info_por_intencion
from Util.error_handler import manejar_error
from Util.token_optimizer import (
    count_tokens, extract_relevant, compress_history, build_modular_prompt,
    validate_and_compress, log_token_usage, get_optimized_config, is_trivial_message
)
from Util.flujo_automatico import procesar_flujo_automatico

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def _extraer_json_robusto(texto: str) -> Optional[dict]:
    """
    Extrae JSON de manera robusta, buscando directamente las llaves { y }.
    
    Args:
        texto: Texto que puede contener JSON
        
    Returns:
        Diccionario parseado o None si no se encuentra JSON válido
    """
    if not texto:
        return None
    
    # Buscar primera llave de apertura
    first_brace = texto.find("{")
    if first_brace == -1:
        return None
    
    # Buscar última llave de cierre desde el final
    last_brace = texto.rfind("}")
    if last_brace == -1 or last_brace <= first_brace:
        return None
    
    # Extraer solo la parte JSON
    json_text = texto[first_brace:last_brace + 1]
    
    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        return None


def detectar_consulta_reserva(texto: str, numero_cliente: str = None) -> dict:
    """
    Detecta si el mensaje es una consulta sobre reservas, citas o turnos.
    PRIMERO intenta con keywords (detectar_intencion), solo usa Gemini si es ambiguo.
    
    Args:
        texto: Mensaje del usuario
        numero_cliente: Número del cliente (opcional, para manejo de errores)
    
    Returns:
        dict con:
            - es_consulta_reserva: bool - Si el mensaje es sobre reservas/citas
            - respuesta_acorde: str - Respuesta generada por Gemini (solo si es consulta)
            - error: bool - Si hubo un error al procesar con Gemini
    """
    # OPTIMIZACIÓN: Primero intentar con keywords (sin gastar tokens)
    intencion_detectada = detectar_intencion(texto)
    
    # Si detecta "turnos" con keywords, es claramente una consulta de reserva
    if intencion_detectada == "turnos":
        return {
            "es_consulta_reserva": True,
            "respuesta_acorde": "",  # Se generará en otro lugar o se usará respuesta predefinida
            "error": False
        }
    
    # Si detecta otra intención clara (no turnos), no es consulta de reserva
    if intencion_detectada and intencion_detectada != "turnos":
        return {
            "es_consulta_reserva": False,
            "respuesta_acorde": "",
            "error": False
        }
    
    # Solo usar Gemini si es ambiguo (no se detectó intención clara)
    try:
        # Extraer información relevante del texto
        texto_relevante = extract_relevant(texto)
        
        # Construir prompt directo (más eficiente que estructura rígida)
        prompt = f"""Determiná si este mensaje es sobre reservas/turnos/citas.

Mensaje: {texto_relevante}

Si es sobre reservas/turnos/citas, respondé con JSON:
{{"es_consulta_reserva": true, "respuesta_acorde": "tu respuesta breve y natural aquí"}}

Si NO es sobre reservas/turnos/citas, respondé con JSON:
{{"es_consulta_reserva": false, "respuesta_acorde": ""}}

IMPORTANTE: Si generas una respuesta, evita signos de exclamación (¡!), puntos excesivos y tildes poco comunes. Escribe natural, como hablarías en persona.

Solo JSON, sin explicaciones."""
        
        # Validar y comprimir si es necesario
        prompt, input_tokens = validate_and_compress(prompt)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=get_optimized_config(),
        )
        
        response_text = response.text if hasattr(response, 'text') and response.text else ""
        output_tokens = count_tokens(response_text) if response_text else 0
        
        # Log tokens una sola vez después de obtener la respuesta
        log_token_usage("detectar_consulta_reserva", input_tokens, output_tokens)
        
        if not response_text:
            print("⚠️ Respuesta vacía de Gemini en detectar_consulta_reserva")
            return {"es_consulta_reserva": False, "respuesta_acorde": "", "error": True}
        
        # Limpieza robusta: extraer JSON directamente
        resultado = _extraer_json_robusto(response_text)
        
        if resultado:
            resultado.setdefault("es_consulta_reserva", False)
            resultado.setdefault("respuesta_acorde", "")
            resultado.setdefault("error", False)
            return resultado
        
        # Si no se pudo extraer JSON, retornar por defecto
        return {"es_consulta_reserva": False, "respuesta_acorde": "", "error": True}
        
    except Exception as e:
        print(f"⚠️ Error en detectar_consulta_reserva: {e}")
        if numero_cliente:
            manejar_error(e, texto, numero_cliente)
        return {"es_consulta_reserva": False, "respuesta_acorde": "", "error": True}


def generar_respuesta_barberia(intencion: str = "", texto_usuario: str = "", info_relevante: str = "", link_agenda: str = "", link_maps: str = "", ya_hay_contexto: bool = False, chat_service=None, id_chat: str = None, respuesta_predefinida: str = None) -> str:
    """
    Genera una respuesta conversacional. Usa información de informacion_barberia.py si está disponible,
    y solo usa Gemini como último fallback.
    
    Args:
        intencion: Intención detectada (ej: "turnos", "visagismo_redondo", "productos_lc")
        texto_usuario: Mensaje original del usuario
        info_relevante: Bloque de información relevante según la intención (opcional)
        link_agenda: Link de la agenda para reemplazar en respuestas (opcional)
        link_maps: Link de Google Maps para reemplazar en respuestas (opcional)
        ya_hay_contexto: Si ya hay contexto de conversación
        chat_service: Servicio de chat para obtener historial
        id_chat: ID del chat para obtener historial
        respuesta_predefinida: Respuesta predefinida ya obtenida (para evitar doble llamada)
        
    Returns:
        String con la respuesta (predefinida o generada por Gemini)
    """
    # EARLY EXIT: Mensajes triviales que no requieren procesamiento
    if texto_usuario and is_trivial_message(texto_usuario):
        # Respuesta simple y directa para mensajes triviales
        return "¡Dale! Cualquier cosa que necesites, avisame."
    
    # Si ya se pasó una respuesta predefinida, usarla directamente
    if respuesta_predefinida:
        # Reemplazar links si se proporcionaron
        if link_agenda or link_maps:
            respuesta_predefinida = reemplazar_links(respuesta_predefinida, link_agenda, link_maps)
        return respuesta_predefinida
    
    # Si no se pasó intención, intentar detectarla
    if not intencion and texto_usuario:
        intencion = detectar_intencion(texto_usuario)
    
    # Si hay intención pero no info_relevante, obtenerla
    if intencion and not info_relevante:
        info_relevante = get_info_por_intencion(intencion)
    
    # Usar Gemini directamente (la decisión de tokens ya se hizo en chat.py)
    try:
        texto_strip = texto_usuario.strip()
        
        # Obtener historial cuando hay contexto de conversación
        historial_comprimido = ""
        ultimos_mensajes = None
        
        if ya_hay_contexto and chat_service and id_chat:
            try:
                # Siempre obtener últimos mensajes para contextualización (al menos los últimos 3-4)
                ultimos_mensajes = chat_service.obtener_ultimos_mensajes(id_chat, limite=4)
                
                # Si hay muchos mensajes, también obtener historial comprimido como contexto adicional
                todos_mensajes = chat_service.obtener_todos_mensajes(id_chat)
                if todos_mensajes and len(todos_mensajes) > 10:
                    historial_comprimido = compress_history(todos_mensajes)
                    print(f"📚 Usando historial comprimido + últimos mensajes ({len(todos_mensajes)} mensajes totales)")
                else:
                    print(f"📝 Usando últimos mensajes ({len(ultimos_mensajes) if ultimos_mensajes else 0} mensajes)")
            except Exception as e:
                print(f"⚠️ Error obteniendo historial: {e}")
        
        # Construir prompt modular optimizado
        prompt = build_modular_prompt(
            intencion=intencion,
            texto_usuario=texto_usuario,
            info_relevante=info_relevante,
            historial_comprimido=historial_comprimido,
            ultimos_mensajes=ultimos_mensajes,
            ya_hay_contexto=ya_hay_contexto,
            link_agenda=link_agenda
        )
        
        # Validar y comprimir si es necesario
        prompt, input_tokens = validate_and_compress(prompt)

        print(f"🤖 LLAMANDO A GEMINI para generar respuesta (input_tokens: {input_tokens})...")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=get_optimized_config(),
        )
        print(f"✅ Respuesta recibida de Gemini")
        
        response_text = response.text if hasattr(response, 'text') and response.text else ""
        output_tokens = count_tokens(response_text) if response_text else 0
        
        # Log tokens una sola vez después de obtener la respuesta
        log_token_usage("generar_respuesta_barberia", input_tokens, output_tokens)
        
        if not response_text:
            print("⚠️ Respuesta vacía de Gemini en generar_respuesta_barberia")
            # No enviar mensaje al cliente, solo notificar al equipo
            manejar_error(Exception("Respuesta vacía de Gemini"), texto_usuario, None, "Respuesta vacía de Gemini")
            return None  # Retornar None para que no se envíe nada
        
        # Limpiar respuesta: remover markdown y espacios extra
        response_text = response_text.strip()
        
        # Remover markdown si existe (más robusto)
        if "```" in response_text:
            # Buscar bloques de código y removerlos
            response_text = re.sub(r'```[a-z]*\n?', '', response_text)
            response_text = re.sub(r'```', '', response_text)
        
        response_text = response_text.strip()
        
        # Aplicar reemplazo de links si se proporcionaron
        if link_agenda or link_maps:
            response_text = reemplazar_links(response_text, link_agenda, link_maps)
        
        return response_text
        
    except Exception as e:
        print(f"⚠️ Error en generar_respuesta_barberia: {e}")
        # Notificar al equipo pero no enviar mensaje técnico al cliente
        manejar_error(e, texto_usuario, None, "Error en generar_respuesta_barberia")
        # Retornar None para que no se envíe nada al cliente
        return None
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
    count_tokens, extract_relevant, compress_history, build_optimized_message,
    validate_and_compress, log_token_usage, get_optimized_config
)
from Util.flujo_automatico import procesar_flujo_automatico

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def _get_prompt_base() -> str:
    """
    Retorna el prompt base con tono unificado para todas las llamadas a Gemini.
    """
    return """Sos un asistente de barbería. Tono cercano: "bro", "hermano", "amigo".
Respondé según la información que recibís. Sé breve y natural.
Idioma: español. No uses formato Markdown.
IMPORTANTE: No uses saludos genéricos como "que onda?" o "hola" a menos que sea el primer mensaje de la conversación. Si ya hay contexto, ve directo al grano."""


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
        
        # Construir mensaje optimizado
        tarea = "Determiná si este mensaje es sobre reservas/turnos/citas."
        datos_utiles = f"Mensaje: {texto_relevante}"
        formato_respuesta = """Si es sobre reservas/turnos/citas, respondé con JSON:
{"es_consulta_reserva": true, "respuesta_acorde": "tu respuesta breve y natural aquí"}

Si NO es sobre reservas/turnos/citas, respondé con JSON:
{"es_consulta_reserva": false, "respuesta_acorde": ""}

Solo JSON, sin explicaciones."""
        
        prompt = build_optimized_message(
            tarea=tarea,
            datos_utiles=datos_utiles,
            formato_respuesta=formato_respuesta
        )
        
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
    # Si ya se pasó una respuesta predefinida, usarla directamente
    if respuesta_predefinida:
        # Reemplazar links si se proporcionaron
        if link_agenda or link_maps:
            respuesta_predefinida = reemplazar_links(respuesta_predefinida, link_agenda, link_maps)
        return respuesta_predefinida
    
    # SEGUNDO: Si no hay respuesta predefinida, intentar obtener info de informacion_barberia.py
    # Si no se pasó intención, intentar detectarla
    if not intencion and texto_usuario:
        intencion = detectar_intencion(texto_usuario)
    
    # Si hay intención pero no info_relevante, obtenerla
    if intencion and not info_relevante:
        info_relevante = get_info_por_intencion(intencion)
    
    # Detectar si es una intención de visagismo
    es_visagismo = intencion and intencion.startswith("visagismo_")
    
    # FALLBACK: Si no hay respuesta predefinida, usar Gemini
    # Si hay info_relevante, incluirla; si no, usar prompt corto (solo tono)
    try:
        # Obtener historial si está disponible
        historial_comprimido = ""
        ultimos_mensajes = []
        
        if chat_service and id_chat:
            try:
                # Obtener todos los mensajes para comprimir
                todos_mensajes = chat_service.obtener_todos_mensajes(id_chat)
                if todos_mensajes:
                    # Comprimir historial si hay muchos mensajes
                    if len(todos_mensajes) > 3:
                        historial_comprimido = compress_history(todos_mensajes)
                    
                    # Obtener últimos mensajes (máx 3 user + 3 bot)
                    ultimos_mensajes = chat_service.obtener_ultimos_mensajes(id_chat, limite=6)
            except Exception as e:
                print(f"⚠️ Error obteniendo historial: {e}")
        
        # Extraer información relevante
        texto_relevante = extract_relevant(texto_usuario)
        info_relevante_limpia = extract_relevant(info_relevante) if info_relevante else ""
        
        # ESTIMAR TOKENS antes de construir el prompt completo
        # Estimar basándose en los componentes que se usarán
        texto_estimado = texto_relevante
        info_estimada = info_relevante_limpia if info_relevante_limpia else ""
        historial_estimado = historial_comprimido
        mensajes_estimados = ""
        if ultimos_mensajes:
            for msg in ultimos_mensajes:
                mensajes_estimados += f"{msg.get('role', '')}: {msg.get('content', '')}\n"
        
        # Estimar tokens del prompt completo
        prompt_estimado = f"{texto_estimado}\n{info_estimada}\n{historial_estimado}\n{mensajes_estimados}"
        tokens_estimados = count_tokens(prompt_estimado)
        
        # Si los tokens estimados > 500, intentar flujo automático primero
        if tokens_estimados > 500:
            print(f"⚠️ Tokens estimados ({tokens_estimados}) > 500, intentando flujo automático primero...")
            respuesta_automatica = procesar_flujo_automatico(
                texto_usuario=texto_usuario,
                intencion=intencion,
                info_relevante=info_relevante
            )
            
            if respuesta_automatica:
                # Si el flujo automático encontró respuesta, usarla
                print(f"✅ Flujo automático exitoso, evitando llamada a Gemini ({tokens_estimados} tokens ahorrados)")
                return respuesta_automatica
            else:
                print(f"⚠️ Flujo automático no encontró coincidencia, usando Gemini de todas formas")
        
        # Construir tarea según el caso
        if es_visagismo:
            tarea = "El cliente ya mencionó su tipo de estructura facial. DALE LA INFORMACIÓN DIRECTAMENTE. No preguntes otra vez sobre su tipo de rostro. Da la información directamente. Al final, di algo como 'te puedo hacer esto o contame si tenes una idea ya'. Sé directo y natural, sin saludos genéricos."
        else:
            tarea = "Respondé al mensaje del cliente de forma natural y breve."
            if ya_hay_contexto:
                tarea += " Ya hay una conversación en curso, NO uses saludos genéricos como 'que onda?' o 'hola'. Ve directo a responder."
        
        # Construir mensaje optimizado
        prompt = build_optimized_message(
            tarea=tarea,
            datos_utiles=info_relevante_limpia if info_relevante_limpia else f"Mensaje: {texto_relevante}",
            historial_comprimido=historial_comprimido,
            ultimos_mensajes=ultimos_mensajes if ultimos_mensajes else None
        )
        
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
        log_token_usage("generar_respuesta_barberia", input_tokens, output_tokens)
        
        if not response_text:
            print("⚠️ Respuesta vacía de Gemini en generar_respuesta_barberia")
            return "Disculpá, no pude generar una respuesta en este momento. ¿Querés que te derive con alguien del equipo?"
        
        # Limpiar respuesta: remover markdown y espacios extra
        response_text = response_text.strip()
        
        # Remover markdown si existe (más robusto)
        if "```" in response_text:
            # Buscar bloques de código y removerlos
            response_text = re.sub(r'```[a-z]*\n?', '', response_text)
            response_text = re.sub(r'```', '', response_text)
        
        return response_text.strip()
        
    except Exception as e:
        print(f"⚠️ Error en generar_respuesta_barberia: {e}")
        manejar_error(e, texto_usuario, None)
        return "Disculpá, estoy teniendo problemas técnicos. ¿Querés que te derive con alguien del equipo?"
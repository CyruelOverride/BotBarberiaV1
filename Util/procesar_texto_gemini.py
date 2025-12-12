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

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def _get_prompt_base() -> str:
    """
    Retorna el prompt base con tono unificado para todas las llamadas a Gemini.
    """
    return """Sos un asistente de barbería. Tono cercano: "bro", "hermano", "amigo".
Respondé según la información que recibís. Sé breve y natural.
Idioma: español. No uses formato Markdown."""


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
        prompt_base = _get_prompt_base()
        prompt = f"""{prompt_base}

Determiná si este mensaje es sobre reservas/turnos/citas: "{texto}"

Si es sobre reservas/turnos/citas, respondé con JSON:
{{"es_consulta_reserva": true, "respuesta_acorde": "tu respuesta breve y natural aquí"}}

Si NO es sobre reservas/turnos/citas, respondé con JSON:
{{"es_consulta_reserva": false, "respuesta_acorde": ""}}

Solo JSON, sin explicaciones."""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0)
            ),
        )
        
        response_text = response.text if hasattr(response, 'text') and response.text else ""
        
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


def generar_respuesta_barberia(intencion: str = "", texto_usuario: str = "", info_relevante: str = "", link_agenda: str = "", link_maps: str = "") -> str:
    """
    Genera una respuesta conversacional. Primero intenta usar respuestas predefinidas,
    luego usa información de informacion_barberia.py si está disponible,
    y solo usa Gemini como último fallback.
    
    Args:
        intencion: Intención detectada (ej: "turnos", "visagismo_redondo", "productos_lc")
        texto_usuario: Mensaje original del usuario
        info_relevante: Bloque de información relevante según la intención (opcional)
        link_agenda: Link de la agenda para reemplazar en respuestas (opcional)
        link_maps: Link de Google Maps para reemplazar en respuestas (opcional)
        
    Returns:
        String con la respuesta (predefinida o generada por Gemini)
    """
    # PRIMERO: Intentar obtener respuesta predefinida
    respuesta_predefinida = get_respuesta_predefinida(texto_usuario)
    
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
    
    # FALLBACK: Si no hay respuesta predefinida, usar Gemini
    # Si hay info_relevante, incluirla; si no, usar prompt corto (solo tono)
    try:
        prompt_base = _get_prompt_base()
        
        if info_relevante:
            # Prompt corto + información relevante como contenido separado
            prompt = f"""{prompt_base}

Mensaje del cliente: "{texto_usuario}"

Respondé basándote en esta información:"""
            
            # Construir contents con prompt e info separados
            contents = [
                prompt,
                f"\n{info_relevante}\n\nResponde ahora:"
            ]
        else:
            # Prompt corto solo con tono (sin información)
            prompt = f"""{prompt_base}

Mensaje del cliente: "{texto_usuario}"

Responde ahora:"""
            contents = [prompt]

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0)
            ),
        )
        
        response_text = response.text if hasattr(response, 'text') and response.text else ""
        
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
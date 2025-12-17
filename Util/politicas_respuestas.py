"""
Util para manejar políticas de respuestas sobre demoras en turnos.
Flujo: Detectar intención → Normalizar datos → Aplicar política → Elegir mensaje
"""

import re
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
from google import genai
from google.genai.errors import ClientError, APIError
import os
from Util.token_optimizer import count_tokens, get_optimized_config

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


# Keywords para detectar aviso de demora
KEYWORDS_DEMORA = [
    "llego", "llegando", "llegaré", "llegare", "llegó", "llegue",
    "voy a demorar", "demoro", "demorar", "demorando",
    "estoy yendo", "yendo", "viniendo", "estoy viniendo",
    "tengo turno", "mi turno", "turno a las", "turno es",
    "atrasado", "atrasé", "atrase", "me atrasé", "me atrase",
    "llegando tarde", "llegando unos minutos", "llegando 10", "llegando 15",
    "llegando 20", "llegando 30", "llegando 40",
    "retraso", "con retraso", "media hora de retraso", "media hora retraso",
    "con demora", "tengo demora", "voy con demora", "llegando con demora"
]


def detectar_aviso_demora(texto: str) -> bool:
    """
    Detecta si el mensaje es un aviso de demora usando keywords.
    
    Args:
        texto: Mensaje del usuario
        
    Returns:
        True si es un aviso de demora, False en caso contrario
    """
    if not texto:
        return False
    
    texto_lower = texto.lower().strip()
    
    # Buscar keywords de demora
    for keyword in KEYWORDS_DEMORA:
        if keyword in texto_lower:
            return True
    
    return False


def normalizar_datos_demora(texto: str) -> Optional[Dict[str, any]]:
    """
    Extrae y normaliza datos de demora del mensaje usando IA.
    Extrae: hora_turno, hora_llegada, minutos_demora
    
    Args:
        texto: Mensaje del usuario
        
    Returns:
        Diccionario con datos normalizados o None si no se puede extraer
    """
    if not texto:
        return None
    
    # Prompt para extracción de datos
    prompt_extraccion = f"""Extrae información sobre demora en turno del siguiente mensaje. 
Responde SOLO con un JSON válido con estas claves:
- "hora_turno": hora del turno en formato HH:MM (ej: "13:00") o null si no se menciona
- "hora_llegada": hora de llegada en formato HH:MM (ej: "13:15") o null si no se menciona
- "minutos_demora": número de minutos de demora (ej: 15) o null si no se menciona

Mensaje: "{texto}"

Responde SOLO con el JSON, sin explicaciones adicionales."""

    try:
        # Usar Gemini para extracción
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[prompt_extraccion],
                config=get_optimized_config()
            )
        except (ClientError, APIError) as api_error:
            print(f"❌ Error de API de Gemini en normalizar_datos_demora: {api_error}")
            # Retornar None para usar fallback
            return _extraer_datos_fallback(texto)
        
        respuesta_texto = response.text.strip()
        
        # Limpiar respuesta (puede venir con markdown)
        if "```json" in respuesta_texto:
            respuesta_texto = respuesta_texto.split("```json")[1].split("```")[0].strip()
        elif "```" in respuesta_texto:
            respuesta_texto = respuesta_texto.split("```")[1].split("```")[0].strip()
        
        # Parsear JSON
        import json
        datos = json.loads(respuesta_texto)
        
        # Calcular minutos_demora si no está pero hay horas
        if datos.get("minutos_demora") is None:
            hora_turno = datos.get("hora_turno")
            hora_llegada = datos.get("hora_llegada")
            
            if hora_turno and hora_llegada:
                try:
                    # Parsear horas
                    turno_parts = hora_turno.split(":")
                    llegada_parts = hora_llegada.split(":")
                    
                    turno_minutos = int(turno_parts[0]) * 60 + int(turno_parts[1])
                    llegada_minutos = int(llegada_parts[0]) * 60 + int(llegada_parts[1])
                    
                    minutos_demora = llegada_minutos - turno_minutos
                    if minutos_demora > 0:
                        datos["minutos_demora"] = minutos_demora
                except (ValueError, IndexError):
                    pass
        
        # Si hay minutos_demora mencionados directamente, usarlos
        if datos.get("minutos_demora") is None:
            # Buscar patrones como "15 min", "15 minutos", "demoro 15"
            patrones_minutos = [
                r'(\d+)\s*(?:min|minutos|minuto)',
                r'demor(?:o|ar|ando)\s*(\d+)',
                r'llegando\s*(\d+)',
            ]
            
            for patron in patrones_minutos:
                match = re.search(patron, texto.lower())
                if match:
                    datos["minutos_demora"] = int(match.group(1))
                    break
        
        return datos
        
    except Exception as e:
        print(f"⚠️ Error extrayendo datos de demora: {e}")
        # Fallback: intentar extraer con regex simple
        return _extraer_datos_fallback(texto)


def _extraer_datos_fallback(texto: str) -> Optional[Dict[str, any]]:
    """
    Fallback para extraer datos usando regex simple.
    """
    texto_lower = texto.lower()
    datos = {
        "hora_turno": None,
        "hora_llegada": None,
        "minutos_demora": None
    }
    
    # Buscar horas en formato HH:MM
    patron_hora = r'\b(\d{1,2}):(\d{2})\b'
    horas_encontradas = re.findall(patron_hora, texto)
    
    if len(horas_encontradas) >= 2:
        # Primera hora = turno, segunda = llegada
        datos["hora_turno"] = f"{int(horas_encontradas[0][0]):02d}:{horas_encontradas[0][1]}"
        datos["hora_llegada"] = f"{int(horas_encontradas[1][0]):02d}:{horas_encontradas[1][1]}"
    elif len(horas_encontradas) == 1:
        # Solo una hora, podría ser turno o llegada
        hora = f"{int(horas_encontradas[0][0]):02d}:{horas_encontradas[0][1]}"
        if "turno" in texto_lower or "tengo" in texto_lower:
            datos["hora_turno"] = hora
        else:
            datos["hora_llegada"] = hora
    
    # Buscar minutos de demora
    patron_minutos = r'(\d+)\s*(?:min|minutos|minuto)'
    match_minutos = re.search(patron_minutos, texto_lower)
    if match_minutos:
        datos["minutos_demora"] = int(match_minutos.group(1))
    
    # Calcular minutos si hay ambas horas
    if datos["hora_turno"] and datos["hora_llegada"] and not datos["minutos_demora"]:
        try:
            turno_parts = datos["hora_turno"].split(":")
            llegada_parts = datos["hora_llegada"].split(":")
            turno_minutos = int(turno_parts[0]) * 60 + int(turno_parts[1])
            llegada_minutos = int(llegada_parts[0]) * 60 + int(llegada_parts[1])
            minutos = llegada_minutos - turno_minutos
            if minutos > 0:
                datos["minutos_demora"] = minutos
        except (ValueError, IndexError):
            pass
    
    return datos if any(datos.values()) else None


# Evaluar demora ahora se hace en policy_engine.py
# Mantener import para compatibilidad
from Util.policy_engine import evaluar_politica_demora as evaluar_demora


def procesar_aviso_demora(texto: str, link_agenda: str = "") -> Optional[str]:
    """
    Procesa un aviso de demora completo: detecta, normaliza, evalúa y retorna mensaje.
    NOTA: Esta función se mantiene para compatibilidad, pero ahora se usa handle_demora() en message_handlers.py
    
    Args:
        texto: Mensaje del usuario
        link_agenda: Link de agenda para incluir en mensajes de cancelación (opcional)
        
    Returns:
        Mensaje de respuesta o None si no es un aviso de demora
    """
    # 1. Detectar intención
    if not detectar_aviso_demora(texto):
        return None
    
    # 2. Normalizar datos
    datos = normalizar_datos_demora(texto)
    
    if not datos:
        # Si no se pueden extraer datos, respuesta genérica
        return "Bro, no pasa nada. Ya le avisamos al barbero con el cual agendaste tu turno."
    
    # 3. Aplicar política usando policy_engine
    from Util.policy_engine import aplicar_politica, obtener_mensaje_segun_estado
    resultado_politica = aplicar_politica("aviso_demora", datos)
    estado = resultado_politica["estado"]
    
    # 4. Elegir mensaje según estado
    contexto = {"link_agenda": link_agenda}
    mensaje = obtener_mensaje_segun_estado(estado, contexto)
    
    # Agregar link de agenda si es necesario (demora grave o turno perdido)
    if estado in ["demora_grave", "turno_perdido"] and link_agenda:
        mensaje += f"\n\nAcá te dejo el link de la agenda: {link_agenda}"
    
    return mensaje


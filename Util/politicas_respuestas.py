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

# Keywords para detectar consultas de precios
KEYWORDS_PRECIOS = [
    "precio", "precios", "costo", "costos", "valor", "valores",
    "cuanto sale", "cuánto sale", "cuanto cuesta", "cuánto cuesta",
    "cuanto vale", "cuánto vale", "tarifa", "tarifas",
    "precio del", "precio de", "costo del", "costo de",
    "valor del", "valor de", "cuanto sale el", "cuánto sale el",
    "cuanto sale la", "cuánto sale la", "precio tiene", "costo tiene"
]

# Keywords para detectar consultas sobre ir con amigo
KEYWORDS_AMIGO = [
    "con un amigo", "con amigo", "vamos con un amigo", "puedo traer",
    "viene conmigo", "viene con", "dos personas", "vamos dos",
    "puedo venir con", "vamos juntos", "con alguien", "traer a alguien"
]

# Keywords para detectar consultas de más información
KEYWORDS_MAS_INFO = [
    "mas informacion", "más información", "quiero mas info", "quiero más info",
    "info", "informacion", "información", "contame mas", "contame más",
    "quiero saber mas", "quiero saber más", "necesito mas info", "necesito más info",
    "dame mas info", "dame más info", "contame sobre", "cuentame sobre"
]

# Keywords para detectar cancelaciones/no poder ir
KEYWORDS_CANCELACION = [
    "no voy a poder", "no puedo ir", "no voy", "no podre", "no podré",
    "no voy a poder ir", "se me murio", "se me murió", "fallecio", "falleció",
    "emergencia", "imprevisto", "problema familiar", "no puedo asistir",
    "no voy a asistir", "tengo que cancelar", "tengo que faltar",
    "no puedo venir", "no voy a venir", "no podre venir", "no podré venir"
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


def detectar_consulta_precios(texto: str) -> bool:
    """
    Detecta si el mensaje es una consulta de precios usando keywords.
    
    Args:
        texto: Mensaje del usuario
        
    Returns:
        True si es una consulta de precios, False en caso contrario
    """
    if not texto:
        return False
    
    texto_lower = texto.lower().strip()
    
    # Buscar keywords de precios
    for keyword in KEYWORDS_PRECIOS:
        if keyword in texto_lower:
            return True
    
    return False


def obtener_respuesta_precios_directa() -> str:
    """
    Retorna directamente el mensaje predeterminado de precios sin pasar por Gemini.
    
    Returns:
        Mensaje con la lista de precios
    """
    try:
        from Util.respuestas_barberia import get_response
        respuesta = get_response("precios", "cuanto_sale")
        if respuesta:
            return respuesta
    except Exception as e:
        print(f"⚠️ Error obteniendo respuesta de precios: {e}")
    
    # Fallback: retornar mensaje hardcodeado si falla la lectura del JSON
    return "Bro, el valor depende de lo que vos quieras hacerte.\nTe paso la lista:\n• Corte + asesoramiento → $500\n• Corte + asesoramiento + barba → $600\n• Barba perfilada → $250\n• Barba afeitada → $200\n• Cejas en base a visagismo → $50"


def detectar_consulta_amigo(texto: str) -> bool:
    """
    Detecta si el mensaje es una consulta sobre ir con un amigo usando keywords.
    
    Args:
        texto: Mensaje del usuario
        
    Returns:
        True si es una consulta sobre ir con amigo, False en caso contrario
    """
    if not texto:
        return False
    
    texto_lower = texto.lower().strip()
    
    # Buscar keywords de amigo
    for keyword in KEYWORDS_AMIGO:
        if keyword in texto_lower:
            return True
    
    return False


def obtener_respuesta_amigo(link_agenda: str) -> str:
    """
    Retorna la respuesta para consultas sobre ir con amigo.
    
    Args:
        link_agenda: Link de la agenda
        
    Returns:
        Mensaje con la respuesta y el link
    """
    return f"Si bro pero agendense ambos en el link\n\n{link_agenda}"


def detectar_consulta_mas_info(texto: str) -> bool:
    """
    Detecta si el mensaje es una consulta de más información usando keywords.
    
    Args:
        texto: Mensaje del usuario
        
    Returns:
        True si es una consulta de más información, False en caso contrario
    """
    if not texto:
        return False
    
    texto_lower = texto.lower().strip()
    
    # Buscar keywords de más información
    for keyword in KEYWORDS_MAS_INFO:
        if keyword in texto_lower:
            return True
    
    return False


def obtener_respuesta_mas_info() -> str:
    """
    Retorna un mensaje completo con información del visagismo, barbería y precios.
    
    Returns:
        Mensaje completo con toda la información
    """
    try:
        from Util.informacion_barberia import get_info_servicio
        from Util.precios_barberia import obtener_lista_completa_precios
        
        info_servicio = get_info_servicio()
        lista_precios = obtener_lista_completa_precios()
        
        # Construir mensaje formateado
        mensaje = "Bro, acá tenés toda la info:\n\n"
        mensaje += "📋 SOBRE EL SERVICIO:\n"
        mensaje += "El servicio se basa en cortes personalizados según el rostro del cliente (visagismo). "
        mensaje += "No se hacen cortes genéricos, sino que se analiza la estructura craneal, tipo de rostro, "
        mensaje += "tipo de cabello, volumen, densidad y dirección de crecimiento.\n\n"
        mensaje += "A partir de eso se decide qué corte va mejor con tu fisonomía y estilo personal. "
        mensaje += "El objetivo es resaltar tus rasgos.\n\n"
        mensaje += "Trabajamos solo con turnos para que no tengas que esperar: llegás y te atendemos. "
        mensaje += "Mientras esperás o terminás tu corte, podés tomarte un café tranquilo, charlar, "
        mensaje += "estar en un ambiente piola, sin apuros. Queremos que te sientas como en casa.\n\n"
        mensaje += "💰 PRECIOS:\n"
        mensaje += lista_precios
        
        return mensaje
    except Exception as e:
        print(f"⚠️ Error obteniendo respuesta de más información: {e}")
        # Fallback básico
        return "Bro, trabajamos con cortes personalizados según tu rostro (visagismo). Trabajamos solo con turnos. Si querés más info específica, preguntame lo que necesites."


def detectar_cancelacion_empatica(texto: str) -> bool:
    """
    Detecta si el mensaje es una cancelación o aviso de no poder ir usando keywords.
    
    Args:
        texto: Mensaje del usuario
        
    Returns:
        True si es una cancelación/no poder ir, False en caso contrario
    """
    if not texto:
        return False
    
    texto_lower = texto.lower().strip()
    
    # Buscar keywords de cancelación
    for keyword in KEYWORDS_CANCELACION:
        if keyword in texto_lower:
            return True
    
    return False


def generar_respuesta_cancelacion_empatica(texto: str, link_agenda: str) -> str:
    """
    Genera una respuesta empática para cancelaciones usando Gemini.
    Mantiene el tono de "bro", "hermano" pero es empático con la situación.
    
    Args:
        texto: Mensaje del usuario
        link_agenda: Link de la agenda
        
    Returns:
        Mensaje empático generado por Gemini
    """
    try:
        # Construir prompt especial para respuesta empática
        prompt = f"""El cliente escribió: "{texto}"

Analizá el contexto del mensaje. Puede ser:
- Muerte de familiar (abuela, abuelo, etc.)
- Emergencia médica
- Imprevisto personal
- Problema familiar
- Otra situación que le impide asistir

Generá una respuesta empática pero manteniendo el tono casual de la barbería:
- Usá "bro", "hermano" o "amigo" según corresponda
- Mostrá comprensión y empatía por la situación
- NO uses frases muy formales, mantené el tono casual pero respetuoso
- Incluí instrucciones claras: que cancele su turno actual y se agende uno nuevo cuando pueda
- Incluí el link de agenda al final: {link_agenda}
- Si menciona muerte de familiar, sé especialmente empático pero sin exagerar

Responde SOLO con el mensaje para el cliente, sin explicaciones adicionales."""

        # Usar Gemini para generar respuesta
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=get_optimized_config()
        )
        
        respuesta_texto = response.text.strip()
        
        # Asegurar que el link esté incluido
        if link_agenda and link_agenda not in respuesta_texto:
            respuesta_texto += f"\n\nAcá tenés el link de la agenda: {link_agenda}"
        
        return respuesta_texto
        
    except (ClientError, APIError) as api_error:
        print(f"❌ Error de API de Gemini en generar_respuesta_cancelacion_empatica: {api_error}")
        # Fallback: respuesta genérica pero empática
        return f"Bro, no pasa nada, entendemos la situación. Por favor cancelá tu reserva actual y agendate uno nuevo cuando puedas. Acá tenés el link de la agenda: {link_agenda}"
    except Exception as e:
        print(f"⚠️ Error generando respuesta empática: {e}")
        # Fallback: respuesta genérica pero empática
        return f"Bro, no pasa nada, entendemos la situación. Por favor cancelá tu reserva actual y agendate uno nuevo cuando puedas. Acá tenés el link de la agenda: {link_agenda}"


def detectar_intencion_general_con_gemini(texto: str) -> Optional[str]:
    """
    Usa Gemini para detectar la intención general cuando no se detectó por keywords.
    
    Args:
        texto: Mensaje del usuario
        
    Returns:
        Intención detectada (ej: "turnos", "precios", "barba", "cortes", "ubicacion", etc.) o None
    """
    if not texto or len(texto.strip()) <= 10:
        return None
    
    try:
        # Lista de intenciones básicas posibles
        intenciones_posibles = [
            "turnos", "precios", "barba", "cortes", "ubicacion", 
            "productos_lc", "diferencial", "visagismo", "servicios"
        ]
        
        prompt = f"""Analizá el siguiente mensaje del cliente y detectá su intención principal.

Mensaje: "{texto}"

Intenciones posibles:
- "turnos": Si pregunta sobre agendar, reservar, disponibilidad, horarios
- "precios": Si pregunta sobre costos, precios, valores, tarifas
- "barba": Si pregunta específicamente sobre servicios de barba
- "cortes": Si pregunta sobre tipos de corte, estilos, cortes disponibles
- "ubicacion": Si pregunta dónde están, dirección, ubicación, cómo llegar
- "productos_lc": Si pregunta sobre productos, cera, styling
- "diferencial": Si pregunta qué los diferencia, qué tienen de especial
- "visagismo": Si pregunta sobre visagismo, tipos de rostro, qué corte le queda
- "servicios": Si pregunta qué servicios ofrecen, qué hacen

Responde SOLO con el nombre de la intención (ej: "turnos") o "otro" si no coincide con ninguna.
NO incluyas explicaciones, solo el nombre de la intención."""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=get_optimized_config()
        )
        
        respuesta_texto = response.text.strip().lower()
        
        # Limpiar respuesta (puede venir con markdown o explicaciones)
        respuesta_texto = respuesta_texto.replace("```", "").strip()
        
        # Verificar que sea una intención válida
        if respuesta_texto in intenciones_posibles:
            return respuesta_texto
        elif respuesta_texto == "otro":
            return None
        
        # Si la respuesta contiene alguna intención, extraerla
        for intencion in intenciones_posibles:
            if intencion in respuesta_texto:
                return intencion
        
        return None
        
    except (ClientError, APIError) as api_error:
        print(f"❌ Error de API de Gemini en detectar_intencion_general_con_gemini: {api_error}")
        return None
    except Exception as e:
        print(f"⚠️ Error detectando intención con Gemini: {e}")
        return None


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


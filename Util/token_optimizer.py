"""
Módulo de optimización de tokens para reducir consumo en llamadas a Gemini.
Mantiene funcionalidad igual pero optimiza el uso de tokens.
"""

import os
import re
import json
from typing import List, Dict, Optional, Tuple, Any
from google import genai
from google.genai import types

# Constantes de configuración
MAX_TOKENS_INPUT = 4000
MAX_TOKENS_OUTPUT = 300
HISTORY_COMPRESSION_THRESHOLD = 2000
THINKING_ENABLED = False  # Siempre desactivado

# Cliente de Gemini para contar tokens
_client = None

def _get_client():
    """Obtiene el cliente de Gemini para contar tokens."""
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            _client = genai.Client(api_key=api_key)
    return _client


def count_tokens(text: str, use_api: bool = False) -> int:
    """
    Cuenta tokens en un texto. Por defecto usa estimación local (rápida y sin costo).
    Solo usa API cuando estás muy cerca del límite o en modo debug.
    
    Args:
        text: Texto a contar
        use_api: Si True, usa API de Gemini. Si False (default), usa estimación rápida.
        
    Returns:
        Número de tokens estimados
    """
    if not text:
        return 0
    
    # Estimación rápida (español ~ 3.8 chars/token, usamos 4 para ser conservadores)
    estimated = max(1, len(text) // 4)
    
    if not use_api:
        return estimated
    
    # Solo usar API si explícitamente se solicita (modo debug o validación crítica)
    try:
        client = _get_client()
        if not client:
            return estimated
        
        result = client.models.count_tokens(
            model="gemini-2.5-flash",
            contents=[text]
        )
        return getattr(result, "total_tokens", estimated)
    except Exception as e:
        print(f"⚠️ Error contando tokens con API: {e}, usando estimación")
        return estimated


def compact_json_if_present(text: str) -> str:
    """
    Compacta JSON si está presente en el texto.
    Solo procesa si hay exactamente un bloque JSON válido.
    
    Args:
        text: Texto que puede contener JSON
        
    Returns:
        Texto con JSON compactado (si aplica)
    """
    # Solo procesar si hay exactamente un bloque JSON
    if text.count("{") != 1 or text.count("}") != 1:
        return text
    
    try:
        json_text = text[text.find('{'):text.rfind('}')+1]
        parsed = json.loads(json_text)
        compact_json = json.dumps(parsed, ensure_ascii=False, separators=(',', ':'))
        return text[:text.find('{')] + compact_json + text[text.rfind('}')+1:]
    except:
        return text


def extract_relevant(text: str) -> str:
    """
    Extrae solo la información esencial del texto.
    Remueve espacios múltiples y compacta JSON si está presente.
    
    Args:
        text: Texto a procesar
        
    Returns:
        Texto con solo información relevante
    """
    if not text:
        return ""
    
    # Remover espacios múltiples
    text = re.sub(r'\s+', ' ', text)
    
    # Compactar JSON si está presente
    text = compact_json_if_present(text)
    
    # Remover espacios al inicio/final
    return text.strip()


def _get_instrucciones_tono(ya_hay_contexto: bool = False) -> str:
    """
    Retorna las instrucciones de tono para los prompts.
    Centraliza las instrucciones para mantener consistencia.
    
    Args:
        ya_hay_contexto: Si ya hay contexto de conversación (para evitar saludos)
        
    Returns:
        String con instrucciones de tono
    """
    base = "Responde con conversación cálida, como si estuvieses hablando con un amigo. No hables como robot ni como empresa, sé natural y humano. Usa 'Hermano', 'Bro' o 'Amigo' máximo 1 vez por mensaje, solo cuando sea natural. Usa frases claras como 'Te paso info', 'Miro mi agenda y te confirmo', 'Te anoto'. Sé conversacional, directo y amigable. Ir al grano, no dar vueltas. MENSAJES CORTOS (máximo 3-4 líneas). Completo pero conciso."
    if ya_hay_contexto:
        return base + " No uses saludos pero puedes ser calido. Responde en contexto de la conversación anterior. Si no tienes información específica sobre lo que pregunta, invita directamente a la consulta en lugar de dar vueltas explicando sobre visagismo en general."
    return base + " Si no tienes información específica sobre lo que pregunta, invita directamente a la consulta en lugar de dar vueltas."


def compress_history(history: List[Dict[str, str]], max_tokens: int = 300) -> str:
    """
    Comprime el historial de conversación de forma determinista y eficiente.
    Solo mantiene estado conversacional útil: intenciones y último mensaje del usuario.
    
    Args:
        history: Lista de mensajes con formato [{"role": "user/bot", "content": "..."}, ...]
        max_tokens: Máximo de tokens para el resumen (no usado actualmente, se mantiene para compatibilidad)
        
    Returns:
        Resumen comprimido del historial
    """
    if not history:
        return ""
    
    # Obtener último mensaje del usuario
    last_user = next(
        (m.get("content", "") for m in reversed(history) if m.get("role") == "user"),
        ""
    )
    
    # Detectar intenciones de forma simple y determinista
    intents = set()
    for m in history:
        c = m.get("content", "").lower()
        if any(word in c for word in ["turno", "reserva", "agenda", "cita"]):
            intents.add("turnos")
        if any(word in c for word in ["precio", "costo", "cuanto"]):
            intents.add("precios")
        if any(word in c for word in ["visagismo", "rostro", "cara"]):
            intents.add("visagismo")
    
    # Construir resumen mínimo
    parts = []
    if intents:
        parts.append(f"Intenciones previas: {', '.join(sorted(intents))}")
    
    if last_user:
        parts.append(f"Último mensaje usuario: {last_user[:120]}")
    
    return " | ".join(parts)


def _get_prompt_especifico(intencion: str, ya_hay_contexto: bool) -> str:
    """
    Retorna un prompt corto y específico según la intención detectada.
    Solo incluye lo esencial, sin estructura rígida.
    Incluye instrucciones de tono para mantener consistencia.
    
    Args:
        intencion: Intención detectada (ej: "visagismo_redondo", "turnos", "precios")
        ya_hay_contexto: Si ya hay contexto de conversación
        
    Returns:
        Prompt específico y corto con instrucciones de tono
    """
    tono = _get_instrucciones_tono(ya_hay_contexto)
    
    if not intencion:
        return tono
    
    intencion_lower = intencion.lower()
    
    # Saludo inicial
    if intencion_lower == "saludo_inicial":
        return f"""{tono} 
Genera un saludo inicial MUY BREVE (máximo 2-3 líneas) siguiendo este estilo como EJEMPLO (NO lo copies literal):
Ejemplo de estilo: "Buenas hermano, ¿todo bien? ¿Alguna vez te hiciste un corte en base a tu rostro?"
Varía el saludo, usa diferentes palabras pero mantén el tono cálido, personal y la pregunta sobre cortes en base al rostro. Sé directo y natural."""
    
    # Visagismo
    if intencion_lower.startswith("visagismo_"):
        tipo_rostro = intencion.replace("visagismo_", "").replace("_", " ")
        return f"{tono} Cliente mencionó {tipo_rostro}. Si tienes información específica sobre este tipo de rostro, da info directa y concreta. Si NO tienes información específica (ej: menciona 'frentón' o algo no en la base de datos), invita directamente a la consulta diciendo algo como 'vení a la consulta y te asesoramos en persona'. No des vueltas explicando sobre visagismo en general. No repitas frases como 'el visagismo es clave'. Sé directo y conciso."
    
    # Turnos
    if intencion_lower == "turnos":
        return f"{tono} Cliente pregunta por turnos. Responde breve con link de agenda."
    
    # Agendar turno (flujo secuencial)
    if intencion_lower == "agendar_turno":
        return f"""{tono}
El cliente respondió positivamente al saludo inicial. Genera una respuesta breve (máximo 2-3 líneas) siguiendo este estilo como EJEMPLO (NO lo copies literal):
Ejemplo de estilo: "Buenísimo bro. Agendamos un turno para que pruebes por primera vez un corte en base a tu rostro, te parece?"
Varía las palabras pero mantén el tono cálido, la propuesta de agendar turno y la mención al corte en base al rostro."""
    
    # Link agenda (flujo secuencial)
    if intencion_lower == "link_agenda":
        return f"""{tono}
El cliente confirmó que quiere agendar. Genera una respuesta breve (máximo 2-3 líneas) siguiendo este estilo como EJEMPLO (NO lo copies literal):
Ejemplo de estilo: "Perfecto bro, te dejo el link de la agenda así elegís día y hora. Cualquier duda escribime, estamos a las órdenes."
Varía las palabras pero mantén el tono positivo, menciona el link de agenda y ofrece ayuda. El link se agregará automáticamente."""
    
    # Post reserva (flujo secuencial)
    if intencion_lower == "post_reserva":
        return f"""{tono}
El cliente confirmó que agendó. Genera una respuesta breve pero importante (máximo 4-5 líneas) siguiendo este estilo como EJEMPLO (NO lo copies literal):
Ejemplo de estilo: "Bro, una cosa importante: como trabajamos solo por agenda, si por algún motivo no podés venir, avisá o cancelá el turno con tiempo. Así ese horario se lo podemos dar a otro cliente que también necesita ser asesorado y cortarse. Gracias por entender hermano."
Varía las palabras pero mantén el tono amigable, la importancia de avisar/cancelar con tiempo, y el agradecimiento."""
    
    # Precios
    if intencion_lower == "precios":
        return f"{tono} Cliente pregunta precios. Responde con lista breve."
    
    # Ubicación
    if intencion_lower == "ubicacion":
        return f"{tono} Cliente pregunta ubicación. Responde breve con dirección."
    
    # Barba
    if intencion_lower == "barba":
        return f"{tono} Cliente pregunta por barba. Responde breve confirmando que sí se hace."
    
    # Productos
    if intencion_lower == "productos_lc":
        return f"{tono} Cliente pregunta por productos. Responde breve con info y precio."
    
    # Diferencial
    if intencion_lower == "diferencial":
        return f"{tono} Cliente pregunta diferencial. Responde breve destacando visagismo y turnos."
    
    # Cortes
    if intencion_lower == "cortes":
        return f"{tono} Cliente pregunta por cortes. Responde breve sobre visagismo."
    
    # Default: prompt genérico corto
    return f"{tono} Responde sobre {intencion}. Si no tienes información específica, invita directamente a la consulta en lugar de dar vueltas. Sé directo y conciso."


def build_modular_prompt(
    intencion: str = "",
    texto_usuario: str = "",
    info_relevante: str = "",
    historial_comprimido: str = "",
    ultimos_mensajes: List[Dict[str, Any]] = None,
    ya_hay_contexto: bool = False
) -> str:
    """
    Construye un prompt modular y optimizado según la intención.
    Solo agrega las secciones necesarias, evitando estructura rígida.
    
    Args:
        intencion: Intención detectada
        texto_usuario: Mensaje del usuario
        info_relevante: Información relevante extraída
        historial_comprimido: Historial comprimido (opcional)
        ultimos_mensajes: Últimos mensajes (opcional)
        ya_hay_contexto: Si ya hay contexto de conversación
        
    Returns:
        Prompt optimizado y corto
    """
    parts = []
    
    # 1. Prompt específico según intención (más corto que tarea genérica)
    prompt_especifico = _get_prompt_especifico(intencion, ya_hay_contexto)
    parts.append(prompt_especifico)
    
    # 2. Extraer último mensaje del bot si existe (para contextualización)
    ultimo_mensaje_bot = None
    if ultimos_mensajes:
        # Buscar el último mensaje del bot (recorrer desde el final)
        for msg in reversed(ultimos_mensajes):
            if not msg.get("es_cliente", True):  # Es mensaje del bot
                ultimo_mensaje_bot = msg.get("contenido", "")
                break
    
    # 3. Estructurar conversación: último mensaje del bot (si existe) + mensaje del usuario
    if ya_hay_contexto and ultimo_mensaje_bot:
        # Incluir último mensaje del bot completo (no truncar tanto para mantener contexto)
        ultimo_bot_limpio = extract_relevant(ultimo_mensaje_bot)
        if ultimo_bot_limpio:
            # No truncar el último mensaje del bot, o truncar menos (máx 300 chars)
            if len(ultimo_bot_limpio) > 300:
                ultimo_bot_limpio = ultimo_bot_limpio[:300] + "..."
            parts.append(f"Bot: {ultimo_bot_limpio}")
    
    # 4. Mensaje del usuario (siempre presente, pero extraído)
    if texto_usuario:
        texto_limpio = extract_relevant(texto_usuario)
        if texto_limpio:
            parts.append(f"Usuario: {texto_limpio}")
    
    # 5. Instrucción de contexto solo si el bot hizo una pregunta
    if ya_hay_contexto and ultimo_mensaje_bot and ultimo_mensaje_bot.strip().endswith("?"):
        parts.append("Responde a la pregunta anterior.")
    
    # 6. Info relevante (solo si existe y es necesaria)
    if info_relevante:
        info_limpia = extract_relevant(info_relevante)
        if info_limpia and len(info_limpia) > 20:  # Solo si tiene contenido sustancial
            # Truncar info relevante si es muy larga (máx 200 chars)
            if len(info_limpia) > 200:
                info_limpia = info_limpia[:200] + "..."
            parts.append(f"Info: {info_limpia}")
    
    # 7. Historial adicional (solo si no se incluyó el último mensaje del bot explícitamente)
    if historial_comprimido:
        # Truncar historial si es muy largo (máx 150 chars)
        if len(historial_comprimido) > 150:
            historial_comprimido = historial_comprimido[:150] + "..."
        parts.append(f"Contexto adicional: {historial_comprimido}")
    elif ultimos_mensajes and not ultimo_mensaje_bot:
        # Si hay mensajes pero no se encontró mensaje del bot, incluir contexto general
        mensajes_cortos = []
        for msg in ultimos_mensajes[-3:]:  # Máximo 3 mensajes
            role = "U" if msg.get("es_cliente") else "B"
            content = msg.get("contenido", "")[:150]  # Aumentar límite a 150 chars
            mensajes_cortos.append(f"{role}: {content}")
        if mensajes_cortos:
            parts.append("Contexto adicional: " + " | ".join(mensajes_cortos))
    
    # Unir con saltos de línea simples (sin etiquetas rígidas)
    return "\n".join(parts)


def validate_and_compress(
    message: str,
    max_input_tokens: int = MAX_TOKENS_INPUT
) -> Tuple[str, int]:
    """
    Valida que el mensaje no exceda el límite de tokens y comprime si es necesario.
    
    Args:
        message: Mensaje a validar
        max_input_tokens: Límite máximo de tokens
        
    Returns:
        Tupla (mensaje_optimizado, tokens_usados)
    """
    tokens = count_tokens(message)
    
    if tokens <= max_input_tokens:
        return message, tokens
    
    # Si excede, comprimir
    print(f"⚠️ Mensaje excede límite ({tokens} > {max_input_tokens}), comprimiendo...")
    
    # Estrategia de compresión: reducir cada sección proporcionalmente
    lines = message.split('\n')
    target_tokens = max_input_tokens - 100  # Margen de seguridad
    
    # Calcular factor de compresión
    compression_factor = target_tokens / tokens
    
    # Aplicar compresión simple: truncar líneas largas
    compressed_lines = []
    for line in lines:
        # Usar estimación simple en lugar de count_tokens para evitar múltiples llamadas
        if len(line) > 200:  # Si la línea es muy larga (estimación)
            # Truncar a ~70% de su longitud
            new_length = int(len(line) * compression_factor * 0.7)
            compressed_lines.append(line[:new_length] + "...")
        else:
            compressed_lines.append(line)
    
    compressed_message = '\n'.join(compressed_lines)
    compressed_tokens = count_tokens(compressed_message)
    
    return compressed_message, compressed_tokens


def log_token_usage(
    function_name: str,
    input_tokens: int,
    output_tokens: int = 0,
    model: str = "gemini-2.5-flash"
):
    """
    Consolgea el uso de tokens de forma clara.
    
    Args:
        function_name: Nombre de la función que usa tokens
        input_tokens: Tokens de entrada
        output_tokens: Tokens de salida (0 si no se conoce)
        model: Modelo usado
    """
    total = input_tokens + output_tokens
    print(f"📊 Tokens [{function_name}] | Modelo: {model} | Input: {input_tokens} | Output: {output_tokens} | Total: {total}")


def get_optimized_config() -> types.GenerateContentConfig:
    """
    Retorna la configuración optimizada para Gemini.
    Incluye thinking_budget=0, temperature controlada y límite de output tokens.
    
    Returns:
        Configuración de Gemini optimizada
    """
    return types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        temperature=0.4,
        max_output_tokens=MAX_TOKENS_OUTPUT
    )


def log_efficiency(prompt: str, response: str, function_name: str = ""):
    """
    Loguea métrica de eficiencia: ratio utilidad/token.
    Permite detectar prompts inflados y comparar intenciones.
    
    Args:
        prompt: Prompt enviado a Gemini
        response: Respuesta recibida
        function_name: Nombre de la función (opcional, para contexto)
    """
    in_t = count_tokens(prompt)
    out_t = count_tokens(response)
    total_tokens = in_t + out_t
    
    if total_tokens > 0:
        efficiency = len(response) / total_tokens
        print(f"⚡ Eficiencia [{function_name}]: {len(response)} chars / {total_tokens} tokens = {efficiency:.2f} chars/token")
    else:
        print(f"⚡ Eficiencia [{function_name}]: Sin tokens")


# Mensajes triviales que no requieren procesamiento
MENSAJES_TRIVIALES = {
    "ok", "dale", "gracias", "genial", "perfecto",
    "👍", "👌", "ok gracias", "joya", "si", "sí", "no",
    "listo", "bien", "bueno"
}


def is_trivial_message(text: str) -> bool:
    """
    Detecta si un mensaje es trivial y no requiere procesamiento con Gemini.
    
    Args:
        text: Mensaje del usuario
        
    Returns:
        True si el mensaje es trivial, False si requiere procesamiento
    """
    if not text:
        return True
    
    t = text.strip().lower()
    return t in MENSAJES_TRIVIALES or len(t) <= 4


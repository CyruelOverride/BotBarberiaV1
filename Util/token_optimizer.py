"""
Módulo de optimización de tokens para reducir consumo en llamadas a Gemini.
Mantiene funcionalidad igual pero optimiza el uso de tokens.
"""

import os
import re
import json
from typing import List, Dict, Optional, Tuple
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


def count_tokens(text: str, model: str = "gemini-2.5-flash") -> int:
    """
    Cuenta tokens en un texto usando la API de Gemini.
    
    Args:
        text: Texto a contar
        model: Modelo a usar (default: gemini-2.5-flash)
        
    Returns:
        Número de tokens estimados
    """
    if not text:
        return 0
    
    try:
        client = _get_client()
        if not client:
            # Fallback: estimación aproximada (1 token ≈ 4 caracteres en español)
            return len(text) // 4
        
        # Usar count_tokens de Gemini
        result = client.models.count_tokens(model=model, contents=[text])
        if hasattr(result, 'total_tokens'):
            return result.total_tokens
        elif hasattr(result, 'input_tokens'):
            return result.input_tokens
        else:
            # Fallback si no hay atributo esperado
            return len(text) // 4
    except Exception as e:
        print(f"⚠️ Error contando tokens: {e}, usando estimación")
        # Fallback: estimación aproximada
        return len(text) // 4


def extract_relevant(text: str) -> str:
    """
    Extrae solo la información esencial del texto.
    Remueve texto irrelevante, compacta JSON, elimina duplicados.
    
    Args:
        text: Texto a procesar
        
    Returns:
        Texto con solo información relevante
    """
    if not text:
        return ""
    
    # Remover espacios múltiples
    text = re.sub(r'\s+', ' ', text)
    
    # Remover comentarios si hay JSON
    if '{' in text and '}' in text:
        try:
            # Intentar parsear y compactar JSON
            json_text = text[text.find('{'):text.rfind('}')+1]
            parsed = json.loads(json_text)
            compact_json = json.dumps(parsed, ensure_ascii=False, separators=(',', ':'))
            text = text[:text.find('{')] + compact_json + text[text.rfind('}')+1:]
        except:
            pass
    
    # Remover líneas vacías múltiples
    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
    
    # Remover caracteres de control y espacios al inicio/final
    text = text.strip()
    
    return text


def compress_history(history: List[Dict[str, str]], max_tokens: int = 300) -> str:
    """
    Comprime el historial de conversación a un resumen de ~max_tokens.
    Mantiene: datos importantes del usuario, decisiones, intenciones, números relevantes.
    
    Args:
        history: Lista de mensajes con formato [{"role": "user/bot", "content": "..."}, ...]
        max_tokens: Máximo de tokens para el resumen
        
    Returns:
        Resumen comprimido del historial
    """
    if not history:
        return ""
    
    # Extraer información clave
    intenciones = []
    decisiones = []
    numeros = []
    datos_usuario = []
    
    for msg in history:
        content = msg.get("content", "")
        role = msg.get("role", "")
        
        # Extraer números (fechas, precios, IDs, etc.)
        numeros_encontrados = re.findall(r'\b\d+[.,]?\d*\b', content)
        numeros.extend(numeros_encontrados)
        
        # Detectar intenciones clave
        if any(word in content.lower() for word in ["turno", "reserva", "agenda", "cita"]):
            intenciones.append("turnos")
        if any(word in content.lower() for word in ["precio", "costo", "cuanto"]):
            intenciones.append("precios")
        if any(word in content.lower() for word in ["visagismo", "rostro", "cara"]):
            intenciones.append("visagismo")
        
        # Datos del usuario (nombres, preferencias)
        if role == "user":
            # Extraer nombres propios (palabras capitalizadas)
            nombres = re.findall(r'\b[A-Z][a-z]+\b', content)
            datos_usuario.extend(nombres)
    
    # Construir resumen
    resumen_parts = []
    
    if intenciones:
        intenciones_unicas = list(set(intenciones))
        resumen_parts.append(f"Intenciones: {', '.join(intenciones_unicas)}")
    
    if datos_usuario:
        datos_unicos = list(set(datos_usuario))[:5]  # Máximo 5 nombres
        resumen_parts.append(f"Datos usuario: {', '.join(datos_unicos)}")
    
    if numeros:
        numeros_unicos = list(set(numeros))[:10]  # Máximo 10 números
        resumen_parts.append(f"Números relevantes: {', '.join(numeros_unicos[:10])}")
    
    # Agregar último mensaje del usuario si existe
    for msg in reversed(history):
        if msg.get("role") == "user":
            resumen_parts.append(f"Último mensaje usuario: {msg.get('content', '')[:100]}")
            break
    
    resumen = " | ".join(resumen_parts)
    
    # Si el resumen es muy largo, truncar
    tokens_resumen = count_tokens(resumen)
    if tokens_resumen > max_tokens:
        # Truncar manteniendo las partes más importantes
        partes = resumen.split(" | ")
        resumen = " | ".join(partes[:2])  # Solo primeras 2 partes
    
    return resumen


def build_optimized_message(
    tarea: str,
    datos_utiles: str = "",
    historial_comprimido: str = "",
    ultimos_mensajes: List[Dict[str, str]] = None,
    formato_respuesta: str = ""
) -> str:
    """
    Construye un mensaje optimizado con estructura específica para reducir tokens.
    
    Args:
        tarea: Instrucción principal
        datos_utiles: Datos relevantes extraídos
        historial_comprimido: Resumen del historial
        ultimos_mensajes: Lista de últimos mensajes (máx 3 user + 3 bot)
        formato_respuesta: Formato esperado de respuesta (opcional)
        
    Returns:
        Mensaje estructurado optimizado
    """
    parts = []
    
    # TAREA (siempre presente)
    parts.append(f"TAREA:\n{tarea}")
    
    # DATOS_UTILES
    if datos_utiles:
        parts.append(f"DATOS_UTILES:\n{datos_utiles}")
    
    # HISTORIAL_COMPRESO
    if historial_comprimido:
        parts.append(f"HISTORIAL_COMPRESO:\n{historial_comprimido}")
    
    # ULTIMOS_MENSAJES
    if ultimos_mensajes:
        mensajes_str = []
        for msg in ultimos_mensajes[-6:]:  # Máximo 6 mensajes (3 user + 3 bot)
            role = msg.get("role", "user")
            content = msg.get("content", "")
            mensajes_str.append(f"{role.upper()}: {content}")
        if mensajes_str:
            parts.append(f"ULTIMOS_MENSAJES:\n" + "\n".join(mensajes_str))
    
    # FORMATO_RESPUESTA
    if formato_respuesta:
        parts.append(f"FORMATO_RESPUESTA:\n{formato_respuesta}")
    
    return "\n\n".join(parts)


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
        if count_tokens(line) > 50:  # Si la línea es muy larga
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
    Retorna la configuración optimizada para Gemini (sin thinking tokens).
    
    Returns:
        Configuración de Gemini sin thinking tokens
    """
    return types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0)
    )


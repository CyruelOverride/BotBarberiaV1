"""
Módulo unificado para detección de intenciones.
Combina keywords básicas, keywords específicas (predefinidas) y Gemini solo si es ambiguo.
"""

from typing import Optional, Tuple
from Util.intents import detectar_intencion as _detectar_intencion_keywords
from Util.respuestas_barberia import detectar_intencion_respuesta as _detectar_intencion_predefinida


def detectar_intencion_unificada(texto: str) -> Optional[Tuple[str, str, dict]]:
    """
    Detecta intención usando estrategia en capas: keywords → predefinidas → Gemini (solo si ambiguo).
    
    Args:
        texto: Mensaje del usuario
        
    Returns:
        Tupla (intencion, fuente, metadata) o None si no se detecta:
        - intencion: Nombre de la intención detectada
        - fuente: "keywords", "predefinidas", "gemini" o None
        - metadata: Dict con info adicional (ej: {"clave": "cuanto_sale"} para predefinidas)
    """
    if not texto:
        return None
    
    # CAPA 1: Keywords básicas (más rápido, sin costo)
    intencion_keywords = _detectar_intencion_keywords(texto)
    if intencion_keywords:
        return (intencion_keywords, "keywords", {})
    
    # CAPA 2: Keywords específicas de respuestas predefinidas
    resultado_predefinida = _detectar_intencion_predefinida(texto)
    if resultado_predefinida:
        intencion_predef, clave_predef = resultado_predefinida
        return (intencion_predef, "predefinidas", {"clave": clave_predef})
    
    # CAPA 3: Gemini solo si el mensaje es ambiguo (no se detectó nada claro)
    # Solo usar si el mensaje tiene suficiente contenido para ser ambiguo
    texto_limpio = texto.strip()
    if len(texto_limpio) > 10:  # Solo si tiene suficiente contenido
        try:
            from Util.respuestas_barberia import detectar_clave_con_gemini
            resultado_gemini = detectar_clave_con_gemini(texto)
            if resultado_gemini:
                intencion_gemini, clave_gemini = resultado_gemini
                return (intencion_gemini, "gemini", {"clave": clave_gemini})
        except Exception as e:
            print(f"⚠️ Error usando Gemini para detección de intención: {e}")
            # Si falla Gemini, retornar None (no es crítico)
    
    return None


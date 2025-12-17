"""
Util para gestionar precios de servicios de la barbería.
Centraliza la información de precios para evitar inconsistencias.
"""

from typing import Optional, Dict, List

# Diccionario estructurado de precios
PRECIOS_SERVICIOS = {
    "corte": {
        "nombre": "Corte + asesoramiento",
        "precio": 500,
        "keywords": ["corte", "cortes", "pelado", "pelo", "cabello", "visagismo", "asesoramiento"]
    },
    "corte_barba": {
        "nombre": "Corte + asesoramiento + barba",
        "precio": 600,
        "keywords": ["corte y barba", "corte+barba", "corte con barba", "ambos", "los dos", "completo"]
    },
    "barba_perfilada": {
        "nombre": "Barba perfilada",
        "precio": 250,
        "keywords": ["barba perfilada", "perfilada", "perfilar barba", "arreglar barba"]
    },
    "barba_afeitada": {
        "nombre": "Barba afeitada",
        "precio": 200,
        "keywords": ["barba afeitada", "afeitada", "afeitar", "afeitar barba", "rasurar"]
    },
    "cejas": {
        "nombre": "Cejas en base a visagismo",
        "precio": 50,
        "keywords": ["cejas", "ceja", "cejas visagismo"]
    }
}


def obtener_precio_por_nombre(servicio: str) -> Optional[Dict[str, any]]:
    """
    Busca un precio por nombre de servicio.
    Busca en el nombre del servicio y en las keywords asociadas.
    
    Args:
        servicio: Nombre del servicio a buscar (ej: "corte", "barba", "cejas")
        
    Returns:
        Diccionario con "nombre" y "precio" si se encuentra, None si no se encuentra
    """
    if not servicio:
        return None
    
    servicio_lower = servicio.lower().strip()
    
    # Buscar coincidencia exacta o por keywords
    for key, info in PRECIOS_SERVICIOS.items():
        # Buscar en el nombre del servicio
        if servicio_lower in info["nombre"].lower():
            return {
                "nombre": info["nombre"],
                "precio": info["precio"]
            }
        
        # Buscar en keywords
        for keyword in info["keywords"]:
            if keyword.lower() in servicio_lower or servicio_lower in keyword.lower():
                return {
                    "nombre": info["nombre"],
                    "precio": info["precio"]
                }
    
    return None


def obtener_lista_completa_precios() -> str:
    """
    Retorna la lista completa de precios formateada para mostrar al cliente.
    
    Returns:
        String con la lista completa de precios formateada
    """
    lista = []
    for key, info in PRECIOS_SERVICIOS.items():
        lista.append(f"• {info['nombre']} → ${info['precio']}")
    
    return "\n".join(lista)


def obtener_info_precios_para_prompt(texto_usuario: str = "") -> str:
    """
    Obtiene información de precios para incluir en el prompt de Gemini.
    Si el texto del usuario menciona un servicio específico, intenta obtener ese precio.
    Si no, retorna la lista completa.
    
    Args:
        texto_usuario: Texto del mensaje del usuario (opcional)
        
    Returns:
        String con información de precios formateada para el prompt
    """
    if texto_usuario:
        texto_lower = texto_usuario.lower()
        
        # Intentar encontrar un servicio específico mencionado
        precio_encontrado = obtener_precio_por_nombre(texto_usuario)
        
        if precio_encontrado:
            return f"""PRECIOS:
{precio_encontrado['nombre']} → ${precio_encontrado['precio']}

Si el cliente pregunta por otro servicio, aquí está la lista completa:
{obtener_lista_completa_precios()}"""
    
    # Si no se encontró servicio específico o no hay texto, retornar lista completa
    return f"""PRECIOS:
{obtener_lista_completa_precios()}

IMPORTANTE: Estos son los precios oficiales. Úsalos exactamente como están. NO inventes precios ni modifiques estos valores."""


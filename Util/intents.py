"""
Sistema de detección de intenciones basado en keywords.
NO usa Gemini, solo matching de texto.

NOTA: El sistema de respuestas predefinidas (respuestas_barberia.py) tiene prioridad
y usa su propia detección más específica. Este módulo se mantiene para compatibilidad
con el sistema anterior y para intenciones que no tienen respuesta predefinida.
"""

from typing import Optional

# Diccionario de intenciones con sus keywords asociadas
INTENTS = {
    "turnos": [
        "turno", "agendar", "reserva", "agenda", "cita", "disponibilidad",
        "quiero un turno", "necesito turno", "sacar turno", "pedir turno"
    ],
    "cortes": [
        "corte", "pelado", "estilo", "visagismo", "corte de pelo",
        "qué corte", "tipo de corte", "cortes"
    ],
    "diferencial": [
        "diferencial", "qué los diferencia", "qué hace especial",
        "por qué elegir", "qué tienen de especial", "qué los hace diferentes"
    ],
    "precios": [
        "precio", "cuánto sale", "costo", "tarifa", "precios",
        "cuánto cuesta", "precio del", "precio de"
    ],
    "barba": [
        "barba", "arreglo de barba", "afeitado", "hacen barba",
        "hacen barbas", "trabajan barba", "arreglan barba"
    ],
    "productos_lc": [
        "cera", "producto lc", "lc", "styling", "productos",
        "cera modeladora", "cera en polvo", "cera mate", "productos exclusivos",
        "producto exclusivo", "cera brillo"
    ],
    "visagismo_redondo": [
        "cara redonda", "rostro redondo", "tengo cara redonda",
        "cara redonda qué corte", "rostro redondo qué me queda"
    ],
    "visagismo_cuadrado": [
        "cara cuadrada", "rostro cuadrado", "tengo cara cuadrada",
        "cara cuadrada qué corte", "rostro cuadrado qué me queda"
    ],
    "visagismo_ovalado": [
        "cara ovalada", "rostro ovalado", "tengo cara ovalada",
        "cara ovalada qué corte", "rostro ovalado qué me queda"
    ],
    "visagismo_alargado": [
        "cara alargada", "rostro alargado", "cara rectangular",
        "tengo cara alargada", "cara alargada qué corte",
        "rostro alargado qué me queda", "rostro rectangular"
    ],
    "visagismo_diamante": [
        "cara diamante", "rostro diamante", "tengo cara diamante",
        "cara diamante qué corte", "rostro diamante qué me queda"
    ],
    "visagismo_triangular": [
        "cara triangular", "rostro triangular", "tengo cara triangular",
        "cara triangular qué corte", "rostro triangular qué me queda"
    ],
    "visagismo_entradas": [
        "entradas", "calvicie", "pérdida de pelo", "tengo entradas",
        "calvicie incipiente", "pérdida frontal", "entradas pronunciadas"
    ],
    "preguntas_frecuentes": [
        "preguntas frecuentes", "faq", "info general", "información",
        "qué puedo preguntar", "dudas"
    ],
    "niños_mujeres": [
        "niños", "niñas", "mujeres", "mujer", "chicos",
        "atienden niños", "atienden mujeres", "atienden niñas",
        "trabajan con niños", "trabajan con mujeres"
    ],
    "derivar_humano": [
        "hablar con alguien", "humano", "persona", "atendedor",
        "asistente humano", "quiero hablar con", "necesito hablar con",
        "derivar", "contactar con alguien"
    ]
}


def detectar_intencion(texto: str) -> Optional[str]:
    """
    Detecta la intención del usuario basándose en keywords.
    
    Args:
        texto: Texto del mensaje del usuario
        
    Returns:
        Nombre de la intención detectada o None si no hay match claro
    """
    if not texto:
        return None
    
    texto_lower = texto.lower().strip()
    
    # Buscar coincidencias: priorizar matches más específicos primero
    # (frases completas antes de palabras sueltas)
    
    # Primero buscar frases completas (más específicas)
    for intencion, keywords in INTENTS.items():
        for keyword in keywords:
            if keyword in texto_lower:
                return intencion
    
    return None

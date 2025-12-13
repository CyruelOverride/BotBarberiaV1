"""
Módulo de flujo automático para resolver mensajes usando solo keywords.
NO usa Gemini, solo matching de texto y respuestas predefinidas.
"""

from typing import Optional
from Util.respuestas_barberia import detectar_intencion_respuesta, get_response
from Util.intents import detectar_intencion
from Util.informacion_barberia import get_info_por_intencion


def procesar_flujo_automatico(
    texto_usuario: str,
    intencion: str = None,
    info_relevante: str = None
) -> Optional[str]:
    """
    Intenta resolver el mensaje usando solo keywords y respuestas predefinidas.
    NO usa Gemini.
    
    Args:
        texto_usuario: Mensaje del usuario
        intencion: Intención ya detectada (opcional, para evitar detectarla de nuevo)
        info_relevante: Información relevante ya obtenida (opcional)
    
    Returns:
        Respuesta si encuentra coincidencia, None si no encuentra nada
    """
    print("🔄 FLUJO AUTOMÁTICO: Iniciando procesamiento...")
    
    if not texto_usuario:
        print("⚠️ FLUJO AUTOMÁTICO: Texto vacío, retornando None")
        return None
    
    texto_lower = texto_usuario.lower().strip()
    print(f"🔄 FLUJO AUTOMÁTICO: Procesando mensaje: '{texto_usuario[:50]}...'")
    
    # PRIORIDAD 1: Intentar detectar respuesta predefinida (más específico)
    print("🔄 FLUJO AUTOMÁTICO: Intentando detectar respuesta predefinida...")
    resultado_respuesta = detectar_intencion_respuesta(texto_usuario)
    
    if resultado_respuesta:
        intencion_detectada, clave = resultado_respuesta
        respuesta = get_response(intencion_detectada, clave)
        if respuesta:
            print(f"✅ FLUJO AUTOMÁTICO: Respuesta predefinida encontrada ({intencion_detectada}.{clave})")
            return respuesta
        else:
            print(f"⚠️ FLUJO AUTOMÁTICO: Intención detectada pero sin respuesta ({intencion_detectada}.{clave})")
    else:
        print("⚠️ FLUJO AUTOMÁTICO: No se encontró respuesta predefinida")
    
    # PRIORIDAD 2: Si no hay respuesta predefinida, intentar detectar intención general
    if not intencion:
        print("🔄 FLUJO AUTOMÁTICO: Intentando detectar intención general...")
        intencion = detectar_intencion(texto_usuario)
    
    if intencion:
        print(f"🔄 FLUJO AUTOMÁTICO: Intención detectada: '{intencion}'")
        # Si hay intención pero no info_relevante, obtenerla
        if not info_relevante:
            print(f"🔄 FLUJO AUTOMÁTICO: Obteniendo información para intención '{intencion}'...")
            info_relevante = get_info_por_intencion(intencion)
        
        # Si hay información relevante, construir respuesta breve
        if info_relevante:
            print(f"🔄 FLUJO AUTOMÁTICO: Construyendo respuesta para intención '{intencion}'...")
            # Construir respuesta basada en la intención detectada
            respuesta = _construir_respuesta_por_intencion(intencion, info_relevante, texto_usuario)
            if respuesta:
                print(f"✅ FLUJO AUTOMÁTICO: Respuesta construida exitosamente para intención '{intencion}'")
                return respuesta
            else:
                print(f"⚠️ FLUJO AUTOMÁTICO: No se pudo construir respuesta para intención '{intencion}'")
        else:
            print(f"⚠️ FLUJO AUTOMÁTICO: No hay información relevante para intención '{intencion}'")
    else:
        print("⚠️ FLUJO AUTOMÁTICO: No se detectó ninguna intención")
    
    # Si no encuentra nada, retornar None para que se use Gemini
    print("❌ FLUJO AUTOMÁTICO: No se encontró coincidencia, se usará Gemini")
    return None


def _construir_respuesta_por_intencion(intencion: str, info_relevante: str, texto_usuario: str) -> Optional[str]:
    """
    Construye una respuesta breve basada en la intención y la información relevante.
    
    Args:
        intencion: Intención detectada
        info_relevante: Información relevante para esa intención
        texto_usuario: Mensaje original del usuario
        
    Returns:
        Respuesta construida o None si no se puede construir
    """
    if not intencion or not texto_usuario:
        return None
    
    if not intencion or not texto_usuario:
        return None
    
    texto_lower = texto_usuario.lower()
    
    # Respuestas específicas según intención
    if intencion.startswith("visagismo_"):
        # Para visagismo, dar información directa
        tipo_rostro = intencion.replace("visagismo_", "").replace("_", " ")
        
        # Extraer recomendaciones principales de la info
        recomendaciones = []
        if info_relevante:
            if "volumen arriba" in info_relevante.lower() or "pompadour" in info_relevante.lower():
                recomendaciones.append("volumen arriba")
            if "fade" in info_relevante.lower() or "degradado" in info_relevante.lower():
                recomendaciones.append("degradados")
            if "barba" in info_relevante.lower():
                recomendaciones.append("barba")
        
        respuesta = f"Bro, para {tipo_rostro} te puedo hacer: "
        if recomendaciones:
            respuesta += ", ".join(recomendaciones[:3])
        else:
            respuesta += "un corte que te favorezca según tu estructura"
        respuesta += ". Te puedo hacer esto o contame si tenes una idea ya."
        
        return respuesta
    
    elif intencion == "turnos":
        return "Bro, podés agendar tu turno desde el link de la agenda. Ahí ves todos los horarios disponibles y elegís el que te quede mejor."
    
    elif intencion == "precios":
        return "Bro, el valor depende de lo que vos quieras hacerte. Te paso la lista:\n• Corte + asesoramiento → $500\n• Corte + asesoramiento + barba → $600\n• Barba perfilada → $250\n• Barba afeitada → $200\n• Cejas en base a visagismo → $50"
    
    elif intencion == "ubicacion" or "donde" in texto_lower or "ubicacion" in texto_lower:
        return "Estamos en Juan José de Amézaga 2241. Te dejo la ubicación exacta en Google Maps."
    
    elif intencion == "barba":
        return "Sí bro, se realizan trabajos de barba, también en base al tipo de rostro. Analizamos tu tipo de rostro y barba para crear un estilo que te quede perfecto."
    
    elif intencion == "productos_lc":
        return "Sí, también se venden productos de la marca LC para mantener el corte perfecto todos los días. Valor: $500 cada uno. Podés reservar el producto para retirarlo en la barbería."
    
    elif intencion == "diferencial":
        return "Bro, el diferencial es que hacemos cortes basados en visagismo: analizamos el rostro y creamos un corte a medida. Además, trabajamos el styling con productos y herramientas para que te veas como querés. Trabajamos solo con turnos para que no tengas que esperar."
    
    elif intencion == "cortes":
        return "Bro, el servicio se basa en cortes personalizados según el rostro (visagismo). Analizamos estructura craneal, tipo de rostro, tipo de cabello, volumen y densidad. A partir de eso decidimos qué corte va mejor con tu fisonomía."
    
    # Si no hay respuesta específica, intentar construir una genérica basada en la info
    if info_relevante:
        # Extraer las primeras líneas relevantes de la información
        lineas = info_relevante.split('\n')[:3]
        respuesta_base = '\n'.join(lineas)
        
        # Si la respuesta es muy larga, acortarla
        if len(respuesta_base) > 300:
            respuesta_base = respuesta_base[:300] + "..."
        
        return respuesta_base
    
    return None


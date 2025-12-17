"""
Router de mensajes: Decide qué handler usar según prioridades.
Solo routing, no lógica de negocio.
"""

from typing import Optional, Tuple, Any
from Util.intent_detector import detectar_intencion_unificada
from Util.message_handlers import (
    handle_demora,
    handle_derivacion,
    handle_link_agenda,
    handle_precios,
    handle_gemini_response
)
from Util.respuestas_barberia import get_response, reemplazar_links
from Util.informacion_barberia import get_info_por_intencion
from Util.token_optimizer import count_tokens, build_modular_prompt, compress_history
from Util.flujo_automatico import procesar_flujo_automatico


def handle_commands(texto_lower: str, chat_instance: Any) -> Optional[str]:
    """
    Maneja comandos especiales (ayuda, cancelar).
    
    Args:
        texto_lower: Texto en minúsculas
        chat_instance: Instancia de Chat
        
    Returns:
        Respuesta del comando o None si no es un comando
    """
    # Comandos especiales (sin delay)
    if texto_lower in ("cancelar", "salir", "cancel"):
        chat_instance.clear_state(chat_instance.id_chat.replace("chat_", "") if chat_instance.id_chat else "")
        from Util.estado import clear_citas
        numero = chat_instance.id_chat.replace("chat_", "") if chat_instance.id_chat else ""
        clear_citas(numero)
        return "❌ Operación cancelada."
    
    # Verificar si hay un comando registrado (ej: "ayuda")
    if texto_lower in chat_instance.function_graph:
        return chat_instance.function_graph[texto_lower]['function'](
            chat_instance.id_chat.replace("chat_", "") if chat_instance.id_chat else "",
            texto_lower
        )
    
    return None


def handle_sequential_flow(
    texto: str,
    texto_strip: str,
    chat_instance: Any,
    link_reserva: str
) -> Optional[str]:
    """
    Maneja flujo secuencial de bienvenida.
    
    Args:
        texto: Texto original
        texto_strip: Texto sin espacios
        chat_instance: Instancia de Chat
        link_reserva: Link de reserva
        
    Returns:
        Respuesta del flujo secuencial o None si no aplica
    """
    numero = chat_instance.id_chat.replace("chat_", "") if chat_instance.id_chat else ""
    
    # Paso 1: Saludo inicial
    if chat_instance.es_saludo(texto_strip) and not chat_instance.ya_se_saludo(numero):
        chat_instance.marcar_saludo(numero)
        link_maps = "https://maps.app.goo.gl/uaJPmJrxUJr5wZE87"
        saludo_inicial = handle_gemini_response(
            intencion="saludo_inicial",
            texto=texto_strip,
            info_relevante="",
            link_agenda=link_reserva,
            link_maps=link_maps,
            ya_hay_contexto=False,
            chat_service=None,  # Comentado: No se usa más la base de datos
            id_chat=chat_instance.id_chat,
            respuesta_predefinida=None
        )
        return saludo_inicial
    
    # Paso 2-4: Flujo de bienvenida
    flujo_paso = chat_instance.get_flujo_paso(numero)
    
    # Si está en paso "saludo_inicial" y ya se saludó
    if flujo_paso == "saludo_inicial" and chat_instance.ya_se_saludo(numero):
        if chat_instance.quiere_link(texto_strip):
            chat_instance.set_flujo_paso(numero, "link_enviado")
            return handle_link_agenda(
                texto=texto_strip,
                link_agenda=link_reserva,
                chat_service=None,  # Comentado: No se usa más la base de datos
                id_chat=chat_instance.id_chat,
                ya_hay_contexto=True
            )
        elif chat_instance.es_respuesta_positiva(texto_strip):
            chat_instance.set_flujo_paso(numero, "agendar_turno")
            return handle_gemini_response(
                intencion="agendar_turno",
                texto=texto_strip,
                info_relevante="",
                link_agenda=link_reserva,
                link_maps="",
                ya_hay_contexto=True,
                chat_service=None,  # Comentado: No se usa más la base de datos
                id_chat=chat_instance.id_chat,
                respuesta_predefinida=None
            )
    
    # Paso 3: Si está en paso "agendar_turno"
    if flujo_paso == "agendar_turno":
        if chat_instance.quiere_link(texto_strip):
            chat_instance.set_flujo_paso(numero, "link_enviado")
            return handle_link_agenda(
                texto=texto_strip,
                link_agenda=link_reserva,
                chat_service=None,  # Comentado: No se usa más la base de datos
                id_chat=chat_instance.id_chat,
                ya_hay_contexto=True
            )
        elif chat_instance.es_respuesta_positiva(texto_strip):
            chat_instance.set_flujo_paso(numero, "link_enviado")
            return handle_link_agenda(
                texto=texto_strip,
                link_agenda=link_reserva,
                chat_service=None,  # Comentado: No se usa más la base de datos
                id_chat=chat_instance.id_chat,
                ya_hay_contexto=True
            )
    
    # Paso 4: Confirmación de reserva
    texto_lower = texto_strip.lower()
    if flujo_paso == "link_enviado" and any(palabra in texto_lower for palabra in 
        ["ya agende", "ya agendé", "reserve", "reservé", "ya reservé", "ya reserve", 
         "listo", "listo agende", "agende", "agendé", "confirmado", "ya está"]):
        chat_instance.set_flujo_paso(numero, "reserva_confirmada")
        return handle_gemini_response(
            intencion="post_reserva",
            texto=texto_strip,
            info_relevante="",
            link_agenda="",
            link_maps="",
            ya_hay_contexto=True,
            chat_service=None,  # Comentado: No se usa más la base de datos
            id_chat=chat_instance.id_chat,
            respuesta_predefinida=None
        )
    
    return None


def handle_critical_rules(
    texto: str,
    texto_strip: str,
    chat_instance: Any,
    link_reserva: str
) -> Optional[str]:
    """
    Maneja reglas críticas (demoras, derivación, link explícito).
    
    Args:
        texto: Texto original
        texto_strip: Texto sin espacios
        chat_instance: Instancia de Chat
        link_reserva: Link de reserva
        
    Returns:
        Respuesta de regla crítica o None si no aplica
    """
    # Detectar aviso de demora (política determinística)
    respuesta_demora = handle_demora(texto_strip, link_reserva, chat_instance)
    if respuesta_demora:
        return respuesta_demora
    
    # Detectar intención unificada
    resultado_intencion = detectar_intencion_unificada(texto_strip)
    
    if resultado_intencion:
        intencion, fuente, metadata = resultado_intencion
        
        # Derivación a humano
        if intencion == "derivar_humano":
            numero_derivacion = (
                chat_instance.numero_derivacion 
                if hasattr(chat_instance, 'numero_derivacion') and chat_instance.numero_derivacion 
                else "59891453663"
            )
            return handle_derivacion(numero_derivacion)
        
        # Link explícito
        if chat_instance.quiere_link(texto_strip):
            return handle_link_agenda(
                texto=texto_strip,
                link_agenda=link_reserva,
                chat_service=None,  # Comentado: No se usa más la base de datos
                id_chat=chat_instance.id_chat,
                ya_hay_contexto=True
            )
    
    return None


def handle_predefined_responses(
    texto_strip: str,
    link_reserva: str,
    link_maps: str
) -> Optional[str]:
    """
    Maneja respuestas predefinidas con keywords directos.
    
    Args:
        texto_strip: Texto sin espacios
        link_reserva: Link de reserva
        link_maps: Link de maps
        
    Returns:
        Respuesta predefinida o None si no hay match
    """
    try:
        from Util.respuestas_barberia import detectar_intencion_respuesta
        resultado_keywords = detectar_intencion_respuesta(texto_strip)
        if resultado_keywords:
            intencion_kw, clave_kw = resultado_keywords
            respuesta_predefinida = get_response(intencion_kw, clave_kw)
            if respuesta_predefinida:
                respuesta_final = reemplazar_links(respuesta_predefinida, link_reserva, link_maps)
                
                # Si es sobre turnos/agenda y no tiene link, agregarlo
                texto_lower = texto_strip.lower()
                if ("turno" in texto_lower or "agenda" in texto_lower or "reserva" in texto_lower) and link_reserva:
                    if link_reserva not in respuesta_final:
                        respuesta_final += f"\n\n{link_reserva}"
                
                return respuesta_final
    except Exception as e:
        print(f"⚠️ Error en sistema de respuestas predefinidas: {e}")
        from Util.error_handler import manejar_error
        manejar_error(e, texto_strip, None)
    
    return None


def handle_gemini_generation(
    texto_strip: str,
    chat_instance: Any,
    link_reserva: str,
    link_maps: str
) -> Optional[str]:
    """
    Maneja generación con Gemini.
    
    Args:
        texto_strip: Texto sin espacios
        chat_instance: Instancia de Chat
        link_reserva: Link de reserva
        link_maps: Link de maps
        
    Returns:
        Respuesta generada por Gemini o None si hay error
    """
    # Detectar intención unificada
    resultado_intencion = detectar_intencion_unificada(texto_strip)
    intencion = resultado_intencion[0] if resultado_intencion else None
    
    # Obtener info relevante
    info_relevante = ""
    if intencion:
        info_relevante = get_info_por_intencion(intencion, texto_strip)
    
    numero = chat_instance.id_chat.replace("chat_", "") if chat_instance.id_chat else ""
    ya_hay_contexto = chat_instance.ya_se_saludo(numero) or bool(intencion)
    
    # Comentado: No se usa más la base de datos
    # Obtener historial cuando hay contexto
    historial_comprimido = ""
    ultimos_mensajes = None
    # if ya_hay_contexto and chat_instance.chat_service and chat_instance.id_chat:
    #     try:
    #         ultimos_mensajes = chat_instance.chat_service.obtener_ultimos_mensajes(chat_instance.id_chat, limite=4)
    #         todos_mensajes = chat_instance.chat_service.obtener_todos_mensajes(chat_instance.id_chat)
    #         if todos_mensajes and len(todos_mensajes) > 10:
    #             historial_comprimido = compress_history(todos_mensajes)
    #     except Exception as e:
    #         print(f"⚠️ Error obteniendo historial: {e}")
    
    # Estimar tokens
    prompt_estimado = build_modular_prompt(
        intencion=intencion if intencion else "",
        texto_usuario=texto_strip,
        info_relevante=info_relevante,
        historial_comprimido=historial_comprimido,
        ultimos_mensajes=ultimos_mensajes,
        ya_hay_contexto=ya_hay_contexto
    )
    tokens_estimados = count_tokens(prompt_estimado, use_api=False)
    print(f"📊 Tokens estimados: {tokens_estimados}")
    
    try:
        # Si tokens <= 500, usar Gemini directamente
        if tokens_estimados <= 500:
            print(f"✅ Tokens <= 500, usando Gemini directamente")
            respuesta = handle_gemini_response(
                intencion=intencion if intencion else "",
                texto=texto_strip,
                info_relevante=info_relevante,
                link_agenda=link_reserva,
                link_maps=link_maps,
                ya_hay_contexto=ya_hay_contexto,
                chat_service=None,  # Comentado: No se usa más la base de datos
                id_chat=chat_instance.id_chat,
                respuesta_predefinida=None
            )
        else:
            # Si tokens > 500, intentar flujo automático primero
            print(f"⚠️ Tokens > 500, intentando flujo automático primero...")
            respuesta_automatica = procesar_flujo_automatico(
                texto_usuario=texto_strip,
                intencion=intencion if intencion else "",
                info_relevante=info_relevante
            )
            
            if respuesta_automatica:
                print(f"✅ Flujo automático exitoso, evitando Gemini")
                respuesta = respuesta_automatica
            else:
                # Si no encuentra nada, usar Gemini de todas formas
                print(f"⚠️ Flujo automático no encontró respuesta, usando Gemini")
                respuesta = handle_gemini_response(
                    intencion=intencion if intencion else "",
                    texto=texto_strip,
                    info_relevante=info_relevante,
                    link_agenda=link_reserva,
                    link_maps=link_maps,
                    ya_hay_contexto=ya_hay_contexto,
                    chat_service=None,  # Comentado: No se usa más la base de datos
                    id_chat=chat_instance.id_chat,
                    respuesta_predefinida=None
                )
        
        if not respuesta:
            return None
        
        # Reemplazar links
        respuesta_final = reemplazar_links(respuesta, link_reserva, link_maps)
        
        # FORZAR link si es necesario
        texto_lower = texto_strip.lower()
        debe_incluir_link = False
        if intencion and intencion.lower() in ["turnos", "link_agenda"]:
            debe_incluir_link = True
        elif "turno" in texto_lower or "agenda" in texto_lower or "reserva" in texto_lower:
            debe_incluir_link = True
        
        if debe_incluir_link and link_reserva and link_reserva not in respuesta_final:
            respuesta_final += f"\n\n{link_reserva}"
        
        return respuesta_final
        
    except Exception as e:
        print(f"⚠️ Error al generar respuesta con Gemini: {e}")
        from Util.error_handler import manejar_error
        manejar_error(e, texto_strip, None)
        
        # FALLBACK: Intentar flujo automático
        try:
            intencion_fallback = detectar_intencion_unificada(texto_strip)
            intencion_fallback_str = intencion_fallback[0] if intencion_fallback else ""
            info_relevante_fallback = get_info_por_intencion(intencion_fallback_str, texto_strip) if intencion_fallback_str else ""
            
            respuesta_automatica = procesar_flujo_automatico(
                texto_usuario=texto_strip,
                intencion=intencion_fallback_str,
                info_relevante=info_relevante_fallback
            )
            
            if respuesta_automatica:
                respuesta_final = reemplazar_links(respuesta_automatica, link_reserva, link_maps)
                return respuesta_final
        except Exception as e2:
            print(f"⚠️ Error en flujo automático fallback: {e2}")
        
        return None


def route_message(numero: str, texto: str, chat_instance: Any) -> Optional[str]:
    """
    Función principal del router que decide qué handler usar según prioridades.
    
    Args:
        numero: Número del cliente
        texto: Mensaje del usuario
        chat_instance: Instancia de Chat
        
    Returns:
        Respuesta del handler o None si no se puede procesar
    """
    texto_strip = texto.strip()
    texto_lower = texto_strip.lower()
    
    link_reserva = chat_instance.link_reserva if chat_instance.link_reserva else "linkagenda.com"
    link_maps = "https://maps.app.goo.gl/uaJPmJrxUJr5wZE87"
    
    # PRIORIDAD 0: Comandos especiales (sin delay)
    respuesta = handle_commands(texto_lower, chat_instance)
    if respuesta:
        return respuesta
    
    # PRIORIDAD 1: Flujo secuencial de bienvenida
    respuesta = handle_sequential_flow(texto, texto_strip, chat_instance, link_reserva)
    if respuesta:
        return respuesta
    
    # PRIORIDAD 2: Reglas críticas (demoras, derivación, link explícito)
    respuesta = handle_critical_rules(texto, texto_strip, chat_instance, link_reserva)
    if respuesta:
        return respuesta
    
    # PRIORIDAD 3: Respuestas predefinidas
    respuesta = handle_predefined_responses(texto_strip, link_reserva, link_maps)
    if respuesta:
        return respuesta
    
    # PRIORIDAD 4: Generación con Gemini
    respuesta = handle_gemini_generation(texto_strip, chat_instance, link_reserva, link_maps)
    if respuesta:
        return respuesta
    
    # FALLBACK: Mensaje por defecto
    numero_clean = chat_instance.id_chat.replace("chat_", "") if chat_instance.id_chat else numero
    ya_hay_contexto = chat_instance.ya_se_saludo(numero_clean) if hasattr(chat_instance, 'ya_se_saludo') else False
    
    if ya_hay_contexto:
        return "Escribime lo que necesites o escribí *ayuda* para ver las opciones."
    else:
        return "¡Bro! ¿Todo bien?\n\nEscribime lo que necesites o escribí *ayuda* para ver las opciones."


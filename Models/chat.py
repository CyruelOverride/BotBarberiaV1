from typing import Any, Optional, Dict, Callable
from datetime import datetime
import re
from Services.ChatService import ChatService
from Services.ClienteService import ClienteService
from Services.RepartidorService import RepartidorService
from Util.database import get_db_session
from whatsapp_api import enviar_mensaje_whatsapp
from Util.estado import get_estado, reset_estado, get_waiting_for, set_waiting_for, clear_waiting_for, get_citas, add_cita, clear_citas
from Util.repartidor_util import handle_interactive
from Util.calificacion_util import manejar_calificacion
from Util.procesar_texto_gemini import detectar_consulta_reserva, generar_respuesta_barberia
from Util.intents import detectar_intencion
from Util.informacion_barberia import get_info_por_intencion, LINK_RESERVA, NUMERO_DERIVACION
from Util.respuestas_barberia import get_respuesta_predefinida, reemplazar_links, get_response, detectar_intencion_respuesta
from Util.token_optimizer import count_tokens, build_modular_prompt, compress_history
from Util.error_handler import manejar_error, registrar_mensaje


class Chat:
    # Variable para el link de reserva (configurar con link de Weybook)
    # Ejemplo: link_reserva = "https://weybook.com/barberia"
    link_reserva = ""
    
    # Variable para el número de derivación en caso de errores o cuando el cliente lo solicite
    # Ejemplo: numero_derivacion = "+5491234567890"
    numero_derivacion = "+59891453663"
    
    def __init__(self, id_chat=None, id_cliente=None, id_repartidor=None, chat_service=None):
        self.id_chat = id_chat
        self.id_cliente = id_cliente
        self.id_repartidor = id_repartidor
        
        if chat_service:
            self.chat_service = chat_service
        else:
            db_session = get_db_session()
            self.chat_service = ChatService(db_session)

        
        self.conversation_data: Dict[str, Any] = {}
        
        self.function_graph: Dict[str, Dict] = {}
        self._register_commands()
        
        # Flujo antiguo comentado para referencia
        # self.function_map = {
        #     "flujo_inicio": self.flujo_inicio,
        #     "flujo_nombre_completo": self.flujo_nombre_completo,
        #     "flujo_servicio": self.flujo_servicio,
        #     "flujo_dia_hora": self.flujo_dia_hora,
        #     "flujo_confirmacion_cita": self.flujo_confirmacion_cita,
        # }
        
    
    def _register_commands(self):
        self.function_graph = {
            "ayuda": {
                'function': self.funcion_ayuda,
                'name': 'funcion_ayuda',
                'doc': self.funcion_ayuda.__doc__,
                'command': 'ayuda'
            },
        }
    
    def get_session(self, numero):
        estado = get_estado(numero)
        return estado
    
    def reset_session(self, numero):
        reset_estado(numero)
    
    def clear_state(self, numero):
        self.reset_session(numero)
        self.reset_conversation(numero)
    
    def set_waiting_for(self, numero, func_name: str, context_data=None):
        set_waiting_for(numero, func_name, context_data)
        print(f"{numero}: Esperando respuesta para: {func_name}")
    
    def set_conversation_data(self, key: str, value: Any):
        self.conversation_data[key] = value
    
    def get_conversation_data(self, key: str, default: Any = None) -> Any:
        return self.conversation_data.get(key, default)
    
    def clear_conversation_data(self):
        self.conversation_data = {}
    
    def reset_conversation(self, numero):
        clear_waiting_for(numero)
        self.conversation_data = {}
        print("Conversación reseteada.")
    
    def is_waiting_response(self, numero) -> bool:
        return get_waiting_for(numero) is not None
    
    def print_state(self):
        print(f"\n{'='*60}")
        print("ESTADO DE LA CONVERSACIÓN")
        print(f"{'='*60}")
        estado_memoria = get_estado(self.id_cliente if isinstance(self.id_cliente, str) else "") if self.id_cliente else "N/A"
        print(f"Estado en memoria: {estado_memoria}")
        print(f"Datos de conversación: {self.conversation_data}")
        print(f"{'='*60}\n")

    def es_saludo(self, texto: str) -> bool:
        """
        Detecta si el mensaje es un saludo.
        
        Args:
            texto: Mensaje del usuario
            
        Returns:
            True si es un saludo, False si no
        """
        texto_lower = texto.lower().strip()
        
        # Limpiar signos de puntuación para mejor detección
        texto_limpio = re.sub(r'[.,;:!?¿¡]', '', texto_lower)
        
        # Palabras y frases de saludo
        saludos = [
            "hola", "holi", "holis",
            "buenas", "buenos días", "buenos dias", "buen día", "buen dia",
            "buenas tardes", "buenas noches",
            "que tal", "qué tal", "que onda", "qué onda",
            "como estas", "cómo estás",
            "todo bien", "qué hay", "que hay"
        ]
        
        # Verificar si el texto contiene saludos
        for saludo in saludos:
            # Buscar el saludo en el texto limpio (sin puntuación)
            if saludo in texto_limpio:
                # Si el texto es muy corto o es principalmente el saludo, es un saludo
                # También verificar si empieza con el saludo (con o sin puntuación)
                if len(texto_limpio) <= len(saludo) + 10 or texto_limpio.startswith(saludo):
                    return True
        
        # Caso especial: "buenas" seguido de "todo bien" (con o sin coma)
        if "buenas" in texto_limpio and "todo bien" in texto_limpio:
            return True
        
        return False
    
    def ya_se_saludo(self, numero: str) -> bool:
        """
        Verifica si ya se saludó en esta conversación.
        
        Args:
            numero: Número del cliente
            
        Returns:
            True si ya se saludó, False si no
        """
        estado = get_estado(numero)
        return estado.get("context_data", {}).get("ya_se_saludo", False)
    
    def marcar_saludo(self, numero: str):
        """
        Marca que ya se saludó en esta conversación.
        
        Args:
            numero: Número del cliente
        """
        estado = get_estado(numero)
        if "context_data" not in estado:
            estado["context_data"] = {}
        estado["context_data"]["ya_se_saludo"] = True
        estado["context_data"]["flujo_paso"] = "saludo_inicial"  # Iniciar flujo
    
    def get_flujo_paso(self, numero: str) -> str:
        """Obtiene el paso actual del flujo."""
        estado = get_estado(numero)
        return estado.get("context_data", {}).get("flujo_paso", "")
    
    def set_flujo_paso(self, numero: str, paso: str):
        """Establece el paso actual del flujo."""
        estado = get_estado(numero)
        if "context_data" not in estado:
            estado["context_data"] = {}
        estado["context_data"]["flujo_paso"] = paso
    
    def es_respuesta_positiva(self, texto: str) -> bool:
        """
        Detecta si la respuesta es positiva (sí, dale, perfecto, etc.).
        
        Args:
            texto: Mensaje del usuario
            
        Returns:
            True si es positiva, False si no
        """
        texto_lower = texto.lower().strip()
        positivas = ["si", "sí", "dale", "ok", "perfecto", "bueno", "bien", "claro", "por supuesto", 
                     "de acuerdo", "vamos", "joya", "genial", "buenísimo", "buenisimo", "👍", "👌"]
        
        # Si el texto es muy corto y contiene palabras positivas
        if len(texto_lower) <= 20:
            for palabra in positivas:
                if palabra in texto_lower:
                    return True
        
        # Si contiene "no" explícitamente, es negativa
        if any(neg in texto_lower for neg in ["no", "nop", "tampoco", "mejor no"]):
            return False
        
        return False
    
    def quiere_link(self, texto: str) -> bool:
        """
        Detecta si el usuario está pidiendo explícitamente el link de la agenda.
        
        Args:
            texto: Mensaje del usuario
            
        Returns:
            True si está pidiendo el link, False si no
        """
        if not texto:
            return False
        
        texto_lower = texto.lower().strip()
        
        # Frases que indican que quiere el link
        frases_link = [
            "pasame", "pásame", "pasame el link", "pásame el link",
            "dale pasame", "dale pásame", "pasame el link", "pásame el link",
            "pásame la agenda", "pasame la agenda", "pásame link", "pasame link",
            "mandame", "mándame", "mandame el link", "mándame el link",
            "dame", "dame el link", "dame link", "dame la agenda",
            "envíame", "envíame el link", "envíame link", "envíame la agenda",
            "quiero agendar", "quiero reservar", "quiero turno",
            "necesito agendar", "necesito reservar", "necesito turno",
            "link", "la agenda", "el link", "link de agenda"
        ]
        
        # Si el mensaje es corto y contiene alguna frase de link
        if len(texto_lower) <= 30:
            for frase in frases_link:
                if frase in texto_lower:
                    return True
        
        return False

    def funcion_ayuda(self, numero, texto):
        ayuda_texto = (
            "¡Hola hermano!\n\n"
            "Soy el asistente de la barbería. Te puedo ayudar con:\n\n"
            "*Turnos y reservas*\n"
            "• Agendar tu turno\n"
            "• Consultar disponibilidad\n"
            "• Cancelar o reagendar\n\n"
            "*Info sobre cortes*\n"
            "• Qué incluye el servicio\n"
            "• Precios\n"
            "• Visagismo (qué corte te queda según tu tipo de rostro)\n"
            "• Servicios de barba\n\n"
            "*Productos LC*\n"
            "• Info sobre productos exclusivos\n"
            "• Precios y disponibilidad\n\n"
            "*Preguntas frecuentes*\n"
            "• Diferencial del servicio\n"
            "• Ubicación\n"
            "• Formas de pago\n"
            "• Horarios\n\n"
            "Escribime lo que necesites, bro. Estoy acá para ayudarte."
        )
        return enviar_mensaje_whatsapp(numero, ayuda_texto)

    def handle_text(self, numero, texto):
        """
        Procesa mensajes de texto del cliente.
        Flujo enfocado en barbería: turnos, cortes, visagismo, productos LC, etc.
        """
        texto_strip = texto.strip()
        texto_lower = texto_strip.lower()
        
        # Verificar si es repartidor (funcionalidad separada)
        repartidor_service = RepartidorService()
        repartidor = repartidor_service.obtener_repartidor_por_telefono(numero)

        if repartidor:
            print(f"Repartidor: {repartidor}")

            if texto_strip.startswith("pedido_") or texto_strip.startswith("entregado_"):
                if texto_strip.startswith("entregado_"):
                    interactive = {
                        "type": "button_reply",
                        "button_reply": { "id": texto_strip }
                    }
                else:
                    interactive = {
                        "type": "list_reply",
                        "list_reply": { "id": texto_strip }
                    }

                resultado = handle_interactive(numero, interactive)
                return resultado

            return enviar_mensaje_whatsapp(numero, "Eres repartidor no puedo procesar un mensaje que no sea conversacion")

        # Manejar calificaciones
        if texto_strip.startswith("calificar_"):
            return manejar_calificacion(numero, texto_strip)

        if not self.id_chat:
            self.id_chat = f"chat_{numero}"

        # Comandos especiales
        if texto_lower in ("cancelar", "salir", "cancel"):
            self.clear_state(numero)
            clear_citas(numero)
            return enviar_mensaje_whatsapp(numero, "❌ Operación cancelada.")

        # Verificar si hay un comando registrado (ej: "ayuda")
        if texto_lower in self.function_graph:
            return self.function_graph[texto_lower]['function'](numero, texto_lower)

        # ============================================
        # PRIORIDAD 0: FLUJO SECUENCIAL DE BIENVENIDA
        # ============================================
        # Paso 1: Saludo inicial (usar Gemini con ejemplos)
        if self.es_saludo(texto_strip) and not self.ya_se_saludo(numero):
            self.marcar_saludo(numero)
            link_reserva = self.link_reserva if self.link_reserva else LINK_RESERVA
            link_maps = "https://maps.app.goo.gl/uaJPmJrxUJr5wZE87"
            saludo_inicial = generar_respuesta_barberia(
                intencion="saludo_inicial",
                texto_usuario=texto_strip,
                info_relevante="",
                link_agenda=link_reserva,
                link_maps=link_maps,
                ya_hay_contexto=False,
                chat_service=self.chat_service,
                id_chat=self.id_chat,
                respuesta_predefinida=None
            )
            if saludo_inicial:
                if self.id_chat:
                    self.chat_service.registrar_mensaje(self.id_chat, saludo_inicial, es_cliente=False)
                return enviar_mensaje_whatsapp(numero, saludo_inicial)
        
        # Paso 2: Si ya se saludó y está en paso "saludo_inicial", detectar respuesta positiva
        flujo_paso = self.get_flujo_paso(numero)
        if flujo_paso == "saludo_inicial" and self.ya_se_saludo(numero):
            # PRIORIDAD: Si pide el link explícitamente, enviarlo con Gemini pero FORZAR link
            if self.quiere_link(texto_strip):
                self.set_flujo_paso(numero, "link_enviado")
                link_reserva = self.link_reserva if self.link_reserva else LINK_RESERVA
                respuesta = generar_respuesta_barberia(
                    intencion="link_agenda",
                    texto_usuario=texto_strip,
                    info_relevante="",
                    link_agenda=link_reserva,
                    link_maps="",
                    ya_hay_contexto=True,
                    chat_service=self.chat_service,
                    id_chat=self.id_chat,
                    respuesta_predefinida=None
                )
                if respuesta:
                    respuesta = reemplazar_links(respuesta, link_reserva, "")
                    # FORZAR link SIEMPRE al final si no está presente
                    if link_reserva and link_reserva not in respuesta:
                        respuesta = f"{respuesta}\n\n{link_reserva}"
                    if self.id_chat:
                        self.chat_service.registrar_mensaje(self.id_chat, respuesta, es_cliente=False)
                    return enviar_mensaje_whatsapp(numero, respuesta)
            elif self.es_respuesta_positiva(texto_strip):
                self.set_flujo_paso(numero, "agendar_turno")
                link_reserva = self.link_reserva if self.link_reserva else LINK_RESERVA
                respuesta = generar_respuesta_barberia(
                    intencion="agendar_turno",
                    texto_usuario=texto_strip,
                    info_relevante="",
                    link_agenda=link_reserva,
                    link_maps="",
                    ya_hay_contexto=True,
                    chat_service=self.chat_service,
                    id_chat=self.id_chat,
                    respuesta_predefinida=None
                )
                if respuesta:
                    if self.id_chat:
                        self.chat_service.registrar_mensaje(self.id_chat, respuesta, es_cliente=False)
                    return enviar_mensaje_whatsapp(numero, respuesta)
            # Si es negativa o no clara, continuar con flujo normal
        
        # Paso 3: Si está en paso "agendar_turno", detectar respuesta positiva y enviar link
        if flujo_paso == "agendar_turno":
            # PRIORIDAD: Si pide el link explícitamente, enviarlo con Gemini pero FORZAR link
            if self.quiere_link(texto_strip):
                self.set_flujo_paso(numero, "link_enviado")
                link_reserva = self.link_reserva if self.link_reserva else LINK_RESERVA
                respuesta = generar_respuesta_barberia(
                    intencion="link_agenda",
                    texto_usuario=texto_strip,
                    info_relevante="",
                    link_agenda=link_reserva,
                    link_maps="",
                    ya_hay_contexto=True,
                    chat_service=self.chat_service,
                    id_chat=self.id_chat,
                    respuesta_predefinida=None
                )
                if respuesta:
                    respuesta = reemplazar_links(respuesta, link_reserva, "")
                    # FORZAR link SIEMPRE al final si no está presente
                    if link_reserva and link_reserva not in respuesta:
                        respuesta = f"{respuesta}\n\n{link_reserva}"
                    if self.id_chat:
                        self.chat_service.registrar_mensaje(self.id_chat, respuesta, es_cliente=False)
                    return enviar_mensaje_whatsapp(numero, respuesta)
            elif self.es_respuesta_positiva(texto_strip):
                self.set_flujo_paso(numero, "link_enviado")
                link_reserva = self.link_reserva if self.link_reserva else LINK_RESERVA
                respuesta = generar_respuesta_barberia(
                    intencion="link_agenda",
                    texto_usuario=texto_strip,
                    info_relevante="",
                    link_agenda=link_reserva,
                    link_maps="",
                    ya_hay_contexto=True,
                    chat_service=self.chat_service,
                    id_chat=self.id_chat,
                    respuesta_predefinida=None
                )
                if respuesta:
                    respuesta = reemplazar_links(respuesta, link_reserva, "")
                    # FORZAR link SIEMPRE al final si no está presente
                    if link_reserva and link_reserva not in respuesta:
                        respuesta = f"{respuesta}\n\n{link_reserva}"
                    if self.id_chat:
                        self.chat_service.registrar_mensaje(self.id_chat, respuesta, es_cliente=False)
                    return enviar_mensaje_whatsapp(numero, respuesta)
            # Si es negativa, continuar con flujo normal
        
        # Paso 4: Detectar confirmación de reserva y enviar mensaje post-reserva
        texto_lower_reserva = texto_lower
        if flujo_paso == "link_enviado" and any(palabra in texto_lower_reserva for palabra in 
            ["ya agende", "ya agendé", "reserve", "reservé", "ya reservé", "ya reserve", 
             "listo", "listo agende", "agende", "agendé", "confirmado", "ya está"]):
            self.set_flujo_paso(numero, "reserva_confirmada")
            respuesta = generar_respuesta_barberia(
                intencion="post_reserva",
                texto_usuario=texto_strip,
                info_relevante="",
                link_agenda="",
                link_maps="",
                ya_hay_contexto=True,
                chat_service=self.chat_service,
                id_chat=self.id_chat,
                respuesta_predefinida=None
            )
            if respuesta:
                if self.id_chat:
                    self.chat_service.registrar_mensaje(self.id_chat, respuesta, es_cliente=False)
                return enviar_mensaje_whatsapp(numero, respuesta)

        # ============================================
        # PRIORIDAD 1: REGLAS BÁSICAS CRÍTICAS
        # ============================================
        # Detectar cosas críticas con keywords simples (derivar, ubicación, precio básico)
        intencion_critica = detectar_intencion(texto_strip)
        
        # DETECCIÓN ESPECIAL: Si el usuario pide el link explícitamente, enviarlo con Gemini pero FORZAR link
        if self.quiere_link(texto_strip):
            link_reserva = self.link_reserva if self.link_reserva else LINK_RESERVA
            respuesta = generar_respuesta_barberia(
                intencion="link_agenda",
                texto_usuario=texto_strip,
                info_relevante="",
                link_agenda=link_reserva,
                link_maps="",
                ya_hay_contexto=True,
                chat_service=self.chat_service,
                id_chat=self.id_chat,
                respuesta_predefinida=None
            )
            if respuesta:
                respuesta = reemplazar_links(respuesta, link_reserva, "")
                # FORZAR link SIEMPRE al final si no está presente
                if link_reserva and link_reserva not in respuesta:
                    respuesta = f"{respuesta}\n\n{link_reserva}"
                if self.id_chat:
                    self.chat_service.registrar_mensaje(self.id_chat, respuesta, es_cliente=False)
                return enviar_mensaje_whatsapp(numero, respuesta)
        
        if intencion_critica == "derivar_humano":
            numero_derivacion = self.numero_derivacion if hasattr(self, 'numero_derivacion') and self.numero_derivacion else NUMERO_DERIVACION
            mensaje_derivacion = (
                f"Te voy a derivar con un asistente humano que te va a poder ayudar mejor. "
                f"En breve te contactará alguien de nuestro equipo.\n\n"
                f"Contacto: {numero_derivacion}"
            )
            if self.id_chat:
                self.chat_service.registrar_mensaje(self.id_chat, mensaje_derivacion, es_cliente=False)
            enviar_mensaje_whatsapp(numero, mensaje_derivacion)
            return {"success": True}

        # ============================================
        # PRIORIDAD 2: ESTIMAR TOKENS Y DECIDIR FLUJO
        # ============================================
        # Solo usar respuestas predefinidas con keywords directos (sin Gemini)
        respuesta_predefinida = None
        try:
            # Solo buscar con keywords directos, sin usar Gemini
            resultado_keywords = detectar_intencion_respuesta(texto_strip)
            if resultado_keywords:
                intencion_kw, clave_kw = resultado_keywords
                respuesta_predefinida = get_response(intencion_kw, clave_kw)
        except Exception as e:
            print(f"⚠️ Error en sistema de respuestas predefinidas: {e}")
            manejar_error(e, texto_strip, numero)
        
        # Si hay respuesta predefinida con keywords directos, usarla (10% de los casos)
        if respuesta_predefinida:
            link_reserva = self.link_reserva if self.link_reserva else LINK_RESERVA
            link_maps = "https://maps.app.goo.gl/uaJPmJrxUJr5wZE87"
            respuesta_final = reemplazar_links(respuesta_predefinida, link_reserva, link_maps)
            
            # Si es sobre turnos/agenda y no tiene link, agregarlo
            if ("turno" in texto_lower or "agenda" in texto_lower or "reserva" in texto_lower) and link_reserva:
                if link_reserva not in respuesta_final:
                    respuesta_final += f"\n\n{link_reserva}"
            
            if self.id_chat:
                self.chat_service.registrar_mensaje(self.id_chat, respuesta_final, es_cliente=False)
            return enviar_mensaje_whatsapp(numero, respuesta_final)
        
        # Preparar datos para estimar tokens
        info_relevante = ""
        if intencion_critica:
            info_relevante = get_info_por_intencion(intencion_critica)
        
        ya_hay_contexto = self.ya_se_saludo(numero) or intencion_critica
        
        # Obtener historial cuando hay contexto de conversación
        historial_comprimido = ""
        ultimos_mensajes = None
        if ya_hay_contexto and self.chat_service and self.id_chat:
            try:
                # Siempre obtener últimos mensajes para contextualización (al menos los últimos 3-4)
                ultimos_mensajes = self.chat_service.obtener_ultimos_mensajes(self.id_chat, limite=4)
                
                # Si hay muchos mensajes, también obtener historial comprimido como contexto adicional
                todos_mensajes = self.chat_service.obtener_todos_mensajes(self.id_chat)
                if todos_mensajes and len(todos_mensajes) > 10:
                    historial_comprimido = compress_history(todos_mensajes)
                    print(f"📚 Usando historial comprimido + últimos mensajes ({len(todos_mensajes)} mensajes totales)")
                else:
                    print(f"📝 Usando últimos mensajes ({len(ultimos_mensajes) if ultimos_mensajes else 0} mensajes)")
            except Exception as e:
                print(f"⚠️ Error obteniendo historial: {e}")
        
        # Estimar tokens del prompt que se construiría
        prompt_estimado = build_modular_prompt(
            intencion=intencion_critica if intencion_critica else "",
            texto_usuario=texto_strip,
            info_relevante=info_relevante,
            historial_comprimido=historial_comprimido,
            ultimos_mensajes=ultimos_mensajes,
            ya_hay_contexto=ya_hay_contexto
        )
        tokens_estimados = count_tokens(prompt_estimado, use_api=False)
        print(f"📊 Tokens estimados: {tokens_estimados}")
        
        # ============================================
        # PRIORIDAD 3: GEMINI (90% de los casos si tokens <= 500)
        # ============================================
        try:
            link_reserva = self.link_reserva if self.link_reserva else LINK_RESERVA
            link_maps = "https://maps.app.goo.gl/uaJPmJrxUJr5wZE87"
            
            # Si tokens <= 500, usar Gemini directamente (90% de los casos)
            if tokens_estimados <= 500:
                print(f"✅ Tokens <= 500, usando Gemini directamente")
                respuesta = generar_respuesta_barberia(
                    intencion_critica if intencion_critica else "", 
                    texto_strip, 
                    info_relevante,
                    link_reserva,
                    link_maps,
                    ya_hay_contexto,
                    self.chat_service,
                    self.id_chat,
                    respuesta_predefinida=None
                )
            else:
                # Si tokens > 500, intentar flujo automático primero
                print(f"⚠️ Tokens > 500, intentando flujo automático primero...")
                from Util.flujo_automatico import procesar_flujo_automatico
                respuesta_automatica = procesar_flujo_automatico(
                    texto_usuario=texto_strip,
                    intencion=intencion_critica if intencion_critica else "",
                    info_relevante=info_relevante
                )
                
                if respuesta_automatica:
                    print(f"✅ Flujo automático exitoso, evitando Gemini")
                    respuesta = respuesta_automatica
                else:
                    # Si no encuentra nada, usar Gemini de todas formas
                    print(f"⚠️ Flujo automático no encontró respuesta, usando Gemini")
                    respuesta = generar_respuesta_barberia(
                        intencion_critica if intencion_critica else "", 
                        texto_strip, 
                        info_relevante,
                        link_reserva,
                        link_maps,
                        ya_hay_contexto,
                        self.chat_service,
                        self.id_chat,
                        respuesta_predefinida=None
                    )
            
            # Reemplazar links en la respuesta final
            respuesta_final = reemplazar_links(respuesta, link_reserva, link_maps)
            
            # FORZAR link si:
            # 1. La intención es "turnos" o "link_agenda"
            # 2. El usuario preguntó por turnos/agenda/reserva
            # 3. Se menciona link/agenda pero no está presente
            import re
            menciona_link_o_agenda = re.search(
                r"(link|agenda|reserva|turno).*(?:te paso|te dejo|te mando|ahí|ahi)",
                respuesta_final,
                re.IGNORECASE
            )
            
            debe_incluir_link = False
            if intencion_critica and intencion_critica.lower() in ["turnos", "link_agenda"]:
                debe_incluir_link = True
            elif "turno" in texto_lower or "agenda" in texto_lower or "reserva" in texto_lower:
                debe_incluir_link = True
            elif menciona_link_o_agenda:
                debe_incluir_link = True
            
            if debe_incluir_link and link_reserva and link_reserva not in respuesta_final:
                respuesta_final += f"\n\n{link_reserva}"
            
            if self.id_chat:
                self.chat_service.registrar_mensaje(self.id_chat, respuesta_final, es_cliente=False)
            
            return enviar_mensaje_whatsapp(numero, respuesta_final)
            
        except Exception as e:
            print(f"⚠️ Error al generar respuesta con Gemini: {e}")
            manejar_error(e, texto_strip, numero)
            # Fallback: usar mensaje por defecto
            mensaje_default = "Disculpá, estoy teniendo problemas técnicos. ¿Querés que te derive con alguien del equipo?"
            if self.id_chat:
                self.chat_service.registrar_mensaje(self.id_chat, mensaje_default, es_cliente=False)
            return enviar_mensaje_whatsapp(numero, mensaje_default)

        # ============================================
        # MENSAJE POR DEFECTO (si todo lo anterior falla)
        # ============================================
        # Solo usar mensaje genérico si no hay contexto de conversación
        ya_hay_contexto = self.ya_se_saludo(numero) or intencion_critica
        if ya_hay_contexto:
            # Si ya hay contexto, no usar saludo genérico
            mensaje_default = "Escribime lo que necesites o escribí *ayuda* para ver las opciones."
        else:
            mensaje_default = "¡Bro! ¿Todo bien?\n\nEscribime lo que necesites o escribí *ayuda* para ver las opciones."
        
        if self.id_chat:
            self.chat_service.registrar_mensaje(self.id_chat, mensaje_default, es_cliente=False)
        return enviar_mensaje_whatsapp(numero, mensaje_default)

        # ============================================
        # FLUJO ANTIGUO DE AGENDAMIENTO (COMENTADO PARA REFERENCIA)
        # ============================================
        # # Verificar si hay un waiting_for activo
        # estado = get_estado(numero)
        # waiting_for = estado.get("waiting_for")
        # 
        # if waiting_for and waiting_for in self.function_map:
        #     return self.function_map[waiting_for](numero, texto_lower)
        # 
        # # Intentar extraer día y hora del mensaje si no hay waiting_for
        # dia_encontrado, hora_encontrada = self.extraer_dia_y_hora(texto_strip)
        # 
        # if dia_encontrado or hora_encontrada:
        #     # Si encontró día u hora, guardar en contexto y continuar flujo
        #     context_data = estado.get("context_data", {})
        #     if dia_encontrado:
        #         context_data["dia"] = dia_encontrado
        #     if hora_encontrada:
        #         context_data["hora"] = hora_encontrada
        #     estado["context_data"] = context_data
        #     
        #     # Verificar qué información ya tiene el usuario
        #     tiene_nombre = context_data.get("nombre")
        #     tiene_servicio = context_data.get("servicio")
        #     
        #     if not tiene_nombre:
        #         # No tiene nombre, iniciar flujo normal pero con día/hora ya guardados
        #         mensaje_bienvenida = "👋 hola soy la demo asistente "
        #         if dia_encontrado and hora_encontrada:
        #             mensaje_bienvenida += f"anoté {dia_encontrado.capitalize()} a las {hora_encontrada}. "
        #         elif dia_encontrado:
        #             mensaje_bienvenida += f"anoté {dia_encontrado.capitalize()}. "
        #         elif hora_encontrada:
        #             mensaje_bienvenida += f"anoté la hora {hora_encontrada}. "
        #         
        #         mensaje_bienvenida += "decime tu nombre y apellido para iniciar la agenda"
        #         
        #         estado["state"] = "solicitando_nombre_completo"
        #         self.set_waiting_for(numero, "flujo_nombre_completo")
        #         
        #         if self.id_chat:
        #             self.chat_service.registrar_mensaje(self.id_chat, mensaje_bienvenida, es_cliente=False)
        #         
        #         return enviar_mensaje_whatsapp(numero, mensaje_bienvenida)
        #     elif not tiene_servicio:
        #         # Tiene nombre pero no servicio
        #         estado["state"] = "solicitando_servicio"
        #         self.set_waiting_for(numero, "flujo_servicio")
        #         mensaje = "¿Qué servicio querés reservar?\n\nEscribí:\n• *Corte de pelo*\n• *Barba*\n• *Corte + Barba*"
        #         return enviar_mensaje_whatsapp(numero, mensaje)
        #     elif dia_encontrado and hora_encontrada:
        #         # Tiene todo, mostrar resumen directamente
        #         return self.mostrar_resumen_directo(numero, context_data)
        #     elif dia_encontrado:
        #         # Tiene día pero falta hora
        #         estado["state"] = "solicitando_dia_hora"
        #         self.set_waiting_for(numero, "flujo_dia_hora")
        #         mensaje = f"✅ {dia_encontrado.capitalize()} anotado 📅\n\n¿A qué hora querés reservar?\n\nEscribí la hora (ejemplo: 14:30)"
        #         return enviar_mensaje_whatsapp(numero, mensaje)
        #     elif hora_encontrada:
        #         # Tiene hora pero falta día
        #         estado["state"] = "solicitando_dia_hora"
        #         self.set_waiting_for(numero, "flujo_dia_hora")
        #         mensaje = f"✅ Hora {hora_encontrada} anotada 🕐\n\n¿Para qué día querés reservar?\n\nEscribí el día y la hora juntos (ejemplo: jueves {hora_encontrada})"
        #         return enviar_mensaje_whatsapp(numero, mensaje)
        # 
        # # Si no hay waiting_for, iniciar flujo de agendamiento
        # return self.flujo_inicio(numero, texto_lower)

    def _registrar_y_enviar_mensaje(self, numero, mensaje):
        if self.id_chat:
            self.chat_service.registrar_mensaje(self.id_chat, mensaje, es_cliente=False)
        return enviar_mensaje_whatsapp(numero, mensaje)

    # ============================================
    # FUNCIONES DEL FLUJO ANTIGUO (COMENTADAS PARA REFERENCIA)
    # ============================================
    
    # def extraer_dia_y_hora(self, texto):
    #     """Extrae día de la semana y hora del mensaje si están presentes."""
    #     texto_lower = texto.lower()
    #     dia_encontrado = None
    #     hora_encontrada = None
    #     
    #     # Buscar días de la semana
    #     dias_map = {
    #         "lunes": "lunes",
    #         "martes": "martes",
    #         "miercoles": "miércoles",
    #         "miércoles": "miércoles",
    #         "jueves": "jueves",
    #         "viernes": "viernes",
    #         "sabado": "sábado",
    #         "sábado": "sábado",
    #         "domingo": "domingo"
    #     }
    #     
    #     for dia_key, dia_valor in dias_map.items():
    #         if dia_key in texto_lower:
    #             dia_encontrado = dia_valor
    #             break
    #     
    #     # Buscar hora en formato HH:MM o HH MM
    #     # Patrón para hora: HH:MM, HH.MM, HH MM, o "a las HH:MM", "las HH"
    #     patrones_hora = [
    #         r'\b(\d{1,2}):(\d{2})\b',  # 14:30, 9:00
    #         r'\b(\d{1,2})\.(\d{2})\b',  # 14.30
    #         r'\b(\d{1,2})\s+(\d{2})\b',  # 14 30
    #         r'a\s+las\s+(\d{1,2}):?(\d{2})?',  # a las 14:30, a las 14
    #         r'las\s+(\d{1,2}):?(\d{2})?',  # las 14:30, las 14
    #     ]
    #     
    #     for patron in patrones_hora:
    #         match = re.search(patron, texto_lower)
    #         if match:
    #             horas = int(match.group(1))
    #             minutos = int(match.group(2)) if match.group(2) else 0
    #             
    #             if 0 <= horas <= 23 and 0 <= minutos <= 59:
    #                 hora_encontrada = f"{horas:02d}:{minutos:02d}"
    #                 break
    #     
    #     return dia_encontrado, hora_encontrada

    #     # def flujo_inicio(self, numero, mensaje):
    #     """Inicia el flujo de agendamiento de citas solicitando el nombre completo."""
    #     estado = get_estado(numero)
    #     estado["state"] = "solicitando_nombre_completo"
    #     self.set_waiting_for(numero, "flujo_nombre_completo")
    #     
    #     mensaje_bienvenida = (
    #         "👋 hola soy la demo asistente decime tu nombre y apellido para iniciar la agenda"
    #     )
    #     
    #     if self.id_chat:
    #         self.chat_service.registrar_mensaje(self.id_chat, mensaje_bienvenida, es_cliente=False)
    #     
    #     return enviar_mensaje_whatsapp(numero, mensaje_bienvenida)

    # def flujo_inicio_con_dia_hora(self, numero, mensaje, dia_encontrado, hora_encontrada):
    #     """Inicia el flujo cuando ya se detectó día u hora en el mensaje."""
    #     estado = get_estado(numero)
    #     estado["state"] = "solicitando_nombre_completo"
    #     self.set_waiting_for(numero, "flujo_nombre_completo")
    #     
    #     mensaje_bienvenida = (
    #         "👋 ¡Hola! Soy el asistente de la barbería 💈\n\n"
    #         "¿Me decís tu nombre y apellido? "
    #     )
    #     
    #     if self.id_chat:
    #         self.chat_service.registrar_mensaje(self.id_chat, mensaje_bienvenida, es_cliente=False)
    #     
    #     return enviar_mensaje_whatsapp(numero, mensaje_bienvenida)

    # def mostrar_resumen_directo(self, numero, context_data):
    #     """Muestra el resumen directamente cuando ya se tiene toda la información."""
    #     nombre = context_data.get("nombre", "")
    #     apellido = context_data.get("apellido", "")
    #     servicio = context_data.get("servicio", "")
    #     dia = context_data.get("dia", "")
    #     hora = context_data.get("hora", "")
    #     
    #     if not all([nombre, apellido, servicio, dia, hora]):
    #         # Faltan datos, continuar flujo normal
    #         return self.flujo_inicio(numero, "")
    #     
    #     estado = get_estado(numero)
    #     estado["state"] = "confirmando_cita"
    #     self.set_waiting_for(numero, "flujo_confirmacion_cita")
    #     
    #     mensaje_resumen = (
    #         "📋 *Resumen de tu turno:*\n\n"
    #         f"👤 *{nombre} {apellido}*\n"
    #         f"💈 *{servicio}*\n"
    #         f"📅 *{dia.capitalize()}*\n"
    #         f"🕐 *{hora}*\n\n"
    #         "¿Confirmás? (escribí *confirmar* o *si* para confirmar, *cancelar* para cancelar)"
    #     )
    #     
    #     if self.id_chat:
    #         self.chat_service.registrar_mensaje(self.id_chat, mensaje_resumen, es_cliente=False)
    #     
    #     return enviar_mensaje_whatsapp(numero, mensaje_resumen)

    #     # def flujo_nombre_completo(self, numero, mensaje):
    #     """Captura el nombre completo y solicita el servicio."""
    #     nombre_completo = mensaje.strip()
    #     
    #     if not nombre_completo or len(nombre_completo) < 3:
    #         return enviar_mensaje_whatsapp(numero, "😅 Me parece muy corto. ¿Podrías escribir tu nombre completo?")
    #     
    #     # Separar nombre y apellido (tomar primera palabra como nombre, resto como apellido)
    #     partes = nombre_completo.split()
    #     if len(partes) < 2:
    #         return enviar_mensaje_whatsapp(numero, "😅 Necesito tu nombre y apellido. ¿Me los podés escribir juntos?")
    #     
    #     nombre = partes[0]
    #     apellido = " ".join(partes[1:])
    #     
    #     estado = get_estado(numero)
    #     estado["state"] = "solicitando_servicio"
    #     # Asegurar que context_data existe y actualizar correctamente
    #     if "context_data" not in estado:
    #         estado["context_data"] = {}
    #     estado["context_data"]["nombre"] = nombre
    #     estado["context_data"]["apellido"] = apellido
    #     self.set_waiting_for(numero, "flujo_servicio")
    #     
    #     mensaje_respuesta = (
    #         f"¡Perfecto, {nombre}! 👌\n\n"
    #         f"¿Qué servicio querés reservar?\n\n"
    #         "Escribí:\n"
    #         "• *Corte de pelo*\n"
    #         "• *Barba*\n"
    #         "• *Corte + Barba*"
    #     )
    #     
    #     if self.id_chat:
    #         self.chat_service.registrar_mensaje(self.id_chat, mensaje_respuesta, es_cliente=False)
    #     
    #     return enviar_mensaje_whatsapp(numero, mensaje_respuesta)

    # def flujo_servicio(self, numero, mensaje):
    #     """Captura el servicio y solicita el día de la semana."""
    #     servicio_texto = mensaje.strip().lower()
    #     
    #     # Normalizar servicio
    #     servicios_map = {
    #         "corte de pelo": "Corte de pelo",
    #         "corte": "Corte de pelo",
    #         "pelo": "Corte de pelo",
    #         "barba": "Barba",
    #         "corte + barba": "Corte + Barba",
    #         "corte y barba": "Corte + Barba",
    #         "corte+barba": "Corte + Barba",
    #         "ambos": "Corte + Barba",
    #         "los dos": "Corte + Barba"
    #     }
    #     
    #     servicio = servicios_map.get(servicio_texto)
    #     
    #     if not servicio:
    #         return enviar_mensaje_whatsapp(
    #             numero,
    #             "😅 No entendí bien. Escribí una de estas opciones:\n\n"
    #             "• *Corte de pelo*\n"
    #             "• *Barba*\n"
    #             "• *Corte + Barba*"
    #         )
    #     
    #     estado = get_estado(numero)
    #     # Asegurar que context_data existe y actualizar correctamente
    #     if "context_data" not in estado:
    #         estado["context_data"] = {}
    #     estado["context_data"]["servicio"] = servicio
    #     
    #     # Verificar si ya tiene día y hora guardados (del mensaje inicial)
    #     context_data = estado.get("context_data", {})
    #     dia = context_data.get("dia", "")
    #     hora = context_data.get("hora", "")
    #     
    #     # Si ya tiene día y hora, mostrar resumen directamente
    #     if dia and hora:
    #         estado["state"] = "confirmando_cita"
    #         self.set_waiting_for(numero, "flujo_confirmacion_cita")
    #         
    #         nombre = context_data.get("nombre", "")
    #         apellido = context_data.get("apellido", "")
    #         
    #         # Normalizar día
    #         if dia == "miercoles":
    #             dia = "miércoles"
    #         elif dia == "sabado":
    #             dia = "sábado"
    #         context_data["dia"] = dia
    #         estado["context_data"] = context_data
    #         
    #         mensaje_resumen = (
    #             "📋 *Resumen de tu turno:*\n\n"
    #             f"👤 *{nombre} {apellido}*\n"
    #             f"💈 *{servicio}*\n"
    #             f"📅 *{dia.capitalize()}*\n"
    #             f"🕐 *{hora}*\n\n"
    #             "¿Confirmás? (escribí *confirmar* o *si* para confirmar, *cancelar* para cancelar)"
    #         )
    #         
    #         if self.id_chat:
    #             self.chat_service.registrar_mensaje(self.id_chat, mensaje_resumen, es_cliente=False)
    #         
    #         return enviar_mensaje_whatsapp(numero, mensaje_resumen)
    #     
    #     # Si no tiene día y hora, pedirlos
    #     estado["state"] = "solicitando_dia_hora"
    #     self.set_waiting_for(numero, "flujo_dia_hora")
    #     
    #     mensaje_respuesta = (
    #         f"✅ Perfecto, {servicio} 💈\n\n"
    #         "¿Para qué día y hora querés reservar?\n\n"
    #         "Escribí el día y la hora (ejemplo: jueves 14:30)"
    #     )
    #     
    #     if self.id_chat:
    #         self.chat_service.registrar_mensaje(self.id_chat, mensaje_respuesta, es_cliente=False)
    #     
    #     return enviar_mensaje_whatsapp(numero, mensaje_respuesta)

    # def flujo_dia_hora(self, numero, mensaje):
    #     """Captura el día y hora juntos y muestra resumen para confirmar."""
    #     texto_strip = mensaje.strip()
    #     
    #     # Intentar extraer día y hora del mensaje
    #     dia_encontrado, hora_encontrada = self.extraer_dia_y_hora(texto_strip)
    #     
    #     estado = get_estado(numero)
    #     context_data = estado.get("context_data", {})
    #     
    #     # Si se encontró día, guardarlo
    #     if dia_encontrado:
    #         context_data["dia"] = dia_encontrado
    #         estado["context_data"] = context_data
    #     
    #     # Si se encontró hora, validarla y guardarla
    #     if hora_encontrada:
    #         context_data["hora"] = hora_encontrada
    #         estado["context_data"] = context_data
    #     else:
    #         # Intentar extraer hora del mensaje si no se detectó automáticamente
    #         hora = texto_strip
    #         try:
    #             partes = hora.split(":")
    #             if len(partes) == 2:
    #                 horas = int(partes[0])
    #                 minutos = int(partes[1])
    #                 if 0 <= horas <= 23 and 0 <= minutos <= 59:
    #                     hora_encontrada = f"{horas:02d}:{minutos:02d}"
    #                     context_data["hora"] = hora_encontrada
    #                     estado["context_data"] = context_data
    #         except (ValueError, IndexError):
    #             pass
    #     
    #     # Verificar qué falta
    #     dia = context_data.get("dia", "")
    #     hora = context_data.get("hora", "")
    #     
    #     # Si falta día
    #     if not dia:
    #         dias_validos = ["lunes", "martes", "miércoles", "miercoles", "jueves", "viernes", "sábado", "sabado", "domingo"]
    #         # Intentar extraer día del mensaje
    #         texto_lower = texto_strip.lower()
    #         for dia_key in ["lunes", "martes", "miercoles", "miércoles", "jueves", "viernes", "sabado", "sábado", "domingo"]:
    #             if dia_key in texto_lower:
    #                 if dia_key == "miercoles":
    #                     dia = "miércoles"
    #                 elif dia_key == "sabado":
    #                     dia = "sábado"
    #                 else:
    #                     dia = dia_key
    #                 context_data["dia"] = dia
    #                 estado["context_data"] = context_data
    #                 break
    #         
    #         if not dia:
    #             return enviar_mensaje_whatsapp(
    #                 numero,
    #                 "😅 No encontré el día. Escribí el día y la hora juntos:\n"
    #                 "Ejemplo: jueves 14:30 o lunes 09:00"
    #             )
    #     
    #     # Si falta hora
    #     if not hora:
    #         return enviar_mensaje_whatsapp(
    #             numero,
    #             "😅 No encontré la hora. Escribí el día y la hora juntos:\n"
    #             "Ejemplo: jueves 14:30 o lunes 09:00"
    #         )
    #     
    #     # Validar formato de hora
    #     try:
    #         partes = hora.split(":")
    #         if len(partes) != 2:
    #             raise ValueError
    #         
    #         horas_int = int(partes[0])
    #         minutos_int = int(partes[1])
    #         
    #         if not (0 <= horas_int <= 23) or not (0 <= minutos_int <= 59):
    #             raise ValueError
    #         
    #         # Formatear hora con ceros a la izquierda si es necesario
    #         hora_formateada = f"{horas_int:02d}:{minutos_int:02d}"
    #     except (ValueError, IndexError):
    #         return enviar_mensaje_whatsapp(
    #             numero,
    #             "😅 La hora no es válida. Escribí el día y la hora juntos:\n"
    #             "Ejemplo: jueves 14:30 o lunes 09:00"
    #         )
    #     
    #     # Actualizar hora formateada
    #     context_data["hora"] = hora_formateada
    #     estado["context_data"] = context_data
    #     
    #     # Obtener datos para el resumen
    #     nombre = context_data.get("nombre", "")
    #     apellido = context_data.get("apellido", "")
    #     servicio = context_data.get("servicio", "")
    #     
    #     # Normalizar día y guardarlo
    #     if dia == "miercoles":
    #         dia = "miércoles"
    #     elif dia == "sabado":
    #         dia = "sábado"
    #     
    #     # Guardar día normalizado en context_data
    #     context_data["dia"] = dia
    #     estado["context_data"] = context_data
    #     
    #     estado["state"] = "confirmando_cita"
    #     self.set_waiting_for(numero, "flujo_confirmacion_cita")
    #     
    #     mensaje_resumen = (
    #         "📋 *Resumen de tu turno:*\n\n"
    #         f"👤 *{nombre} {apellido}*\n"
    #         f"💈 *{servicio}*\n"
    #         f"📅 *{dia.capitalize()}*\n"
    #         f"🕐 *{hora_formateada}*\n\n"
    #         "¿Confirmás? (escribí *confirmar* o *si* para confirmar, *cancelar* para cancelar)"
    #     )
    #     
    #     if self.id_chat:
    #         self.chat_service.registrar_mensaje(self.id_chat, mensaje_resumen, es_cliente=False)
    #     
    #     return enviar_mensaje_whatsapp(numero, mensaje_resumen)

    # def flujo_confirmacion_cita(self, numero, mensaje):
    #     """Confirma y guarda la cita en memoria."""
    #     texto_lower = mensaje.strip().lower()
    #     
    #     if texto_lower not in ("confirmar", "si", "sí", "confirmo", "ok"):
    #         if texto_lower in ("cancelar", "no", "salir"):
    #             self.clear_state(numero)
    #             return enviar_mensaje_whatsapp(numero, "❌ Turno cancelado. Escribí cualquier mensaje para comenzar de nuevo.")
    #         else:
    #             return enviar_mensaje_whatsapp(
    #                 numero,
    #                 "😅 Escribí *confirmar* o *si* para confirmar, o *cancelar* para cancelar."
    #             )
    #     
    #     estado = get_estado(numero)
    #     context_data = estado.get("context_data", {})
    #     
    #     nombre = context_data.get("nombre", "")
    #     apellido = context_data.get("apellido", "")
    #     servicio = context_data.get("servicio", "")
    #     dia = context_data.get("dia", "")
    #     hora = context_data.get("hora", "")
    #     
    #     if not all([nombre, apellido, servicio, dia, hora]):
    #         return enviar_mensaje_whatsapp(numero, "⚠️ Error: Faltan datos del turno. Por favor, comienza de nuevo.")
    #     
    #     # Validar si el horario ya está ocupado
    #     citas_existentes = get_citas(numero)
    #     for cita_existente in citas_existentes:
    #         if cita_existente.get("dia") == dia and cita_existente.get("hora") == hora:
    #             return enviar_mensaje_whatsapp(
    #                 numero,
    #                 f"⛔ Esa hora ya está ocupada ({dia.capitalize()} {hora}).\n\n"
    #                 "Por favor elegí otra hora."
    #             )
    #     
    #     # Guardar cita en memoria
    #     cita = {
    #         "nombre": nombre,
    #         "apellido": apellido,
    #         "servicio": servicio,
    #         "dia": dia,
    #         "hora": hora
    #     }
    #     
    #     add_cita(numero, cita)
    #     
    #     # Limpiar estado
    #     self.clear_state(numero)
    #     
    #     mensaje_confirmacion = (
    #         "✅ *¡Turno confirmado!* 🎉\n\n"
    #         f"👤 *{nombre} {apellido}*\n"
    #         f"💈 *{servicio}*\n"
    #         f"📅 *{dia.capitalize()}*\n"
    #         f"🕐 *{hora}*\n\n"
    #         "¡Te esperamos en la barbería! 💈\n\n"
    #         "Escribí cualquier mensaje para agendar otro turno."
    #     )
    #     
    #     if self.id_chat:
    #         self.chat_service.registrar_mensaje(self.id_chat, mensaje_confirmacion, es_cliente=False)
    #     
    #     return enviar_mensaje_whatsapp(numero, mensaje_confirmacion)


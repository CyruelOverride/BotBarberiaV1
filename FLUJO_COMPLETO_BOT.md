# Flujo Completo del Bot de Barbería - Documentación Técnica

## 📋 Resumen Ejecutivo

Este documento explica paso a paso cómo funciona el bot cuando llega un mensaje de WhatsApp, qué archivo se ejecuta, qué función llama a qué, y en qué orden.

---

## 🔄 Flujo Principal: De WhatsApp al Bot

### 1️⃣ **ENTRADA: WhatsApp Webhook**
**Archivo:** `webhook_server.py`  
**Función:** `receive()` (línea 116)

**¿Qué hace?**
- Recibe el POST de WhatsApp cuando llega un mensaje
- Extrae el JSON del request
- Llama a `procesar_mensaje_recibido()` de `whatsapp_api.py`

**Código clave:**
```python
@app.post("/webhook")
async def receive(request: Request):
    data = await request.json()
    resultado = procesar_mensaje_recibido(data)  # → whatsapp_api.py
```

---

### 2️⃣ **PROCESAMIENTO INICIAL DEL MENSAJE**
**Archivo:** `whatsapp_api.py`  
**Función:** `procesar_mensaje_recibido()` (línea 121)

**¿Qué hace?**
- Valida que el mensaje sea de WhatsApp Business
- Extrae el número del remitente
- Llama a `get_type()` de `Util/get_type.py` para determinar el tipo de mensaje
- Si es audio, lo transcribe usando `get_transcription()` de `Util/audio_util.py`
- Retorna: `(numero, contenido, tipo)`

**Flujo:**
```
procesar_mensaje_recibido()
  ├─→ get_type() → Util/get_type.py
  │   ├─→ Si es audio: get_transcription() → Util/audio_util.py
  │   └─→ Retorna (tipo, contenido)
  └─→ Retorna (numero, contenido, tipo)
```

**Código clave:**
```python
tipo, contenido = get_type(message)  # → Util/get_type.py
if tipo == "audio":
    tipo = "text"  # Se convierte a texto después de transcribir
return numero, contenido, tipo
```

---

### 3️⃣ **CREACIÓN DE SERVICIOS Y CHAT**
**Archivo:** `webhook_server.py`  
**Función:** `receive()` (línea 129-147)

**¿Qué hace?**
- Crea sesión de base de datos
- Crea `ChatService` y `ClienteService`
- Obtiene o crea el cliente en BD
- Obtiene o crea el chat en BD
- Registra el mensaje del cliente en BD
- Crea instancia de `Chat` (clase principal)
- Llama a `chat.handle_text()` o `chat.handle_text()` según el tipo

**Código clave:**
```python
chat_service = ChatService(db_session)
id_cliente = ClienteService.obtener_o_crear_cliente("", "", numero)
chat_bd = chat_service.obtener_o_crear_chat(id_cliente, numero)
chat_service.registrar_mensaje(id_chat, mensaje, es_cliente=True)

chat = Chat(id_chat=id_chat, id_cliente=id_cliente, chat_service=chat_service)
chat.handle_text(numero, mensaje)  # → Models/chat.py
```

---

## 🧠 PROCESAMIENTO DEL MENSAJE: `handle_text()`

**Archivo:** `Models/chat.py`  
**Función:** `handle_text()` (línea 270)

Este es el **corazón del bot**. Aquí se decide qué hacer con cada mensaje.

### **PRIORIDAD 0: Comandos Especiales y Flujo Secuencial**

#### A. Comandos Especiales (línea 281-289)
- **"cancelar", "salir", "cancel"**: Limpia estado y cancela operación
- **"ayuda"**: Llama a `funcion_ayuda()` (definida en la misma clase)

#### B. Flujo Secuencial de Bienvenida (línea 291-418)

**Paso 1: Saludo Inicial** (línea 295-311)
- Detecta si es saludo con `es_saludo()`
- Si es el primer saludo, llama a `generar_respuesta_barberia()` con intención "saludo_inicial"
- **Archivo llamado:** `Util/procesar_texto_gemini.py`

**Paso 2-4: Flujo de Agendamiento** (línea 313-418)
- Detecta si el usuario quiere el link de agenda
- Detecta respuestas positivas para agendar
- Detecta confirmación de reserva
- Usa `generar_respuesta_barberia()` con diferentes intenciones

---

### **PRIORIDAD 1: Reglas Básicas Críticas** (línea 420-469)

#### A. Detección de Aviso de Demora (línea 452-457)
**Archivo:** `Util/politicas_respuestas.py`  
**Función:** `procesar_aviso_demora()`

**Flujo interno:**
```
procesar_aviso_demora()
  ├─→ detectar_aviso_demora()  # Detecta keywords
  ├─→ normalizar_datos_demora()  # Extrae datos con Gemini
  ├─→ evaluar_demora()  # Política determinística
  └─→ Retorna mensaje según estado
```

#### B. Detección de Intención Crítica (línea 460)
**Archivo:** `Util/intents.py`  
**Función:** `detectar_intencion()`

**¿Qué hace?**
- Busca keywords en el texto
- Retorna intención detectada (ej: "precios", "turnos", "barba")

#### C. Derivación a Humano (línea 462-469)
- Si detecta intención "derivar_humano", envía mensaje de derivación

---

### **PRIORIDAD 2: Respuestas Predefinidas** (línea 471-522)

**Archivo:** `Util/respuestas_barberia.py`  
**Función:** `detectar_intencion_respuesta()` (línea 96)

**¿Qué hace?**
- Busca keywords más específicos que `detectar_intencion()`
- Retorna `(intencion, clave)` si encuentra match
- Llama a `get_response()` para obtener respuesta del JSON
- **Archivo JSON:** `Util/respuestas_barberia.json`

**Si encuentra respuesta predefinida:**
- Reemplaza links con `reemplazar_links()`
- Agrega link de agenda si es necesario
- Envía mensaje con delay

---

### **PRIORIDAD 3: Preparación para Gemini** (línea 524-560)

#### A. Obtener Información Relevante (línea 525-528)
**Archivo:** `Util/informacion_barberia.py`  
**Función:** `get_info_por_intencion()`

**¿Qué hace?**
- Según la intención detectada, obtiene información relevante
- Si es "precios", llama a `get_info_precios()` que usa `Util/precios_barberia.py`
- Retorna string con información para incluir en el prompt

**Flujo para precios:**
```
get_info_por_intencion("precios", texto_usuario)
  └─→ get_info_precios(texto_usuario)
      └─→ obtener_info_precios_para_prompt(texto_usuario)  # Util/precios_barberia.py
          ├─→ obtener_precio_por_nombre()  # Si menciona servicio específico
          └─→ obtener_lista_completa_precios()  # Si no
```

#### B. Obtener Historial (línea 532-548)
**Archivo:** `Models/chat.py`  
**Funciones:**
- `chat_service.obtener_ultimos_mensajes()` - Últimos 4 mensajes
- `chat_service.obtener_todos_mensajes()` - Todos los mensajes
- `compress_history()` de `Util/token_optimizer.py` - Comprime historial

#### C. Construir Prompt (línea 551-559)
**Archivo:** `Util/token_optimizer.py`  
**Función:** `build_modular_prompt()`

**¿Qué hace?**
- Construye el prompt optimizado para Gemini
- Incluye: instrucciones de tono, intención, texto usuario, info relevante, historial
- Estima tokens con `count_tokens()`

---

### **PRIORIDAD 4: Generación de Respuesta con Gemini** (línea 562-641)

#### A. Decisión: Gemini Directo vs Flujo Automático (línea 569-609)

**Si tokens <= 500:**
- Llama directamente a `generar_respuesta_barberia()`

**Si tokens > 500:**
- Primero intenta `procesar_flujo_automatico()` de `Util/flujo_automatico.py`
- Si no encuentra respuesta, usa `generar_respuesta_barberia()`

#### B. Generar Respuesta con Gemini
**Archivo:** `Util/procesar_texto_gemini.py`  
**Función:** `generar_respuesta_barberia()` (línea ~150)

**Flujo interno:**
```
generar_respuesta_barberia()
  ├─→ build_modular_prompt()  # Construye prompt optimizado
  ├─→ validate_and_compress()  # Valida y comprime si es necesario
  ├─→ client.models.generate_content()  # Llama a Gemini API
  ├─→ Limpia respuesta (remueve markdown)
  ├─→ reemplazar_links()  # Reemplaza placeholders de links
  └─→ Retorna respuesta o None si hay error
```

**Si hay error:**
- Llama a `manejar_error()` de `Util/error_handler.py`
- Retorna `None` (no envía mensaje al cliente, solo notifica al equipo)

#### C. Post-procesamiento (línea 616-639)
- Reemplaza links con `reemplazar_links()`
- Fuerza link de agenda si es necesario
- Envía mensaje con `_registrar_y_enviar_mensaje()`

---

### **PRIORIDAD 5: Fallbacks** (línea 643-674)

Si hay error en Gemini:
1. **Fallback 1:** Intenta `procesar_flujo_automatico()` de `Util/flujo_automatico.py`
2. **Fallback 2:** Si falla, no envía nada (solo notifica al equipo)

---

### **PRIORIDAD 6: Mensaje por Defecto** (línea 676-687)

Si todo lo anterior falla:
- Envía mensaje genérico según si hay contexto o no

---

## 📤 ENVÍO DE MENSAJE

**Archivo:** `Models/chat.py`  
**Función:** `_registrar_y_enviar_mensaje()` (línea 759)

**¿Qué hace?**
1. Aplica delay de 30-60 segundos (aleatorio)
2. Registra mensaje en BD con `chat_service.registrar_mensaje()`
3. Llama a `enviar_mensaje_whatsapp()` de `whatsapp_api.py`

**Archivo final:** `whatsapp_api.py`  
**Función:** `enviar_mensaje_whatsapp()` (línea 18)

**¿Qué hace?**
- Hace POST a la API de WhatsApp
- Envía el mensaje al usuario
- Retorna resultado del envío

---

## 📊 Diagrama de Flujo Completo

```
WhatsApp → webhook_server.py/receive()
  │
  ├─→ whatsapp_api.py/procesar_mensaje_recibido()
  │   └─→ Util/get_type.py/get_type()
  │       └─→ [Si es audio] Util/audio_util.py/get_transcription()
  │
  ├─→ Services/ChatService.py (crear/obtener chat)
  ├─→ Services/ClienteService.py (crear/obtener cliente)
  │
  └─→ Models/chat.py/handle_text()
      │
      ├─→ [PRIORIDAD 0] Comandos especiales / Flujo secuencial
      │   └─→ Util/procesar_texto_gemini.py/generar_respuesta_barberia()
      │
      ├─→ [PRIORIDAD 1] Reglas críticas
      │   ├─→ Util/politicas_respuestas.py/procesar_aviso_demora()
      │   └─→ Util/intents.py/detectar_intencion()
      │
      ├─→ [PRIORIDAD 2] Respuestas predefinidas
      │   └─→ Util/respuestas_barberia.py/detectar_intencion_respuesta()
      │       └─→ Util/respuestas_barberia.json
      │
      ├─→ [PRIORIDAD 3] Preparación para Gemini
      │   ├─→ Util/informacion_barberia.py/get_info_por_intencion()
      │   │   └─→ [Si precios] Util/precios_barberia.py/obtener_info_precios_para_prompt()
      │   ├─→ Services/ChatService.py/obtener_ultimos_mensajes()
      │   └─→ Util/token_optimizer.py/build_modular_prompt()
      │
      ├─→ [PRIORIDAD 4] Generación con Gemini
      │   ├─→ [Si tokens > 500] Util/flujo_automatico.py/procesar_flujo_automatico()
      │   └─→ Util/procesar_texto_gemini.py/generar_respuesta_barberia()
      │       ├─→ Util/token_optimizer.py/build_modular_prompt()
      │       ├─→ Gemini API (google.genai)
      │       └─→ Util/respuestas_barberia.py/reemplazar_links()
      │
      └─→ Models/chat.py/_registrar_y_enviar_mensaje()
          ├─→ [Delay 30-60 segundos]
          ├─→ Services/ChatService.py/registrar_mensaje()
          └─→ whatsapp_api.py/enviar_mensaje_whatsapp()
              └─→ WhatsApp API (POST request)
```

---

## 🔑 Archivos Clave y sus Responsabilidades

### **webhook_server.py**
- **Responsabilidad:** Punto de entrada, recibe webhooks de WhatsApp
- **Funciones principales:** `receive()`, `verify()`

### **whatsapp_api.py**
- **Responsabilidad:** Comunicación con API de WhatsApp
- **Funciones principales:** 
  - `procesar_mensaje_recibido()` - Procesa mensaje entrante
  - `enviar_mensaje_whatsapp()` - Envía mensaje saliente

### **Models/chat.py**
- **Responsabilidad:** Lógica principal del bot, orquesta todo el flujo
- **Función principal:** `handle_text()` - Procesa cada mensaje

### **Util/get_type.py**
- **Responsabilidad:** Determina tipo de mensaje y extrae contenido
- **Función principal:** `get_type()` - Detecta tipo y procesa (especialmente audios)

### **Util/audio_util.py**
- **Responsabilidad:** Transcripción de audios
- **Función principal:** `get_transcription()` - Usa Gemini para transcribir

### **Util/intents.py**
- **Responsabilidad:** Detección básica de intenciones con keywords
- **Función principal:** `detectar_intencion()` - Matching simple de keywords

### **Util/respuestas_barberia.py**
- **Responsabilidad:** Sistema de respuestas predefinidas
- **Funciones principales:**
  - `detectar_intencion_respuesta()` - Detección más específica
  - `get_response()` - Obtiene respuesta del JSON
  - `reemplazar_links()` - Reemplaza placeholders

### **Util/politicas_respuestas.py**
- **Responsabilidad:** Políticas determinísticas (demoras)
- **Función principal:** `procesar_aviso_demora()` - Flujo completo de demoras

### **Util/precios_barberia.py**
- **Responsabilidad:** Gestión centralizada de precios
- **Funciones principales:**
  - `obtener_precio_por_nombre()` - Busca precio específico
  - `obtener_lista_completa_precios()` - Lista completa
  - `obtener_info_precios_para_prompt()` - Info para Gemini

### **Util/informacion_barberia.py**
- **Responsabilidad:** Información sobre servicios de barbería
- **Función principal:** `get_info_por_intencion()` - Obtiene info según intención

### **Util/token_optimizer.py**
- **Responsabilidad:** Optimización de prompts y tokens
- **Funciones principales:**
  - `build_modular_prompt()` - Construye prompt optimizado
  - `count_tokens()` - Cuenta tokens
  - `compress_history()` - Comprime historial
  - `_get_instrucciones_tono()` - Instrucciones de tono

### **Util/procesar_texto_gemini.py**
- **Responsabilidad:** Generación de respuestas con Gemini
- **Función principal:** `generar_respuesta_barberia()` - Llama a Gemini API

### **Util/flujo_automatico.py**
- **Responsabilidad:** Respuestas automáticas sin Gemini (fallback)
- **Función principal:** `procesar_flujo_automatico()` - Respuestas basadas en reglas

### **Util/error_handler.py**
- **Responsabilidad:** Manejo de errores y notificaciones
- **Función principal:** `manejar_error()` - Notifica al equipo

### **Services/ChatService.py**
- **Responsabilidad:** Operaciones de BD relacionadas con chats
- **Funciones principales:**
  - `obtener_o_crear_chat()` - Obtiene/crea chat
  - `registrar_mensaje()` - Guarda mensaje en BD
  - `obtener_ultimos_mensajes()` - Obtiene historial

---

## 🎯 Orden de Prioridades en `handle_text()`

1. **PRIORIDAD 0:** Comandos especiales y flujo secuencial de bienvenida
2. **PRIORIDAD 1:** Reglas críticas (demoras, derivación)
3. **PRIORIDAD 2:** Respuestas predefinidas (keywords específicos)
4. **PRIORIDAD 3:** Preparación para Gemini (info, historial, prompt)
5. **PRIORIDAD 4:** Generación con Gemini o flujo automático
6. **PRIORIDAD 5:** Fallbacks si hay errores
7. **PRIORIDAD 6:** Mensaje por defecto

---

## ⚡ Puntos Importantes

1. **Delay de 30-60 segundos:** Se aplica en `_registrar_y_enviar_mensaje()` antes de enviar
2. **Manejo de errores:** Si Gemini falla, no se envía mensaje técnico al cliente, solo se notifica al equipo
3. **Audios:** Se transcriben primero, luego se procesan como texto
4. **Precios:** Se obtienen de `Util/precios_barberia.py` para evitar inventar valores
5. **Demoras:** Se procesan con política determinística antes de cualquier otra cosa
6. **Respuestas predefinidas:** Tienen prioridad sobre Gemini si hay match de keywords

---

## 📝 Notas Finales

- El flujo está diseñado para ser eficiente: primero intenta respuestas rápidas (keywords), luego Gemini solo si es necesario
- Los tokens se estiman antes de llamar a Gemini para decidir si usar flujo automático o Gemini
- El historial se comprime si hay muchos mensajes para optimizar tokens
- Todos los mensajes se registran en BD antes y después de enviar


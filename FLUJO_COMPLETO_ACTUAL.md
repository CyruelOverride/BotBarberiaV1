# Flujo Completo del Bot de Barbería - Arquitectura Actual

## 📋 Resumen Ejecutivo

Este documento explica el flujo completo del bot después de la refactorización. El sistema ahora está organizado en módulos separados con responsabilidades claras: Router, Policy Engine, Handlers, y Detección Unificada de Intenciones.

---

## 🔄 Flujo Principal: De WhatsApp a Respuesta

### 1️⃣ **ENTRADA: WhatsApp Webhook**
**Archivo:** `webhook_server.py`  
**Función:** `receive()` (línea 116)

**¿Qué hace?**
- Recibe el POST de WhatsApp cuando llega un mensaje
- Extrae el JSON del request
- Llama a `procesar_mensaje_recibido()` de `whatsapp_api.py`
- Crea servicios de BD (ChatService, ClienteService)
- Obtiene/crea cliente y chat en BD
- Crea instancia de `Chat` y llama a `handle_text()`

**Código clave:**
```python
@app.post("/webhook")
async def receive(request: Request):
    data = await request.json()
    resultado = procesar_mensaje_recibido(data)  # → whatsapp_api.py
    # ... crear servicios BD ...
    chat.handle_text(numero, mensaje)  # → Models/chat.py
```

---

### 2️⃣ **PROCESAMIENTO INICIAL DEL MENSAJE**
**Archivo:** `whatsapp_api.py`  
**Función:** `procesar_mensaje_recibido()` (línea 121)

**¿Qué hace?**
- Valida que el mensaje sea de WhatsApp Business
- Extrae número del remitente y contenido
- Llama a `get_type()` para determinar tipo de mensaje (texto/audio/interactivo)
- Si es audio, `get_type()` lo transcribe con Gemini
- Retorna: `(numero, contenido, tipo)`

**Archivos relacionados:**
- `Util/get_type.py`: Determina tipo de mensaje y transcribe audios
- `Util/audio_util.py`: Maneja transcripción de audios

---

### 3️⃣ **ORQUESTADOR: Chat.handle_text()**
**Archivo:** `Models/chat.py`  
**Función:** `handle_text()` (línea 270)

**¿Qué hace?**
- **Orquestador simple**: Solo coordina, no contiene lógica de negocio
- Registra el mensaje del cliente en BD
- Llama al router para procesar el mensaje
- Si hay respuesta, aplica delay (30-60 segundos) y envía

**Código clave:**
```python
def handle_text(self, numero, texto):
    # Registrar mensaje en BD
    self.chat_service.registrar_mensaje(self.id_chat, texto_strip, es_cliente=True)
    
    # Llamar al router
    from Util.message_router import route_message
    respuesta = route_message(numero, texto, self)
    
    # Enviar con delay si hay respuesta
    if respuesta:
        return self._registrar_y_enviar_mensaje(numero, respuesta, aplicar_delay=True)
```

---

### 4️⃣ **ROUTER: Decisión de Prioridades**
**Archivo:** `Util/message_router.py`  
**Función:** `route_message()` (línea 389)

**¿Qué hace?**
- **Router principal**: Decide qué handler usar según prioridades
- No contiene lógica de negocio, solo routing
- Ejecuta handlers en orden de prioridad hasta encontrar respuesta

**Orden de prioridades:**
1. **PRIORIDAD 0**: Comandos especiales (`handle_commands`)
2. **PRIORIDAD 1**: Flujo secuencial de bienvenida (`handle_sequential_flow`)
3. **PRIORIDAD 2**: Reglas críticas (`handle_critical_rules`)
4. **PRIORIDAD 3**: Respuestas predefinidas (`handle_predefined_responses`)
5. **PRIORIDAD 4**: Generación con Gemini (`handle_gemini_generation`)
6. **FALLBACK**: Mensaje por defecto

**Código clave:**
```python
def route_message(numero: str, texto: str, chat_instance: Any) -> Optional[str]:
    # PRIORIDAD 0: Comandos
    respuesta = handle_commands(texto_lower, chat_instance)
    if respuesta: return respuesta
    
    # PRIORIDAD 1: Flujo secuencial
    respuesta = handle_sequential_flow(...)
    if respuesta: return respuesta
    
    # PRIORIDAD 2: Reglas críticas
    respuesta = handle_critical_rules(...)
    if respuesta: return respuesta
    
    # PRIORIDAD 3: Predefinidas
    respuesta = handle_predefined_responses(...)
    if respuesta: return respuesta
    
    # PRIORIDAD 4: Gemini
    respuesta = handle_gemini_generation(...)
    if respuesta: return respuesta
    
    # FALLBACK
    return mensaje_default
```

---

## 🔍 Handlers Específicos

### **PRIORIDAD 0: Comandos Especiales**
**Archivo:** `Util/message_router.py`  
**Función:** `handle_commands()`

**¿Qué hace?**
- Maneja comandos como "cancelar", "salir", "ayuda"
- Sin delay (respuesta inmediata)
- Ejecuta funciones registradas en `chat_instance.function_graph`

---

### **PRIORIDAD 1: Flujo Secuencial de Bienvenida**
**Archivo:** `Util/message_router.py`  
**Función:** `handle_sequential_flow()`

**¿Qué hace?**
- Maneja el flujo de bienvenida paso a paso:
  1. Saludo inicial (si es primer mensaje)
  2. Respuesta positiva → propuesta de agendar
  3. Solicitud de link → envío de link
  4. Confirmación de reserva → mensaje post-reserva
- Usa `handle_gemini_response()` para generar respuestas

---

### **PRIORIDAD 2: Reglas Críticas**
**Archivo:** `Util/message_router.py`  
**Función:** `handle_critical_rules()`

**¿Qué hace?**
- Maneja situaciones críticas que requieren respuesta inmediata:
  - **Avisos de demora**: Usa `handle_demora()` → Policy Engine
  - **Derivación a humano**: Usa `handle_derivacion()`
  - **Link explícito**: Usa `handle_link_agenda()`

**Flujo de demora (ejemplo):**
```
handle_critical_rules()
  → handle_demora()
    → detectar_aviso_demora() (keywords)
    → normalizar_datos_demora() (Gemini para extracción)
    → aplicar_politica() (Policy Engine - código determinístico)
    → obtener_mensaje_segun_estado() (mensaje según política)
```

---

### **PRIORIDAD 3: Respuestas Predefinidas**
**Archivo:** `Util/message_router.py`  
**Función:** `handle_predefined_responses()`

**¿Qué hace?**
- Busca respuestas predefinidas usando keywords directos
- Usa `detectar_intencion_respuesta()` de `Util/respuestas_barberia.py`
- Si encuentra match, retorna respuesta del JSON sin usar Gemini
- Reemplaza links y agrega link de agenda si es necesario

**Archivos relacionados:**
- `Util/respuestas_barberia.py`: Carga y busca respuestas predefinidas
- `Util/respuestas_barberia.json`: Base de datos de respuestas

---

### **PRIORIDAD 4: Generación con Gemini**
**Archivo:** `Util/message_router.py`  
**Función:** `handle_gemini_generation()`

**¿Qué hace?**
- Detecta intención unificada (keywords → predefinidas → Gemini)
- Obtiene información relevante según intención
- Obtiene historial de conversación si hay contexto
- Estima tokens del prompt
- Decide estrategia:
  - Si tokens <= 500: Usa Gemini directamente
  - Si tokens > 500: Intenta flujo automático primero, luego Gemini
- Llama a `handle_gemini_response()` para generar respuesta

**Archivos relacionados:**
- `Util/intent_detector.py`: Detección unificada de intenciones
- `Util/informacion_barberia.py`: Información relevante por intención
- `Util/token_optimizer.py`: Construcción de prompts optimizados
- `Util/procesar_texto_gemini.py`: Generación de respuestas con Gemini

---

## 🧠 Módulos de Soporte

### **Detección Unificada de Intenciones**
**Archivo:** `Util/intent_detector.py`  
**Función:** `detectar_intencion_unificada()`

**¿Qué hace?**
- **Unifica** las 3 formas de detectar intenciones en una sola función
- Estrategia en capas:
  1. **Keywords básicas** (`Util/intents.py`) - más rápido, sin costo
  2. **Keywords específicas** (`Util/respuestas_barberia.py`) - más preciso
  3. **Gemini** (solo si es ambiguo) - más flexible pero costoso

**Retorna:** `(intencion, fuente, metadata)`
- `intencion`: Nombre de la intención
- `fuente`: "keywords", "predefinidas", "gemini" o None
- `metadata`: Info adicional (ej: clave de respuesta predefinida)

---

### **Policy Engine**
**Archivo:** `Util/policy_engine.py`

**¿Qué hace?**
- **Motor de políticas determinísticas**: Solo código, NO prompts
- Funciones principales:
  - `evaluar_politica_demora()`: Evalúa gravedad de demora (código)
  - `aplicar_politica()`: Aplica políticas según intención
  - `obtener_mensaje_segun_estado()`: Obtiene mensaje según estado

**Ejemplo de política de demora:**
```python
def evaluar_politica_demora(minutos: int) -> str:
    if minutos <= 5: return "demora_leve"
    elif minutos <= 10: return "demora_media"
    elif minutos <= 15: return "demora_grave"
    else: return "turno_perdido"
```

**Responsabilidad:** Solo decisiones de políticas, código determinístico y auditable.

---

### **Handlers Específicos**
**Archivo:** `Util/message_handlers.py`

**¿Qué hace?**
- Handlers específicos para cada tipo de mensaje:
  - `handle_demora()`: Avisos de demora (usa Policy Engine)
  - `handle_derivacion()`: Derivación a humano
  - `handle_link_agenda()`: Envío de link de agenda
  - `handle_precios()`: Consultas de precios
  - `handle_gemini_response()`: Respuestas genéricas con Gemini

**Responsabilidad:** Lógica específica de cada tipo de mensaje.

---

### **Optimización de Prompts**
**Archivo:** `Util/token_optimizer.py`

**¿Qué hace?**
- Construye prompts modulares y optimizados
- Funciones principales:
  - `_get_instrucciones_tono()`: Instrucciones de tono (natural, sin exclamaciones excesivas)
  - `_get_prompt_especifico()`: Prompt específico según intención
  - `build_modular_prompt()`: Construye prompt completo con solo lo necesario
  - `count_tokens()`: Estima tokens sin usar API

**Características:**
- Solo incluye contexto, intención, estado, info factual
- **NO incluye reglas de negocio** (esas van en Policy Engine)
- Instrucciones de puntuación: evita exclamaciones, puntos excesivos, tildes poco comunes

---

### **Generación con Gemini**
**Archivo:** `Util/procesar_texto_gemini.py`  
**Función:** `generar_respuesta_barberia()`

**¿Qué hace?**
- Genera respuestas conversacionales usando Gemini
- Construye prompt usando `build_modular_prompt()`
- Maneja errores y fallbacks
- Retorna `None` si hay error (no envía mensaje técnico al cliente)

**Flujo:**
```
generar_respuesta_barberia()
  → build_modular_prompt() (token_optimizer.py)
  → validate_and_compress() (si excede tokens)
  → Gemini API call
  → Validar respuesta
  → Retornar respuesta o None
```

---

## 📊 Diagrama de Flujo

```
WhatsApp → webhook_server.py
    ↓
whatsapp_api.py (procesar_mensaje_recibido)
    ↓
get_type.py (determinar tipo, transcribir audio)
    ↓
Models/chat.py (handle_text - orquestador)
    ↓
Util/message_router.py (route_message)
    ↓
    ├─→ handle_commands() [PRIORIDAD 0]
    ├─→ handle_sequential_flow() [PRIORIDAD 1]
    ├─→ handle_critical_rules() [PRIORIDAD 2]
    │   ├─→ handle_demora()
    │   │   ├─→ detectar_aviso_demora() (keywords)
    │   │   ├─→ normalizar_datos_demora() (Gemini extracción)
    │   │   ├─→ aplicar_politica() (Policy Engine)
    │   │   └─→ obtener_mensaje_segun_estado()
    │   ├─→ handle_derivacion()
    │   └─→ handle_link_agenda()
    ├─→ handle_predefined_responses() [PRIORIDAD 3]
    │   └─→ detectar_intencion_respuesta() (keywords)
    └─→ handle_gemini_generation() [PRIORIDAD 4]
        ├─→ detectar_intencion_unificada()
        │   ├─→ keywords básicas
        │   ├─→ keywords específicas
        │   └─→ Gemini (solo si ambiguo)
        ├─→ get_info_por_intencion()
        ├─→ build_modular_prompt()
        └─→ generar_respuesta_barberia()
            └─→ Gemini API
```

---

## 🎯 Responsabilidades por Archivo

| Archivo | Responsabilidad |
|---------|----------------|
| `webhook_server.py` | Entrada de webhook, creación de servicios BD |
| `whatsapp_api.py` | Procesamiento inicial, extracción de datos |
| `Util/get_type.py` | Determinar tipo de mensaje, transcribir audios |
| `Models/chat.py` | Orquestador simple: registro BD, delay, envío |
| `Util/message_router.py` | Router: decide qué handler usar según prioridades |
| `Util/message_handlers.py` | Handlers específicos para cada tipo de mensaje |
| `Util/intent_detector.py` | Detección unificada de intenciones (3 capas) |
| `Util/policy_engine.py` | Políticas determinísticas (código, no prompts) |
| `Util/politicas_respuestas.py` | Detección y extracción de datos de demora |
| `Util/token_optimizer.py` | Construcción de prompts optimizados |
| `Util/procesar_texto_gemini.py` | Generación de respuestas con Gemini |
| `Util/informacion_barberia.py` | Base de conocimiento de la barbería |
| `Util/respuestas_barberia.py` | Respuestas predefinidas desde JSON |
| `Util/precios_barberia.py` | Gestión de precios de servicios |

---

## 🔑 Principios de Diseño

1. **Separación de responsabilidades**: Cada módulo tiene una función clara
2. **Router pattern**: El router decide qué handler usar, no contiene lógica
3. **Policy Engine**: Políticas determinísticas en código, no en prompts
4. **Detección unificada**: Una sola función para detectar intenciones
5. **Optimización de tokens**: Prompts modulares, solo lo necesario
6. **Fallbacks**: Múltiples niveles de fallback para robustez
7. **Sin reglas en prompts**: Solo contexto, intención, estado, info factual

---

## 📝 Notas Importantes

- **Delay de 30-60 segundos**: Se aplica en `_registrar_y_enviar_mensaje()` para hacer más realista
- **Errores silenciosos**: Si hay error, no se envía mensaje técnico al cliente, solo se notifica al equipo
- **Respuestas predefinidas**: Tienen prioridad sobre Gemini cuando hay match con keywords
- **Tokens**: Si tokens > 500, intenta flujo automático antes de Gemini
- **Historial**: Se obtiene solo cuando hay contexto de conversación (ya se saludó o hay intención)


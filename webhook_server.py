from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import traceback
from Models.chat import Chat
from Services.ChatService import ChatService
from Services.ClienteService import ClienteService
from Util.database import get_db_session, init_db, engine
from sqlmodel import text
from whatsapp_api import procesar_mensaje_recibido, WHATSAPP_PHONE_NUMBER_ID, enviar_mensaje_whatsapp
from seed_database import main as seed_main

app = FastAPI()
VERIFY_TOKEN = "Chacalitas2025"

# Sistema para rastrear último cliente que interactuó con el bot (para testing)
# Estructura: {numero_responsable: {ultimo_cliente: numero, ultimo_mensaje: texto}}
ULTIMO_CLIENTE_CONTEXT: dict = {}

@app.on_event("startup")
async def startup_event():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'cliente'
                );
            """))
            tabla_existe = result.scalar()
        
        if not tabla_existe:
            print("🔄 Tablas no encontradas. Inicializando base de datos...")
            init_db()
            print("✅ Tablas creadas correctamente")
            
            print("🌱 Ejecutando seeding de datos iniciales...")
            try:
                seed_main()
            except Exception as e:
                print(f"⚠️ Error en seeding automático: {e}")
                print("💡 Puedes ejecutar el seeding manualmente visitando /seed-db")
        else:
            print("✅ Base de datos ya inicializada")
        
        print("🚀 Sistema de barbería - Bot de WhatsApp inicializado")
        
    except Exception as e:
        print(f"⚠️ Error al verificar/inicializar base de datos: {e}")
        print("💡 Puedes inicializar manualmente visitando /init-db")


@app.get("/")
async def root():
    return {
        "message": "WhatsApp Webhook Server funcionando",
        "phone_number_id": WHATSAPP_PHONE_NUMBER_ID,
        "endpoints": {
            "webhook": "/webhook",
            "health": "/health",
            "init_db": "/init-db",
            "seed_db": "/seed-db"
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/init-db")
async def init_database():
    """Endpoint para inicializar las tablas manualmente (si no se inicializaron automáticamente)."""
    try:
        init_db()
        return {
            "status": "success",
            "message": "✅ Tablas creadas correctamente",
            "tablas": [
                "cliente", "chat", "mensaje",
                "categoria", "producto"
            ]
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"❌ Error al inicializar: {str(e)}"
        }


@app.get("/seed-db")
async def seed_database():
    """Endpoint para poblar la base de datos con datos de prueba."""
    try:
        seed_main()
        return {
            "status": "success",
            "message": "✅ Seeding completado exitosamente",
            "nota": "Este endpoint es para datos de prueba. El bot de barbería funciona independientemente."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"❌ Error en seeding: {str(e)}"
        }


@app.get("/webhook")
async def verify(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return PlainTextResponse(challenge)
    return PlainTextResponse("Token inválido", status_code=403)


@app.post("/webhook")
async def receive(request: Request):
    db_session = None
    try:
        data = await request.json()
        resultado = procesar_mensaje_recibido(data)

        if not resultado:
            return PlainTextResponse("EVENT_RECEIVED", status_code=200)

        # Extraer valores del resultado (ahora retorna 5 valores)
        numero, mensaje, tipo, message_id, replied_message_id = resultado
        print(f"Mensaje recibido ({tipo}) de {numero}: {mensaje}")

        # PRIORIDAD: Verificar si es mensaje del responsable
        from Util.error_flow import is_responsable, handle_responsable_reply
        
        if is_responsable(numero):
            # Es el responsable, verificar si está respondiendo a un error
            if handle_responsable_reply(numero, mensaje, replied_message_id):
                # Se procesó correctamente, retornar OK
                return PlainTextResponse("EVENT_RECEIVED", status_code=200)
            
            # Verificar si el responsable está usando #Responder para responder a cualquier mensaje del bot
            if tipo in ("text", "interactive") and mensaje.strip().startswith("#Responder"):
                # Extraer el mensaje a reenviar (todo después de #Responder)
                mensaje_a_reenviar = mensaje.strip()[10:].strip()  # Remover "#Responder" y espacios
                
                if mensaje_a_reenviar:
                    # Normalizar número del responsable para buscar en contexto
                    # El número puede venir con o sin +, normalizamos a formato estándar
                    from whatsapp_api import normalizar_numero_telefono
                    numero_normalizado = normalizar_numero_telefono(numero)
                    responsable_test = normalizar_numero_telefono("59891453663")
                    
                    # Buscar último cliente que interactuó con el bot
                    # Intentar con número normalizado y sin normalizar
                    ultimo_cliente = None
                    if responsable_test in ULTIMO_CLIENTE_CONTEXT:
                        ultimo_cliente = ULTIMO_CLIENTE_CONTEXT[responsable_test].get("ultimo_cliente")
                    elif numero_normalizado in ULTIMO_CLIENTE_CONTEXT:
                        ultimo_cliente = ULTIMO_CLIENTE_CONTEXT[numero_normalizado].get("ultimo_cliente")
                    elif numero in ULTIMO_CLIENTE_CONTEXT:
                        ultimo_cliente = ULTIMO_CLIENTE_CONTEXT[numero].get("ultimo_cliente")
                    
                    if ultimo_cliente:
                        # Reenviar mensaje al último cliente
                        resultado = enviar_mensaje_whatsapp(ultimo_cliente, mensaje_a_reenviar)
                        if resultado.get("success"):
                            print(f"✅ Mensaje del responsable reenviado al último cliente {ultimo_cliente}")
                        else:
                            print(f"⚠️ Error al reenviar mensaje: {resultado.get('error')}")
                        return PlainTextResponse("EVENT_RECEIVED", status_code=200)
                    else:
                        print(f"⚠️ No hay último cliente registrado para responsable {numero}")
                else:
                    print(f"⚠️ Mensaje vacío después de #Responder")
                # Si no se pudo procesar, continuar con flujo normal
            # Si no es #Responder, continuar con flujo normal

        # Crear sesión de DB
        db_session = get_db_session()
        
        try:
            chat_service = ChatService(db_session)
            
            id_cliente = ClienteService.obtener_o_crear_cliente("", "", numero)
            
            chat_bd = chat_service.obtener_o_crear_chat(id_cliente, numero)
            id_chat = chat_bd.id_chat
            
            if tipo in ("text", "interactive"):
                chat_service.registrar_mensaje(id_chat, mensaje, es_cliente=True)
            
            chat = Chat(
                id_chat=id_chat,
                id_cliente=id_cliente,
                chat_service=chat_service
            )

            # Registrar último cliente que interactuó (para testing con #Responder)
            # Solo si no es el responsable
            from Util.error_flow import is_responsable
            from whatsapp_api import normalizar_numero_telefono
            if not is_responsable(numero):
                # Rastrear último cliente por cada responsable (para testing, ambos son el mismo número)
                # Normalizar número para consistencia
                responsable_test = normalizar_numero_telefono("59891453663")
                if responsable_test not in ULTIMO_CLIENTE_CONTEXT:
                    ULTIMO_CLIENTE_CONTEXT[responsable_test] = {}
                ULTIMO_CLIENTE_CONTEXT[responsable_test]["ultimo_cliente"] = numero
                ULTIMO_CLIENTE_CONTEXT[responsable_test]["ultimo_mensaje"] = mensaje
            
            if tipo in ("text", "interactive"):
                chat.handle_text(numero, mensaje)
            else:
                chat.handle_text(numero, "Tipo de mensaje no soportado aún.")

            return PlainTextResponse("EVENT_RECEIVED", status_code=200)
        
        finally:
            # ✅ IMPORTANTE: Cerrar la sesión siempre
            if db_session:
                db_session.close()
                print("🔒 Sesión de DB cerrada")

    except Exception as e:
        # Captura global de errores críticos
        from Util.error_flow import handle_critical_exception
        
        # Intentar extraer número y mensaje si están disponibles
        numero_error = "desconocido"
        mensaje_error = "Error al procesar webhook"
        
        try:
            # Intentar obtener datos del resultado si existe
            if 'resultado' in locals() and resultado:
                numero_error, mensaje_error, _, _, _ = resultado
        except:
            # Si no se puede extraer, usar valores por defecto
            pass
        
        # Manejar error crítico
        handle_critical_exception(e, mensaje_error, numero_error, "webhook_server")
        
        # Cerrar sesión en caso de error también
        if db_session:
            db_session.close()
            print("🔒 Sesión de DB cerrada (después de error)")
        
        # Siempre responder 200 OK al webhook para evitar reintentos
        return PlainTextResponse("EVENT_RECEIVED", status_code=200)
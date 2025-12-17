import os
import requests
from Util.get_type import get_type

WHATSAPP_API_URL = "https://graph.facebook.com/v22.0"
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN") or "<TU_TOKEN_DE_ACCESO>"
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN") or "Chacalitas2025"
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "871681339360716")


def normalizar_numero_telefono(numero: str) -> str:
    numero = numero.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not numero.startswith("+"):
        numero = "+" + numero
    return numero


def enviar_mensaje_whatsapp(numero, mensaje):
    url = f"{WHATSAPP_API_URL}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    if isinstance(mensaje, str):
        data = {
            "messaging_product": "whatsapp",
            "to": numero,
            "type": "text",
            "text": {"body": mensaje},
        }
    else:
        data = mensaje  

    response = requests.post(url, headers=headers, json=data)
    print(f" Enviado a {numero}")
    print(" Estado:", response.status_code)

    try:
        res_json = response.json()
        message_id = None
        if response.status_code == 200 and "messages" in res_json:
            # Extraer message_id de la respuesta de WhatsApp API
            message_id = res_json.get("messages", [{}])[0].get("id") if res_json.get("messages") else None
        
        return {
            "success": response.status_code == 200,
            "error": res_json.get("error"),
            "message_id": message_id,
            "messages": res_json.get("messages", [])
        }
    except Exception as e:
        print(" Error", e)
        return {"success": False, "error": str(e), "message_id": None}


def enviar_imagen_whatsapp(numero, ruta_imagen, caption=""):
    url = f"{WHATSAPP_API_URL}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    
    _imagen = f"{WHATSAPP_API_URL}/{WHATSAPP_PHONE_NUMBER_ID}/media"
    
    try:
        with open(ruta_imagen, 'rb') as img_file:
            files = {
                'file': (os.path.basename(ruta_imagen), img_file, 'image/png'),
                'messaging_product': (None, 'whatsapp'),
            }
            upload_headers = {
                "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
            }
            
            print(f"📤 Subiendo imagen: {ruta_imagen}")
            respuesta = requests.post(_imagen, headers=upload_headers, files=files)
            
            if respuesta.status_code != 200:
                print(f"❌ Error subiendo imagen: {respuesta.status_code}")
                print(f"   Respuesta: {respuesta.text}")
                return {"success": False, "error": f"Error al subir imagen: {respuesta.text}"}
            
            _imagen = respuesta.json().get("id")
            print(f"✅ Imagen subida. Media ID: {_imagen}")
        
        data = {
            "messaging_product": "whatsapp",
            "to": numero,
            "type": "image",
            "image": {
                "id": _imagen
            }
        }
        
        if caption:
            data["image"]["caption"] = caption
        
        response = requests.post(url, headers=headers, json=data)
        print(f"➡️ Enviando imagen a {numero}")
        print("📨 Estado:", response.status_code)
        
        try:
            res_json = response.json()
            if response.status_code == 200:
                print("✅ Imagen enviada exitosamente")
                return {
                    "success": True,
                    "message_id": res_json.get("messages", [{}])[0].get("id")
                }
            else:
                return {
                    "success": False,
                    "error": res_json.get("error", "Error desconocido")
                }
        except Exception as e:
            print("⚠️ Error al interpretar la respuesta:", e)
            return {"success": False, "error": str(e)}
            
    except FileNotFoundError:
        print(f"❌ Archivo no encontrado: {ruta_imagen}")
        return {"success": False, "error": f"Archivo no encontrado: {ruta_imagen}"}
    except Exception as e:
        print(f"❌ Error enviando imagen: {e}")
        return {"success": False, "error": str(e)}


def procesar_mensaje_recibido(data):
    try:
        if data.get("object") != "whatsapp_business_account":
            return None

        entry = data.get("entry", [{}])[0]
        value = entry.get("changes", [{}])[0].get("value", {})

        if "statuses" in value:
            return None

        messages = value.get("messages", [])
        if not messages:
            return None

        message = messages[0]
        numero = message.get("from")
        message_id = message.get("id")
        
        # Extraer contexto de respuesta si existe
        context = message.get("context", {})
        replied_message_id = None
        if context:
            replied_message = context.get("replied_message", {})
            replied_message_id = replied_message.get("id") if replied_message else None

        if numero == WHATSAPP_PHONE_NUMBER_ID:
            print(" Ignorando mensaje del propio bot.")
            return None

        tipo, contenido = get_type(message)
        
        if tipo == "audio":
            tipo = "text"
        
        # Retornar: numero, contenido, tipo, message_id, replied_message_id
        return numero, contenido, tipo, message_id, replied_message_id

    except Exception as e:
        print(f"⚠️ Error al procesar mensaje recibido: {e}")
        return None

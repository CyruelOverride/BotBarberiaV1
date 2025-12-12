"""
Módulo para manejar respuestas predefinidas del bot de barbería.
Carga respuestas desde JSON y permite buscar por intención y clave.
"""

import json
import os
from typing import Optional, Dict, Tuple
from google import genai
from google.genai import types

# Ruta al archivo JSON de respuestas
RESPUESTAS_JSON_PATH = os.path.join(
    os.path.dirname(__file__),
    "respuestas_barberia.json"
)

# Cache de respuestas cargadas
_respuestas_cache: Optional[Dict] = None

# Cliente de Gemini (se inicializa solo si se necesita)
_client_gemini = None

def _get_gemini_client():
    """Obtiene el cliente de Gemini, inicializándolo solo si es necesario."""
    global _client_gemini
    if _client_gemini is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            _client_gemini = genai.Client(api_key=api_key)
    return _client_gemini


def cargar_respuestas() -> Dict:
    """
    Carga las respuestas desde el archivo JSON.
    Usa cache para evitar cargar múltiples veces.
    
    Returns:
        Diccionario con todas las respuestas organizadas por intención
    """
    global _respuestas_cache
    
    if _respuestas_cache is not None:
        return _respuestas_cache
    
    try:
        with open(RESPUESTAS_JSON_PATH, 'r', encoding='utf-8') as f:
            _respuestas_cache = json.load(f)
        return _respuestas_cache
    except FileNotFoundError:
        print(f"⚠️ Archivo de respuestas no encontrado: {RESPUESTAS_JSON_PATH}")
        return {}
    except json.JSONDecodeError as e:
        print(f"⚠️ Error al parsear JSON de respuestas: {e}")
        return {}


def get_response(intencion: str, clave: str) -> Optional[str]:
    """
    Obtiene una respuesta específica por intención y clave.
    
    Args:
        intencion: Nombre de la intención (ej: "precios", "turnos")
        clave: Clave de la respuesta (ej: "cuanto_sale", "turno_hoy")
        
    Returns:
        Texto de la respuesta o None si no existe
    """
    respuestas = cargar_respuestas()
    
    if intencion not in respuestas:
        return None
    
    return respuestas[intencion].get(clave)


def buscar_respuesta_por_intencion(intencion: str) -> Dict[str, str]:
    """
    Busca todas las respuestas de una intención específica.
    
    Args:
        intencion: Nombre de la intención
        
    Returns:
        Diccionario con todas las respuestas de esa intención
    """
    respuestas = cargar_respuestas()
    return respuestas.get(intencion, {})


def detectar_intencion_respuesta(texto: str) -> Optional[Tuple[str, str]]:
    """
    Detecta la intención y clave de respuesta basándose en keywords del texto.
    
    Args:
        texto: Mensaje del usuario
        
    Returns:
        Tupla (intencion, clave) si se detecta, None si no hay match
    """
    if not texto:
        return None
    
    texto_lower = texto.lower().strip()
    
    # Mapeo de keywords a (intencion, clave)
    keywords_map = {
        # Precios
        ("cuanto sale", "cuánto sale", "precio", "precios", "cuánto cuesta", "cuanto cuesta", "tarifa", "costo"): ("precios", "cuanto_sale"),
        ("más barato", "mas barato", "más económico", "mas economico", "otros lados", "otro lugar", "más caro", "mas caro"): ("precios", "mas_barato_otros_lados"),
        
        # Ubicación
        ("donde están", "dónde están", "donde estan", "ubicación", "ubicacion", "dirección", "direccion", "direccion", "donde queda", "dónde queda"): ("ubicacion", "donde_estan"),
        
        # Turnos
        ("turno hoy", "turno para hoy", "hora hoy", "tenes hora hoy", "tienes hora hoy", "disponible hoy"): ("turnos", "turno_hoy"),
        ("agendar con tiempo", "reservar con tiempo", "con cuánto tiempo", "con cuanto tiempo", "anticipación", "anticipacion"): ("turnos", "agendar_con_tiempo"),
        ("salgo del laburo", "salgo del trabajo", "salgo a las", "horarios después", "horarios despues", "después del trabajo", "despues del trabajo"): ("turnos", "horarios_salida_trabajo"),
        ("no hay horarios", "no hay turnos", "no quedan turnos", "no quedan horarios", "sin horarios", "sin turnos"): ("turnos", "no_horarios_disponibles"),
        ("no veo horarios hoy", "no aparecen horarios hoy", "no hay para hoy", "no queda nada hoy"): ("turnos", "no_veo_horarios_hoy"),
        ("no aparecen horarios", "no veo horarios", "no hay disponibilidad"): ("situaciones", "no_aparen_horarios_agenda"),
        
        # Servicios
        ("qué incluye", "que incluye", "que trae", "qué trae", "incluye", "qué viene", "que viene"): ("servicios", "que_incluye_corte"),
        ("qué es asesoramiento", "que es asesoramiento", "qué es el asesoramiento", "que es el asesoramiento", "asesoramiento", "asesoría", "asesoria"): ("servicios", "que_es_asesoramiento"),
        ("solo barba", "solo la barba", "hacen barba", "arreglan barba", "barba sola"): ("servicios", "solo_barba"),
        ("hacen tinta", "hacen tatuajes", "tatuajes", "tinta"): ("servicios", "hacen_tinta"),
        ("asesoría se cobra", "asesoria se cobra", "asesoramiento se cobra", "se cobra aparte", "cobra aparte"): ("servicios", "asesoria_se_cobra_aparte"),
        
        # Tiempo
        ("cuánto demora", "cuanto demora", "cuánto tarda", "cuanto tarda", "duración", "duracion", "tiempo demora"): ("tiempo", "cuanto_demora"),
        
        # Pago
        ("pago con tarjeta", "aceptan tarjeta", "tarjeta de crédito", "tarjeta de credito", "tarjeta", "débito", "debito"): ("pago", "pago_tarjeta"),
        
        # Productos
        ("venden productos", "venden cera", "productos a la venta", "productos en venta", "comprar productos", "comprar cera"): ("productos", "venden_productos"),
        
        # Cancelaciones
        ("reagendar", "re agendar", "cambiar turno", "cambiar cita", "mover turno"): ("cancelaciones", "cancelar_reagendar_1"),
        ("no voy a poder", "no puedo llegar", "no puedo ir", "cancelar", "cancelar turno", "cancelar cita"): ("cancelaciones", "cancelar_reagendar_2"),
        ("no pude llegar", "no llegué", "no llegue", "perdí el turno", "perdi el turno", "se me pasó", "se me paso"): ("cancelaciones", "no_pude_llegar"),
        
        # Situaciones
        ("voy ahora", "caer ahora", "sin agenda", "sin reserva", "sin turno", "llegar ahora"): ("situaciones", "caer_sin_agenda"),
        ("dos personas", "somos dos", "dos turnos", "vamos dos", "con otra persona"): ("situaciones", "dos_personas"),
        ("no me manejo", "no manejo web", "no sé usar", "no se usar", "ayuda con web", "ayuda reservar"): ("situaciones", "no_manejo_web"),
        ("no encuentro", "no encuentro el lugar", "está cerrado", "esta cerrado", "cerrado", "no lo encuentro"): ("situaciones", "no_encuentro_lugar"),
        ("llegando tarde", "llegando 10", "llegando 15", "atrasado", "me atrasé", "me atrase", "llegando unos minutos"): ("situaciones", "llegando_tarde"),
        ("llegando 30", "llegando 40", "muy tarde", "muy atrasado", "atraso largo", "llegando mucho más tarde"): ("situaciones", "llegando_muy_tarde"),
        ("política", "politica", "horarios", "respeto turnos", "cancelar con tiempo"): ("situaciones", "politica_horarios"),
        
        # Otros
        ("ya me corté", "ya me corte", "me corté hace poco", "me corte hace poco", "corté hace poco", "corte hace poco"): ("otros", "ya_me_corte"),
        ("son de montevideo", "están en montevideo", "estan en montevideo", "montevideo", "de dónde son", "de donde son"): ("otros", "son_de_montevideo"),
    }
    
    # Buscar match en keywords
    for keywords, (intencion, clave) in keywords_map.items():
        for keyword in keywords:
            if keyword in texto_lower:
                return (intencion, clave)
    
    return None


def detectar_clave_con_gemini(texto: str) -> Optional[Tuple[str, str]]:
    """
    Usa Gemini para detectar si el mensaje coincide con alguna clave del JSON de forma flexible.
    Esto permite que mensajes como "che bro cómo saco turno pa mañana?" coincidan con "turnos".
    
    Args:
        texto: Mensaje del usuario
        
    Returns:
        Tupla (intencion, clave) si se detecta coincidencia, None si no
    """
    try:
        client = _get_gemini_client()
        if not client:
            return None  # Si no hay API key, no usar Gemini
        
        # Obtener todas las claves disponibles del JSON
        respuestas = cargar_respuestas()
        claves_disponibles = []
        for intencion, respuestas_intencion in respuestas.items():
            for clave in respuestas_intencion.keys():
                claves_disponibles.append(f"{intencion}.{clave}")
        
        # Crear prompt para Gemini
        prompt = f"""Analizá este mensaje del usuario: "{texto}"

¿El usuario quiere algo que coincida con alguna de estas claves de respuestas?

Claves disponibles:
{', '.join(claves_disponibles)}

Respondé SOLO con JSON en este formato:
{{"intencion": "nombre_intencion", "clave": "nombre_clave"}}

Si NO hay coincidencia clara, respondé:
{{"intencion": null, "clave": null}}

Solo JSON, sin explicaciones."""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0)
            ),
        )
        
        response_text = response.text if hasattr(response, 'text') and response.text else ""
        
        if not response_text:
            return None
        
        # Extraer JSON de la respuesta
        try:
            # Buscar JSON en la respuesta
            first_brace = response_text.find("{")
            last_brace = response_text.rfind("}")
            if first_brace != -1 and last_brace != -1:
                json_text = response_text[first_brace:last_brace + 1]
                resultado = json.loads(json_text)
                
                if resultado.get("intencion") and resultado.get("clave"):
                    return (resultado["intencion"], resultado["clave"])
        except (json.JSONDecodeError, KeyError):
            pass
        
        return None
        
    except Exception as e:
        print(f"⚠️ Error en detectar_clave_con_gemini: {e}")
        return None


def get_respuesta_predefinida(texto: str) -> Optional[str]:
    """
    Función principal que intenta encontrar una respuesta predefinida.
    Primero intenta con keywords, luego con Gemini para coincidencias flexibles.
    
    Args:
        texto: Mensaje del usuario
        
    Returns:
        Texto de respuesta predefinida o None si no se encuentra
    """
    # PRIMERO: Intentar con keywords (más rápido y barato)
    resultado = detectar_intencion_respuesta(texto)
    
    if resultado:
        intencion, clave = resultado
        return get_response(intencion, clave)
    
    # SEGUNDO: Si no hay match con keywords, usar Gemini para coincidencias flexibles
    resultado_gemini = detectar_clave_con_gemini(texto)
    
    if resultado_gemini:
        intencion, clave = resultado_gemini
        return get_response(intencion, clave)
    
    return None


def reemplazar_links(respuesta: str, link_agenda: str = "", link_maps: str = "") -> str:
    """
    Reemplaza placeholders de links en las respuestas.
    
    Args:
        respuesta: Texto de respuesta
        link_agenda: Link de la agenda (Weybook)
        link_maps: Link de Google Maps
        
    Returns:
        Respuesta con links reemplazados
    """
    if link_agenda:
        respuesta = respuesta.replace("(link de agenda)", link_agenda)
        respuesta = respuesta.replace("(link de la agenda)", link_agenda)
        respuesta = respuesta.replace("acá te dejo el link:", f"acá te dejo el link:\n{link_agenda}")
        respuesta = respuesta.replace("Acá te dejo el link:", f"Acá te dejo el link:\n{link_agenda}")
        respuesta = respuesta.replace("Acá tenés el link:", f"Acá tenés el link:\n{link_agenda}")
        respuesta = respuesta.replace("acá tenés el link:", f"acá tenés el link:\n{link_agenda}")
        respuesta = respuesta.replace("Ahi te la paso", f"Ahi te la paso\n{link_agenda}")
        respuesta = respuesta.replace("A continuación te dejo el link:", f"A continuación te dejo el link:\n{link_agenda}")
    
    if link_maps:
        respuesta = respuesta.replace("(link de Google Maps)", link_maps)
        respuesta = respuesta.replace("(https://maps.app.goo.gl/uaJPmJrxUJr5wZE87)", link_maps)
    
    return respuesta

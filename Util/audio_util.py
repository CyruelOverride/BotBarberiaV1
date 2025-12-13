import os
import time
import tempfile
import requests
from google import genai
from Util.token_optimizer import log_token_usage, count_tokens, get_optimized_config

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def get_transcription(binary_audio: bytes) -> str:
    
    max_retries = 3
    base_delay = 2
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as temp_file:
            temp_file.write(binary_audio)
            temp_file_path = temp_file.name
        
        for attempt in range(max_retries):
            try:
                print(f"🔄 Intento {attempt + 1}/{max_retries} de transcripción")
                
                myfile = client.files.upload(file=temp_file_path)

                # Contar tokens del prompt (solo texto, el archivo no se cuenta aquí)
                prompt_text = "Transcribe this audio file"
                input_tokens = count_tokens(prompt_text)
                log_token_usage("get_transcription", input_tokens, 0)

                response = client.models.generate_content(
                    model="gemini-2.5-flash", 
                    contents=[prompt_text, myfile],
                    config=get_optimized_config()
                )
                
                texto = response.text
                output_tokens = count_tokens(texto) if texto else 0
                log_token_usage("get_transcription", input_tokens, output_tokens)
                
                print(f"✅ Transcripción exitosa: {texto[:50]}...")
                return texto
                    
            except Exception as error:
                print(f"❌ Error en intento {attempt + 1}: {type(error).__name__} → {error}")
                raise error
        
        raise Exception("No se logró transcribir el audio después de varios intentos")
                
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except:
                pass


def get_url_media(id_audio: str) -> str:
    url = f'https://graph.facebook.com/v18.0/{id_audio}/'
    headers = {
        'Authorization': f'Bearer {os.getenv("WHATSAPP_ACCESS_TOKEN")}'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()['url']
    except Exception as error:
        raise error


def get_binary_media(url: str) -> bytes:
    headers = {
        'Authorization': f'Bearer {os.getenv("WHATSAPP_ACCESS_TOKEN")}'
    }
    
    try:
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()
        return response.content
    except Exception as error:
        raise error

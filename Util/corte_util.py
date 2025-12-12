"""
Utilidades para manejar información de cortes de pelo en memoria.
No se persisten en BD, son temporales por sesión.
"""

CORTES = {}

def get_cortes(numero):
    """Obtiene los cortes de pelo del usuario."""
    return CORTES.setdefault(numero, [])

def add_corte(numero, corte):
    """Agrega un corte de pelo a la lista del usuario.
    
    Args:
        numero: Número de teléfono del usuario
        corte: Diccionario con información del corte (nombre, apellido, servicio, día, hora, fecha, etc.)
    
    Returns:
        Lista de cortes del usuario
    """
    cortes = get_cortes(numero)
    cortes.append(corte)
    return cortes

def clear_cortes(numero):
    """Limpia los cortes de pelo del usuario."""
    if numero in CORTES:
        del CORTES[numero]

def get_corte(numero, indice):
    """Obtiene un corte específico por índice."""
    cortes = get_cortes(numero)
    if 0 <= indice < len(cortes):
        return cortes[indice]
    return None


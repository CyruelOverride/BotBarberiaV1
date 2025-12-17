"""
Policy Engine: Motor de políticas determinísticas.
Solo decisiones de políticas basadas en código, NO reglas en prompts.
"""

from typing import Dict, Optional


def evaluar_politica_demora(minutos: Optional[int]) -> str:
    """
    Evalúa la gravedad de la demora según política determinística.
    
    Args:
        minutos: Minutos de demora (None si no se pudo determinar)
        
    Returns:
        Estado de la demora: "demora_leve", "demora_media", "demora_grave", "turno_perdido"
    """
    if minutos is None:
        # Si no se puede determinar, asumir demora media
        return "demora_media"
    
    if minutos <= 5:
        return "demora_leve"
    elif minutos <= 10:
        return "demora_media"
    elif minutos <= 15:
        return "demora_grave"
    else:
        return "turno_perdido"


def aplicar_politica(intencion: str, datos: Dict) -> Dict:
    """
    Aplica políticas determinísticas según la intención detectada.
    
    Args:
        intencion: Intención detectada (ej: "aviso_demora", "precios", etc.)
        datos: Datos extraídos del mensaje
        
    Returns:
        Dict con estado de política y metadata:
        {
            "estado": "demora_leve" | "demora_media" | etc.,
            "metadata": {...}
        }
    """
    if intencion == "aviso_demora":
        minutos = datos.get("minutos_demora")
        estado = evaluar_politica_demora(minutos)
        return {
            "estado": estado,
            "metadata": {
                "minutos_demora": minutos,
                "hora_turno": datos.get("hora_turno"),
                "hora_llegada": datos.get("hora_llegada")
            }
        }
    
    # Para otras intenciones, retornar estado neutro
    return {
        "estado": "neutro",
        "metadata": datos
    }


def obtener_mensaje_segun_estado(estado: str, contexto: Dict) -> Optional[str]:
    """
    Obtiene mensaje según estado de política.
    Los mensajes están definidos en código, no en prompts.
    
    Args:
        estado: Estado de la política (ej: "demora_leve", "demora_media")
        contexto: Contexto adicional (ej: link_agenda para cancelaciones)
        
    Returns:
        Mensaje de respuesta o None si no hay mensaje para ese estado
    """
    # Mensajes de demora
    mensajes_demora = {
        "demora_leve": "Bro, no pasa nada. Ya le avisamos al barbero con el cual agendaste tu turno.",
        "demora_media": "Bro, no pasa nada. Ya le avisamos al barbero con el cual agendaste tu turno.",
        "demora_grave": "Bro, cuando el atraso es así es un poco complicado porque tenemos otros turnos agendados detrás. Si podés llegar lo antes posible, genial. Si no, mejor cancelá ese turno y agendate uno nuevo en el primer horario disponible.",
        "turno_perdido": "Bro, cuando el atraso es tan largo es muy difícil poder atenderte bien porque tenemos otros turnos agendados detrás. En este caso, lo mejor es que canceles ese turno y te agendes uno nuevo en el primer horario disponible, así podemos darte el tiempo que necesitás y no atrasamos al resto."
    }
    
    if estado in mensajes_demora:
        mensaje = mensajes_demora[estado]
        # Si es demora grave o turno perdido, agregar link de agenda si está disponible
        if estado in ["demora_grave", "turno_perdido"]:
            link_agenda = contexto.get("link_agenda", "")
            if link_agenda and link_agenda not in mensaje:
                mensaje += f"\n\n{link_agenda}"
        return mensaje
    
    return None


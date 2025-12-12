"""
Base de conocimiento de la barbería.
Cada función devuelve solo el bloque de información necesario según la intención.
"""

# Variables configurables
LINK_RESERVA = "ejemploLinkReserva.com"  # Link de Weybook (configurar)
NUMERO_DERIVACION = ""  # Número para derivar a humano (configurar)


def get_info_servicio() -> str:
    """Información del servicio principal y experiencia del cliente."""
    return """SERVICIO PRINCIPAL DE LA BARBERÍA:

El servicio se basa en cortes personalizados según el rostro del cliente (visagismo). No se hacen cortes genéricos, sino que se analiza:
- Estructura craneal
- Tipo de rostro
- Tipo de cabello
- Volumen, densidad, dirección de crecimiento

A partir de eso se decide qué corte va mejor con la fisonomía y el estilo personal. El objetivo es resaltar los rasgos de cada cliente.

EXPERIENCIA DEL CLIENTE:

Además del corte, cuidamos que cada visita sea cómoda y relajada.
Trabajamos solo con turnos para que no tengas que esperar: llegás y te atendemos.
Mientras esperás o terminás tu corte, podés tomarte un café tranquilo, charlar, estar en un ambiente piola, sin apuros.
Queremos que te sientas como en casa."""


def get_info_diferencial() -> str:
    """Diferencial del servicio."""
    return """DIFERENCIAL DEL SERVICIO:

Cortes basados en visagismo: analizamos el rostro y creamos un corte a medida. Además, trabajamos el styling con productos y herramientas para que el cliente se vea como quiere.

Trabajamos solo con turnos para que no tengas que esperar: llegás y te atendemos.
Mientras esperás o terminás tu corte, podés tomarte un café tranquilo, charlar, estar en un ambiente piola, sin apuros.
Queremos que te sientas como en casa."""


def get_info_precios() -> str:
    """Información sobre precios."""
    return """PRECIOS:

Los precios varían según el tipo de corte y servicio. Te paso la lista o te asesoro según lo que estés buscando.

Para conocer los precios exactos, podés consultar cuando reserves tu turno o preguntarme por un servicio específico."""


def get_info_barba() -> str:
    """Información sobre servicios de barba."""
    return """SERVICIOS DE BARBA:

Sí, se realizan trabajos de barba, también en base al tipo de rostro.

Al igual que con los cortes, analizamos tu tipo de rostro y barba para crear un estilo que te quede perfecto."""


def get_info_niños_mujeres() -> str:
    """Información sobre si atienden niños o mujeres."""
    return """ATENCIÓN A NIÑOS Y MUJERES:

Según el enfoque del local. Si solo es barbería masculina, responder cortésmente. Si también se atiende, aclararlo.

(Nota: Esta información debe configurarse según las políticas del local)"""


def get_info_productos_lc() -> str:
    """Información sobre productos exclusivos LC."""
    return """PRODUCTOS EXCLUSIVOS LC:

También se venden productos de la marca LC para mantener el corte perfecto todos los días.

PRODUCTOS DISPONIBLES (Valor: $500 cada uno):

1. Cera modeladora brillo:
   - Para pelos más porosos y gruesos a los cuales les falta brillo y son muy opacos
   - Ideal para peinar cortes más clásicos

2. Cera en polvo:
   - Para darle más textura al pelo
   - Ideal para pelo lacio y dar volumen

3. Cera mate:
   - Un efecto más cremoso que la cera en polvo
   - También genera ese efecto opaco y de textura
   - Ideal para pelos más lacios para generar efecto de textura

4. Cera mate brillo:
   - Similar a la cera mate pero aporta un poco más de brillo que la cera en polvo

BENEFICIOS:
- Te ayudan a mantener la forma, volumen y textura del corte día a día
- Son productos que usamos en la barbería y que recomendamos porque dan resultado

CÓMO COMPRARLOS:
- Reservar el producto para retirarlo en la barbería
- Consultar stock
- Derivar si quiere info más detallada de uso o precios"""


def get_info_visagismo_redondo() -> str:
    """Información sobre visagismo para rostro redondo."""
    return """VISAGISMO - ROSTRO REDONDO:

Características:
- Mejillas anchas
- Contornos suaves
- Poca definición en mandíbula

Objetivo:
- Alargar el rostro y generar ángulos, ya sea con la barba o contornos

Recomendaciones:
- Evitar volumen en los laterales (puede servir en casos puntuales)
- Volumen arriba (pompadour, quiff o french crop texturizado)
- Degradados altos (puede variar dependiendo el cliente)
- Barba corta o líneas rectas para estilizar"""


def get_info_visagismo_cuadrado() -> str:
    """Información sobre visagismo para rostro cuadrado."""
    return """VISAGISMO - ROSTRO CUADRADO:

Características:
- Mandíbula marcada
- Frente ancha

Objetivo:
- Suavizar o marcar según el estilo

Recomendaciones:
- Fades medios o bajos
- Textura arriba sin mucho volumen
- Barba prolija o para afinar"""


def get_info_visagismo_ovalado() -> str:
    """Información sobre visagismo para rostro ovalado."""
    return """VISAGISMO - ROSTRO OVALADO:

Características:
- Proporciones equilibradas

Objetivo:
- Mantener la armonía

Recomendaciones:
- Casi todos los estilos funcionan
- Evitar flequillo cerrado
- Fades bajos o medios"""


def get_info_visagismo_alargado() -> str:
    """Información sobre visagismo para rostro alargado/rectangular."""
    return """VISAGISMO - ROSTRO ALARGADO O RECTANGULAR:

Características:
- Más largo que ancho

Objetivo:
- Acortar visualmente

Recomendaciones:
- No mucho volumen arriba (a veces se puede estirar el rostro)
- Volumen en laterales
- Barbas completas o tipo "tres días" """


def get_info_visagismo_diamante() -> str:
    """Información sobre visagismo para rostro diamante."""
    return """VISAGISMO - ROSTRO DIAMANTE:

Características:
- Pómulos anchos
- Frente y mentón angostos

Objetivo:
- Equilibrar parte superior e inferior

Recomendaciones:
- Volumen moderado arriba y a los lados
- Evitar rapados extremos
- Barba que ensanche mandíbula"""


def get_info_visagismo_triangular() -> str:
    """Información sobre visagismo para rostro triangular."""
    return """VISAGISMO - ROSTRO TRIANGULAR (BASE ANCHA):

Características:
- Mandíbula más ancha que la frente

Objetivo:
- Compensar proporciones

Recomendaciones:
- Volumen arriba
- No cortar mucho los laterales
- Barba recortada"""


def get_info_visagismo_entradas() -> str:
    """Información sobre visagismo para entradas o calvicie incipiente."""
    return """VISAGISMO - ENTRADAS O CALVICIE INCIPIENTE:

Características:
- Entradas pronunciadas o pérdida frontal

Objetivo:
- Disimular

Recomendaciones:
- Fade alto: sacar masa de los laterales para que parezca que hay más pelo arriba
- Peinados hacia adelante (crop fringe)
- Textura arriba
- Evitar exponer la frente"""


def get_info_faq() -> str:
    """Preguntas frecuentes generales."""
    return """PREGUNTAS FRECUENTES:

¿Cuál es el diferencial?
Cortes basados en visagismo: analizamos el rostro y creamos un corte a medida. Además, trabajamos el styling con productos y herramientas para que el cliente se vea como quiere.

¿Atienden con turno?
Sí, solo con turno. El bot debe derivar a link de turnos o pedir día y horario de preferencia.

¿Precios?
Los precios varían según el tipo de corte y servicio. Te paso la lista o te asesoro según lo que estés buscando.

¿Hacen barbas?
Sí, se realizan trabajos de barba, también en base al tipo de rostro.

¿Trabajan con niños o mujeres?
Según el enfoque del local. Si solo es barbería masculina, responder cortésmente. Si también se atiende, aclararlo."""


def get_info_cortes() -> str:
    """Información general sobre cortes."""
    return """INFORMACIÓN SOBRE CORTES:

El servicio se basa en cortes personalizados según el rostro del cliente (visagismo). No se hacen cortes genéricos, sino que se analiza:
- Estructura craneal
- Tipo de rostro
- Tipo de cabello
- Volumen, densidad, dirección de crecimiento

A partir de eso se decide qué corte va mejor con la fisonomía y el estilo personal. El objetivo es resaltar los rasgos de cada cliente.

Trabajamos solo con turnos para que no tengas que esperar: llegás y te atendemos."""


def get_info_por_intencion(intencion: str) -> str:
    """
    Obtiene la información relevante según la intención detectada.
    
    Args:
        intencion: Nombre de la intención
        
    Returns:
        String con la información relevante o string vacío si no hay match
    """
    mapeo = {
        "turnos": get_info_servicio,
        "cortes": get_info_cortes,
        "diferencial": get_info_diferencial,
        "precios": get_info_precios,
        "barba": get_info_barba,
        "productos_lc": get_info_productos_lc,
        "visagismo_redondo": get_info_visagismo_redondo,
        "visagismo_cuadrado": get_info_visagismo_cuadrado,
        "visagismo_ovalado": get_info_visagismo_ovalado,
        "visagismo_alargado": get_info_visagismo_alargado,
        "visagismo_diamante": get_info_visagismo_diamante,
        "visagismo_triangular": get_info_visagismo_triangular,
        "visagismo_entradas": get_info_visagismo_entradas,
        "preguntas_frecuentes": get_info_faq,
        "niños_mujeres": get_info_niños_mujeres,
    }
    
    funcion = mapeo.get(intencion)
    if funcion:
        return funcion()
    
    return ""

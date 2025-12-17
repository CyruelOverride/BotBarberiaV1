from Models.chat import Chat


def crear_bot_instancia():
    """
    ⚠️ ADVERTENCIA: Esta función crea una sesión de DB que nunca se cierra.
    Solo usar para testing rápido. En producción, usar webhook_server.py
    que maneja las sesiones correctamente.
    """
    bot = Chat()
    
    return bot  


# ⚠️ Esta sesión permanece abierta - solo para testing
bot = crear_bot_instancia()


if __name__ == "__main__":
    print("Bot gordura ok")
    print(f" Estado del bot: {bot}")

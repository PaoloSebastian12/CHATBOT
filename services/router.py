from services.agent import ejecutar_agente

def answer(mensaje, empresa, numero):
    return ejecutar_agente(numero, empresa, mensaje )
import time
import threading
from collections import deque
from services.tools import buscar_modo_en_sheet, actualizar_sheet

memory_store = {}
lock = threading.Lock()

EXPIRATION_TIME = 6 * 60 * 60  # 6 horas
MAX_USERS = 1000
MAX_MENSAJES = 10  # cantidad de mensajes por usuario

TTL_AUTO = 120
TTL_HUMANO = 15 #600

def obtener_modo(numero):
    if numero not in memory_store:
        guardar_interaccion(numero, "user", "")

    with lock:
        data = memory_store[numero]
        ahora = time.time()

        ttl = TTL_AUTO if data["modo"] == "AUTO" else TTL_HUMANO

        if ahora - data["last_mode_check"] < ttl:
            return data["modo"]

    modo_sheet = buscar_modo_en_sheet(numero)

    with lock:
        memory_store[numero]["modo"] = modo_sheet
        memory_store[numero]["last_mode_check"] = time.time()

    return modo_sheet

def cambiar_modo(numero, nuevo_modo):
    actualizar_sheet(numero, nuevo_modo)

    with lock:
        if numero in memory_store:
            memory_store[numero]["modo"] = nuevo_modo
            memory_store[numero]["last_mode_check"] = time.time()

def guardar_interaccion(numero, role, mensaje):
    if role not in ("user", "assistant"):
        raise ValueError("role inválido")

    with lock:
        limpiar_expirados()
        if numero not in memory_store:
            if len(memory_store) >= MAX_USERS:
                eliminar_mas_antiguo()

            memory_store[numero] = {
                "historial": deque(maxlen=MAX_MENSAJES),
                "last_update": time.time(),
                "modo": "AUTO",
                "last_mode_check": 0}

        data = memory_store[numero]

        data["historial"].append({
            "role": role,
            "content": mensaje
        })
        print("a data es :", data)
        data["last_update"] = time.time()

def obtener_historial(numero):
    with lock:
        data = memory_store.get(numero)

        if not data:
            return []

        if time.time() - data["last_update"] > EXPIRATION_TIME:
            del memory_store[numero]
            return []
        print("obtener_historial data es :", data["historial"])
        return list(data["historial"])


def limpiar_expirados():
    ahora = time.time()

    for numero in list(memory_store.keys()):
        if ahora - memory_store[numero]["last_update"] > EXPIRATION_TIME:
            del memory_store[numero]


def eliminar_mas_antiguo():
    usuario_mas_antiguo = min(
        memory_store,
        key=lambda k: memory_store[k]["last_update"]
    )
    del memory_store[usuario_mas_antiguo]
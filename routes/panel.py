from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from services.tools import iniciar_google
from services.memory import cambiar_modo,guardar_interaccion,obtener_historial
from routes.webhook import enviar_texto

router = APIRouter()

class RespuestaInput(BaseModel):
    numero: str
    mensaje: str

class ModoInput(BaseModel):
    numero: str
    modo: str

@router.get("/panel", response_class=HTMLResponse)
async def panel():
    with open("templates/panel.html", "r", encoding="utf-8") as f:
        return f.read()
# -------------------------
# LEER CHATS DESDE SHEET
# -------------------------
@router.get("/chats")
def obtener_chats():
    sheet = iniciar_google()

    data = sheet.get_all_records()

    chats = []

    for row in data:
        chats.append({
            "numero": row.get("Numero"),
            "mensaje": row.get("Ultimo Mensaje"),
            "modo": row.get("Modo"),
            "estado": row.get("Estado")
        })

    return chats

# -------------------------
# RESPUESTA ASESOR
# -------------------------
@router.post("/responder")
async def responder(data: RespuestaInput):
    numero = data.numero
    mensaje = data.mensaje

    # 📤 enviar por WhatsApp
    await enviar_texto(numero, mensaje)

    # 🧠 guardar en memoria (historial)
    guardar_interaccion(numero, "assistant", mensaje)

    # 🔥 mantener modo humano
    cambiar_modo(numero, "HUMANO")

    return {"status": "ok"}
# -------------------------
# CAMBIAR MODO
# -------------------------
@router.post("/modo")
def modo(data: ModoInput):
    cambiar_modo(data.numero, data.modo)
    return {"status": "ok"}
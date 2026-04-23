from fastapi import APIRouter, Response, BackgroundTasks
from services.memory import obtener_modo
from models.empresa import get_empresa_by_numer
from services.router import answer
from utils.text import clean_text
from pydantic import BaseModel, Field
from fastapi import Request
import httpx
from dotenv import load_dotenv
import os
import asyncio
import time

load_dotenv()

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERSION = "v25.0"

router = APIRouter()

async def enviar_documento(numero_cliente, url_documento, nombre_archivo,texto=""):
    try:
        url = f"https://graph.facebook.com/{VERSION}/{PHONE_NUMBER_ID}/messages"

        headers = {
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }

        payload = {
            "messaging_product": "whatsapp",
            "to": numero_cliente,
            "type": "document",
            "document": {
                "link": url_documento,
                "filename": nombre_archivo,
                "caption": texto
            }
        }

        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload, headers=headers)

        print("📄 ENVÍO DOCUMENTO:", r.status_code)
        print("📄 RESPUESTA META:", r.text)

    except Exception as e:
        print("❌ Error enviando documento:", str(e))

async def procesar_ia_y_enviar(mensaje_limpio, empresa, numero_cliente):
    try:
        print(f"🤖 Procesando IA para {numero_cliente}...")
        print(f"\n✅ Mensaje del cliente: {mensaje_limpio}\n")
        # Ejecutamos la IA en un hilo separado para que no bloquee el servidor
        respuesta = await asyncio.to_thread(answer, mensaje_limpio, empresa, numero_cliente)
        print(f"\n✅ Respuesta IA: {respuesta}\n")
        if respuesta == "__CATALOGO_VARON__":
            await enviar_documento(
                numero_cliente,
                "https://chatbot-production-fbd9.up.railway.app/static/catalogo_hombre2.pdf",
                "Catalogo Hombre.pdf")
            await enviar_documento(
                numero_cliente,
                "https://chatbot-production-fbd9.up.railway.app/static/catalogo_hombre_dama.pdf",
                "Catalogo Hombre.pdf",
                "👟 En este catalogo compartimos nuestras mejores ofertas para hombres y mujeres.")
            await enviar_documento(
                numero_cliente,
                "https://chatbot-production-fbd9.up.railway.app/static/catalogo_hombre.pdf",
                "Catalogo Hombre.pdf",
                "👟 Te compartimos nuestro catálogo con las actualizaciones mas recientes.\n 🔥 Recuerda que renovamos nuestrostock casi a diario , por lo que te recomendamos visitarnos en nuestra tienda fisica.🎯  Alli encontraras promociones unicas! "
            )
            return
        elif respuesta == "__CATALOGO_DAMA__":
            await enviar_documento(
                numero_cliente,
                "https://chatbot-production-fbd9.up.railway.app/static/catalogo_hombre_dama.pdf",
                "Catalogo Dama.pdf",
                "👟 En este catalogo compartimos nuestras mejores ofertas para hombres y mujeres.")
            await enviar_documento(
                numero_cliente,
                "https://chatbot-production-fbd9.up.railway.app/static/catalogo_dama.pdf",
                "Catalogo Dama.pdf",
                "👟 Te compartimos nuestro catálogo con las actualizaciones mas recientes.\n 🔥 Recuerda que renovamos nuestrostock casi a diario , por lo que te recomendamos visitarnos en nuestra tienda fisica.🎯  Alli encontraras promociones unicas! "
            )
            return
        elif respuesta == "__CATALOGO_NINO__":
            await enviar_documento(
                numero_cliente,
                "https://chatbot-production-fbd9.up.railway.app/static/catalogo_nino.pdf",
                "Catalogo Nino.pdf",
                "👟 Te compartimos nuestro catálogo con las actualizaciones mas recientes.\n 🔥 Recuerda que renovamos nuestrostock casi a diario , por lo que te recomendamos visitarnos en nuestra tienda fisica.🎯  Alli encontraras promociones unicas! "
            )
        elif respuesta == "__CATALOGO_FUTBOL__":
            await enviar_documento(
                numero_cliente,
                "https://chatbot-production-fbd9.up.railway.app/static/catalogo_futbol2.pdf",
                "Catalogo Futbol.pdf",)
            await enviar_documento(
                numero_cliente,
                "https://chatbot-production-fbd9.up.railway.app/static/catalogo_futbol.pdf",
                "Catalogo Futbol.pdf",
                "👟 Te compartimos nuestro catálogo con las actualizaciones mas recientes.\n 🔥 Recuerda que renovamos nuestrostock casi a diario , por lo que te recomendamos visitarnos en nuestra tienda fisica.🎯  Alli encontraras promociones unicas! "
            )
            return
        url = f"https://graph.facebook.com/{VERSION}/{PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": numero_cliente,
            "type": "text",
            "text": {"body": respuesta}
        }
        
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload, headers=headers)
            print("ESTADO ENVÍO META:", r.status_code)
            print("RESPUESTA META:", r.text)

    except Exception as e:
        print(f"❌ Error en el proceso de fondo: {str(e)}")

class WebhookInput(BaseModel):
    from_: str = Field(alias="from")
    to: str
    message: str
    class Config:
        populate_by_name = True

@router.get("/webhook")
async def verify(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("WEBHOOK_VERIFIED")
        return Response(content=challenge, media_type="text/plain")

    return Response(content="Token inválido", status_code=403)

@router.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
        print("MIRA LO QUE LLEGÓ:", data)
        if "messages" not in data["entry"][0]["changes"][0]["value"]:
            return {"status": "ok"}
        message_obj = data["entry"][0]["changes"][0]["value"]["messages"][0]

        mensaje_timestamp = int(message_obj.get("timestamp", 0))
        tiempo_actual = int(time.time())
        if (tiempo_actual - mensaje_timestamp) > 400:
            print("⏳ Mensaje viejo detectado (Servidor dormido). Ignorando para evitar respuestas fantasma.")
            return {"status": "ok"}

        numero_cliente = message_obj["from"]
        if message_obj["type"] != "text":
            return {"status": "ignored"}
        mensaje = message_obj["text"]["body"]

        numero_empresa = data["entry"][0]["changes"][0]["value"]["metadata"]["display_phone_number"]
        print(f"Buscando empresa con número: {numero_empresa}")
        empresa = get_empresa_by_numer(numero_empresa)
        print(f"Resultado búsqueda empresa: {empresa}")
        if not empresa:
            print("❌ No se encontró la empresa. Abortando envío.")
            return {"reply": "Empresa no configurada"}
        modo = obtener_modo(numero_cliente)
        print("NUMERO:", numero_cliente)
        print("MODO:", modo)
        if modo == "HUMANO":
            print("👨‍💼 Chat en modo humano. IA bloqueada.")
            return {"status": "modo humano"}
        mensaje = clean_text(mensaje)
        background_tasks.add_task(procesar_ia_y_enviar, mensaje, empresa, numero_cliente)
        return {"status": "ok"}
    except Exception as e:
        print("ERROR:", str(e))
        return {"status": "error", "message": str(e)}
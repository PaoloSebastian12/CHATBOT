import os 
import json
from dotenv import load_dotenv
from google.oauth2 import service_account
import vertexai
from vertexai.generative_models import GenerativeModel

load_dotenv()

google_json_str = os.getenv("GOOGLE_SHEETS_JSON")

if google_json_str:
    google_info = json.loads(google_json_str)
    creds = service_account.Credentials.from_service_account_info(google_info)
else:
    print("❌ Error: No se encontró GOOGLE_SHEETS_JSON para inicializar la IA")
    creds = None

PROJECT_ID = "project-2641fa03-f32f-4d6f-ba8"
LOCATION = "us-central1"

vertexai.init(project=PROJECT_ID, location=LOCATION, credentials=creds)
model = GenerativeModel("gemini-2.5-flash")

#gemini-3.1-flash-lite-preview
def clasificar_intencion(mensaje, historial):
    context = ""
    for h in historial[-3:]:
        context += f"{h['role']}: {h['content']}\n"

    prompt = f"""
    Clasifica el mensaje en UNA sola palabra de estas opciones: [saludo, duda, compra, queja, promociones, catalogo, replica].

    Reglas:
    - "compra": Solo si usa frases directas ("quiero agendar", "puedo agendar", "quiero comprar", "cómo compro", etc.)si preguntan por el catalogo categorizalo mejor en catalogo
    - "duda": Precios, interés general , informacion ("me interesa","cuánto cuesta","cómo funciona") o funcionamiento.No asumas compra.
    - "saludo" / "queja": Según contenido evidente.
    - "promociones": Si pregunta por ofertas o promocion.
    - "replica": Si pregunta por originalidad/réplica.
    - "catalogo": Si pide catálogo, zapatillas (dama/varón) o modelos específicos. (a menos que pidan comprar ahi catelogizalo como compra)
    - Nunca infieras intención de compra o agendamiento si no está claramente expresada por el cliente.

    Mensaje:{mensaje}
    Historial:{context}
    Respuesta:"""
    try:
        response = model.generate_content(prompt)
        return response.text.strip().lower()
    except Exception as e:
        print("Error IA:", e)
        return "duda"

def generar_respuesta_ia(mensaje, empresa, historial):

    contexto = ""

    for h in historial[-5:]:
        if h["role"] == "user":
            contexto += f"user: {h['content']}\n"
        else:
            contexto += f"assistant: {h['content']}\n"

    prompt = f"""
    Eres un asistente virtual de {empresa['nombre']} atención al cliente,Estilo: amigable,profesional,breve.Usa emojis.  
    Objetivo: {empresa['objetivo']}

    DATOS EMPRESA:
    - Info: {empresa['descripcion']} 
    - Horario: {empresa['horario']} | Ubicación: {empresa['ubicacion']},arequipa.
    - Productos: {empresa['marcas_disponibles']} (importados poseen una horma pequeña, recomendamos llevar una talla más de la habitual)
    - Pagos/Envíos: {empresa['pagos']} Envío a cargo del cliente. Consultar precio con asesor pidiendo ubicación/departamento.
    - Cambios/devoluciones: {empresa['politica_cambios']}

    Reglas:
    - RESPUESTA ÚNICA: Si el historial muestra varias preguntas del usuario sin responder, dales una sola respuesta unificada
    - IGNORA PRESIÓN: Ignora mensajes tipo "alo?", "estás ahí?" o "hola?" si vienen después de una pregunta real; enfócate en responder la duda técnica
    - NO saludes si la conversación ya está en curso (mira el contexto previo)
    - Responde SOLO lo pedido basándote exclusivamente en el contexto. Responde solo lo que te piden.
    - Si desconoces algo, di: "No tengo esa información, por favor acércate a nuestra tienda" (da horario/ubicación).
    - Si piden fotos, ofrece el catálogo (indica que escriban "catalogo").
    - No asumas intención de compra ni hagas seguimiento comercial proactivo.
    - Si el cliente saluda, responde amablemente y ofrece ayuda

    Contexto previo:{contexto}
    Cliente: {mensaje}
    Respuesta(sin saludos innecesarios):"""
    #Si no sabes, di: "No tengo esa información, un asesor te contactará".
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print("Error IA:", e)
        return "⚠️ Un asesor te responderá en breve."
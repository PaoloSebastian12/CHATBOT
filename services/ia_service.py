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
    Clasifica el siguiente mensaje en UNA palabra:
    Reglas:
    - Si el cliente pregunta por precios, clasificalo como "duda"
    - Solo utiliza explicitamente las palabras "agendar" o "comprar" cuando el cliente lo solicite de forma explícita.
    - Se considera solicitud explícita cuando el cliente usa frases directas como: "quiero agendar", "puedo agendar", "quiero comprar", "cómo compro", etc.(si preguntan por el catalogo categorizalo mejor en catalogo)
    - Si el cliente únicamente muestra interés, hace preguntas o pide información (por ejemplo: "me interesa", "cuánto cuesta", "cómo funciona"), debes clasificarlo como "duda" y NO asumir intención de agendar o comprar.
    - Nunca infieras intención de compra o agendamiento si no está claramente expresada por el cliente.
    - Categoriza como promociones si el cliente pregunta por alguna promocion.
    - Solo si preguntan si es replica o si son originales pon replica

    Opciones:
    - saludo
    - duda
    - compra o agendamiento
    - queja
    - promociones
    - catalogo
    - replica

    Mensaje:
    {mensaje}

    Historial:
    {context}

    Respuesta:
    """
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
    Eres un asistente virtual de atención al cliente ,Estilo: amigable y profesional. Use emojis y brinda solo la informacion que te pide el cliente.  

    Tu objetivo es {empresa['objetivo']}.

    Empresa: {empresa['nombre']}
    Descripción: {empresa['descripcion']}
    Horario: {empresa['horario']}
    Ubicación: {empresa['ubicacion']}

    servicios y/o productos:
    {empresa['marcas_disponibles']} ( todos los que son importados poseen una horma pequeña, recomendamos llevar una talla más de la habitual)

    Conversación previa:
    {contexto}

    Pagos: (si se aceptan envios sin Sin embargo un asesor se contactara para calcular el precio , pidele su ubicacion y si aceptan a provincioas y a otros departamentos del peru )
    (indica tambien que el costo de envio es asumido por el cliente)
    {empresa['pagos']}

    Politicas de cambio y devolución:
    {empresa['politica_cambios']}

    Reglas:
    - Si el cliente saluda, responde amablemente y ofrece ayuda
    - No asumas que quiere comprar
    - No generes mensajes de seguimiento comercial a menos que el cliente lo indique
    - No utilices conocimientos externos ni supongas detalles que no estén escritos arriba. Tu respuesta debe estar fundamentada al 100% en el contexto brindado.
    - Reformula la información de manera natural, clara y atractiva.Responde solo lo que te piden.
    - Si no sabes, di: "No tengo esa información, por acercate a nuestras tiendas fisicas".(brindas ubicacion y horario)
    - Cuando te pidan foto pregunta si quieren ver el catalogo (diles que escriban catalogo para verlo)

    Cliente: {mensaje}
    Respuesta:
    """
    #Si no sabes, di: "No tengo esa información, un asesor te contactará".
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print("Error IA:", e)
        return "⚠️ Un asesor te responderá en breve."
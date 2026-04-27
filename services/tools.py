import base64
import datetime
from email.mime.text import MIMEText
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from thefuzz import fuzz
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

client = None
sheet_leads = None

def extraer_dia_semana(fecha) -> str:
    dias = {
        0: "Lunes", 1: "Martes", 2: "Miércoles",
        3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"
    }
    return dias[fecha.weekday()]

def extraer_turno(fecha) -> str:
    hora = fecha.hour
    if 6 <= hora < 12:
        return "Mañana"
    elif 12 <= hora < 18:
        return "Tarde"
    elif 18 <= hora < 23:
        return "Noche"
    else:
        return "Madrugada"

def contar_intercambios(historial: list) -> int:
    return len(historial)

def extraer_pais(numero: str) -> str:
    numero = str(numero).strip().lstrip("+")
    prefijos = {
        "54": "Argentina",
        "51": "Perú",
        "55": "Brasil",
        "56": "Chile",
        "57": "Colombia",
        "58": "Venezuela",
        "591": "Bolivia",
        "593": "Ecuador",
        "595": "Paraguay",
        "598": "Uruguay",
        "502": "Guatemala",
        "503": "El Salvador",
        "504": "Honduras",
        "505": "Nicaragua",
        "506": "Costa Rica",
        "507": "Panamá",
        "52": "México",
        "1":  "EE.UU. / Canadá",
        "34": "España",
    }
    # Primero intenta prefijos de 3 dígitos, luego 2
    for largo in (3, 2, 1):
        clave = numero[:largo]
        if clave in prefijos:
            return prefijos[clave]
    return "Desconocido"

def iniciar_google():
    global client, sheet_leads

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    google_info = json.loads(os.getenv("GOOGLE_SHEETS_JSON"))

    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        google_info, scope
    )

    client = gspread.authorize(creds)

    archivo = client.open("Leads")

    try:
        sheet_leads = archivo.worksheet("Leads")
    except:
        sheet_leads = archivo.sheet1
    
    headers = [
    "ID",
    "Modo",
    "Numero",
    "Ultimo Mensaje",
    "Historial",
    "Servicio",
    "Empresa",
    "Dia",
    "Hora",
    "Estado",
    "pais",
    "dia_semana",
    "turno",
    "intercambios"]

    fila1 = sheet_leads.row_values(1)

    if not fila1:
        sheet_leads.append_row(headers)
    if sheet_leads:
        return sheet_leads


    return sheet_leads

def buscar_modo_en_sheet(numero):
    try:
        sheet = iniciar_google()
        columna_numeros = sheet.col_values(3)

        for i, valor in enumerate(columna_numeros[1:], start=2):
            if str(valor).strip() == str(numero):
                modo = sheet.cell(i, 2).value
                return modo if modo else "AUTO"

        return "AUTO"

    except Exception as e:
        print("❌ Error buscando modo:", e)
        return "AUTO"

def identificar_servicio(mensaje,empresa):
    servicios = empresa.get("categorias", {}).keys()

    mensaje = mensaje.lower()
    palabras = mensaje.split()

    encontrados = set()

    for servicio in servicios:
        nombre = servicio.lower()

        if nombre in mensaje:
            encontrados.add(servicio)
            continue

        for palabra in palabras:
            if fuzz.partial_ratio(nombre, palabra) >= 80:
                encontrados.add(servicio)
                break

    return ", ".join(encontrados) if encontrados else "No identificado"
    
def registrar_lead(numero, mensaje, empresa,historial, modo="AUTO"):
    try:
        sheet = iniciar_google()

        fecha = datetime.datetime.now()

        contexto = " | ".join(
            h["content"] for h in historial[-3:]
        )

        servicios = identificar_servicio(mensaje, empresa)
        pais = extraer_pais(numero)

        dia_semana    = extraer_dia_semana(fecha)
        turno         = extraer_turno(fecha)
        intercambios  = contar_intercambios(historial)

        columna_numeros = sheet.col_values(3)

        fila_existente = None

        for i, valor in enumerate(columna_numeros[1:], start=2):
            if str(valor).strip() == str(numero):
                fila_existente = i
                break
        
        print("Fila encontrada:", fila_existente)
        print("Número recibido:", numero)

        if fila_existente:

            sheet.update(f"D{fila_existente}:J{fila_existente}",[[
                mensaje,
                contexto,
                servicios,
                empresa["nombre"],
                fecha.strftime("%Y-%m-%d"),
                fecha.strftime("%H:%M"),
                "Actualizado",
                pais,
                dia_semana,                  
                turno,                       
                intercambios 
            ]])

            print("✅ Cliente actualizado")

        else:

            fila = [
                len(sheet.col_values(1)),   # ID rápido
                modo,
                numero,
                mensaje,
                contexto,
                servicios,
                empresa["nombre"],
                fecha.strftime("%d-%m-%Y"),
                fecha.strftime("%H:%M"),
                "Pendiente",
                pais,
                dia_semana,                  
                turno,                       
                intercambios 
            ]

            sheet.append_row(fila)

            print("✅ Lead guardado Nuevo cliente")

    except Exception as e:
        print("❌ Error lead:", e)

def send_alert(email,mensaje, empresa, numero,historial):
    try:
        token_data = json.loads(os.getenv("GMAIL_TOKEN_JSON"))
        creds = Credentials.from_authorized_user_info(token_data)
        service = build('gmail', 'v1', credentials=creds)

        contexto = ""

        for h in historial[-6:]:  # últimos 6 mensajes
            rol = "Cliente" if h["role"] == "user" else "Bot"
            contexto += f"\n{rol}: {h['content']}\n"

        cuerpo = f"""
        🔥 NUEVO LEAD DETECTADO

        Empresa: {empresa['nombre']}
        Cliente: {numero}

        🧾 --- Resumen del chat ---:
        {contexto}

        📩 Último mensaje:
        {mensaje}"""

        msg = MIMEText(cuerpo)
        msg['subject'] = 'Nuevo Lead Interesado'
        msg['To'] = email
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId='me', body={'raw': raw}).execute()
        print(f"✅ Alerta enviada con éxito a {email}")
    except Exception as e:
        print("Error al enviar email:", (e))

    print(f"📧 Enviando alerta a {email}: {mensaje}")

def actualizar_sheet(numero, nuevo_modo):
    try:
        sheet = iniciar_google()

        columna_numeros = sheet.col_values(3)

        for i, valor in enumerate(columna_numeros[1:], start=2):
            if str(valor).strip() == str(numero):
                sheet.update_cell(i, 2, nuevo_modo)
                print(f"✅ {numero} cambiado a {nuevo_modo}")
                return True
        print("⚠️ Número no existe aún. No se actualizó modo.")
        return False

    except Exception as e:
        print("❌ Error actualizando modo:", e)
        return False
    
def seguimiento_asesor(numero, mensaje,respuesta, empresa,historial, modo="AUTO"):
    try:
        sheet = iniciar_google()

        fecha = datetime.datetime.now()

        ultimos = [h["content"] for h in historial[-3:]]
        ultimos.append(f"BOT: {respuesta}")
        contexto = " | ".join(ultimos)

        servicios = identificar_servicio(mensaje, empresa)
        pais = extraer_pais(numero)

        dia_semana    = extraer_dia_semana(fecha)
        turno         = extraer_turno(fecha)
        intercambios  = contar_intercambios(historial)

        columna_numeros = sheet.col_values(3)

        fila_existente = None

        for i, valor in enumerate(columna_numeros[1:], start=2):
            if str(valor).strip() == str(numero):
                fila_existente = i
                break
        
        print("Fila encontrada:", fila_existente)
        print("Número recibido:", numero)

        if fila_existente:

            sheet.update(f"D{fila_existente}:J{fila_existente}",[[
                mensaje,
                contexto,
                servicios,
                empresa["nombre"],
                fecha.strftime("%d-%m-%Y"),
                fecha.strftime("%H:%M"),
                "HABLADO CON ASESOR",
                pais,
                dia_semana,                  
                turno,                       
                intercambios 
            ]])

            print("✅ Cliente actualizado seguimiento asesor!")

        else:

            fila = [
                len(sheet.col_values(1)),   # ID rápido
                modo,
                numero,
                mensaje,
                contexto,
                servicios,
                empresa["nombre"],
                fecha.strftime("%d-%m-%Y"),
                fecha.strftime("%H:%M"),
                "HABLADO CON ASESOR",
                pais,
                dia_semana,                  
                turno,                       
                intercambios 
            ]

            sheet.append_row(fila)

        print("✅ SEGUIMIENTO ASESOR")

    except Exception as e:
        print("❌ Error lead:", e)


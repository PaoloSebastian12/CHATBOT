
import os
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from datetime import datetime
 
# Importar servicios
try:
    from services.tools import iniciar_google
    from services.memory import cambiar_modo, guardar_interaccion, obtener_historial
    from routes.webhook import enviar_texto
    IMPORTS_OK = True
except Exception as e:
    print(f"⚠️  Error importando servicios: {e}")
    IMPORTS_OK = False
 
# ===== SETUP LOGGING =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - PANEL - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
 
# ===== MODELOS =====
class RespuestaInput(BaseModel):
    numero: str = Field(..., min_length=7, max_length=20)
    mensaje: str = Field(..., min_length=1, max_length=4000)
 
class ModoInput(BaseModel):
    numero: str = Field(..., min_length=7, max_length=20)
    modo: str = Field(..., regex="^(AUTO|HUMANO|CATALOGO)$")
 
# ===== ROUTER =====
router = APIRouter(prefix="/panel", tags=["Panel Asesor"])
 
 
# ===== HELPERS =====
def parsear_historial(historial_texto: str) -> list:
    """
    ✅ NUEVO: Parsea el historial en formato texto a lista de mensajes
    
    Formatos soportados:
    - "Cliente: mensaje | Bot: respuesta"
    - "user: mensaje\nassistant: respuesta"
    - "Usuario: mensaje Bot: respuesta"
    """
    if not historial_texto or historial_texto.strip() == "-":
        return []
    
    mensajes = []
    
    # Intentar parsear por diferentes separadores
    lineas = historial_texto.split('\n')
    
    for linea in lineas:
        linea = linea.strip()
        if not linea:
            continue
        
        # Formato: "Cliente: texto" o "User: texto"
        if linea.startswith("Cliente:") or linea.startswith("user:") or linea.startswith("User:"):
            contenido = linea.split(":", 1)[1].strip()
            mensajes.append({
                "role": "user",
                "content": contenido
            })
        # Formato: "Bot: texto" o "Assistant: texto"
        elif linea.startswith("Bot:") or linea.startswith("assistant:") or linea.startswith("Assistant:"):
            contenido = linea.split(":", 1)[1].strip()
            mensajes.append({
                "role": "assistant",
                "content": contenido
            })
    
    return mensajes
 
 
def extraer_numeros_disponibles() -> list:
    """
    ✅ NUEVO: Extrae todos los números disponibles del sheet
    Para usar en dropdown/select
    """
    try:
        logger.info("📞 Extrayendo números disponibles...")
        sheet = iniciar_google()
        
        if not sheet:
            logger.warning("⚠️  Google Sheets no disponible")
            return []
        
        # Obtener todos los registros
        datos = sheet.get_all_records()
        
        numeros = []
        for row in datos:
            numero = row.get("Numero", "")
            if numero and numero not in numeros:  # Sin duplicados
                numeros.append(numero)
        
        logger.info(f"✅ {len(numeros)} números encontrados")
        return sorted(numeros)
    
    except Exception as e:
        logger.error(f"❌ Error extrayendo números: {e}")
        return []
 
 
# ===== ENDPOINTS =====
 
@router.get("/", response_class=HTMLResponse)
async def panel():
    """Retorna la página HTML del panel"""
    try:
        panel_path = os.path.join("templates", "panel.html")
        
        if not os.path.exists(panel_path):
            logger.error(f"❌ panel.html no encontrado en {panel_path}")
            return """
            <html>
            <body style="font-family: Arial; padding: 20px; background: #f0f0f0;">
                <h1>❌ Error</h1>
                <p>No se encontró templates/panel.html</p>
                <p>Ubicación esperada: {}</p>
                <hr>
                <p>Solución:</p>
                <code>mkdir -p templates && cp panel.html templates/panel.html</code>
            </body>
            </html>
            """.format(panel_path)
        
        with open(panel_path, "r", encoding="utf-8") as f:
            logger.info("✅ Panel HTML cargado")
            return f.read()
    
    except Exception as e:
        logger.error(f"❌ Error cargando panel: {e}")
        return f"<html><body><h1>Error:</h1><p>{str(e)}</p></body></html>"
 
 
@router.get("/health")
async def health():
    """Verifica que el panel está funcionando"""
    checks = {
        "panel": "✅ Activo",
        "timestamp": datetime.now().isoformat(),
    }
    
    try:
        sheet = iniciar_google()
        if sheet:
            checks["google_sheets"] = "✅ Conectado"
        else:
            checks["google_sheets"] = "❌ No disponible"
    except Exception as e:
        checks["google_sheets"] = f"❌ {str(e)[:50]}"
    
    logger.info(f"🏥 Health: {checks}")
    return checks
 
 
@router.get("/chats")
async def obtener_chats():
    """
    ✅ MEJORADO: Obtiene SOLO chats con estado "Pendiente Asesor"
    Retorna formato mejorado
    """
    try:
        logger.info("📊 Obteniendo chats pendientes...")
        
        sheet = iniciar_google()
        if not sheet:
            logger.error("❌ Google Sheets no disponible")
            raise HTTPException(status_code=500, detail="Google Sheets no disponible")
        
        # Obtener todos los registros
        datos = sheet.get_all_records()
        logger.info(f"✅ {len(datos)} registros obtenidos de Google Sheets")
        
        chats = []
        
        for i, row in enumerate(datos):
            try:
                # ✅ FILTRO: Solo "Pendiente Asesor"
                estado = row.get("Estado", "")
                if estado != "Pendiente Asesor":
                    continue  # Saltar si no es pendiente
                
                numero = row.get("Numero", "")
                
                chat = {
                    "id": i,
                    "numero": numero,
                    "mensaje": row.get("Ultimo Mensaje", "-")[:100],  # Truncar
                    "modo": row.get("Modo", "?"),
                    "estado": estado,
                    "hora": row.get("Hora", "-"),
                    "empresa": row.get("Empresa", "-"),
                    "servicio": row.get("Servicio", "-"),
                    "intercambios": row.get("Intercambios", 0),
                    # ✅ NUEVO: Historial parseado
                    "historial": parsear_historial(row.get("Historial", ""))
                }
                chats.append(chat)
            
            except Exception as e:
                logger.warning(f"⚠️  Error procesando fila {i}: {e}")
                continue
        
        logger.info(f"✅ {len(chats)} chats pendientes procesados")
        
        if len(chats) == 0:
            logger.warning("⚠️  Sin chats pendientes")
        
        return {
            "status": "ok",
            "count": len(chats),
            "chats": chats
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en obtener_chats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
 
 
@router.get("/numeros")
async def obtener_numeros():
    """
    ✅ NUEVO: Retorna lista de números para dropdown/select
    """
    try:
        logger.info("📞 Obteniendo lista de números...")
        numeros = extraer_numeros_disponibles()
        
        return {
            "status": "ok",
            "count": len(numeros),
            "numeros": numeros
        }
    
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
 
 
@router.get("/chat/{numero}")
async def ver_chat(numero: str):
    """
    ✅ MEJORADO: Obtiene historial completo de un cliente
    """
    try:
        logger.info(f"📝 Obteniendo chat de {numero}...")
        
        sheet = iniciar_google()
        if not sheet:
            raise HTTPException(status_code=500, detail="Google Sheets no disponible")
        
        # Buscar en Google Sheets
        datos = sheet.get_all_records()
        
        for row in datos:
            if str(row.get("Numero", "")).strip() == str(numero).strip():
                # Parsear historial
                historial = parsear_historial(row.get("Historial", ""))
                
                logger.info(f"✅ {len(historial)} mensajes encontrados para {numero}")
                
                return {
                    "numero": numero,
                    "historial": historial,
                    "count": len(historial),
                    "estado": row.get("Estado", "-"),
                    "empresa": row.get("Empresa", "-"),
                    "servicio": row.get("Servicio", "-")
                }
        
        logger.warning(f"⚠️  Cliente {numero} no encontrado")
        return {
            "numero": numero,
            "historial": [],
            "count": 0,
            "mensaje": "Cliente no encontrado"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
 
 
@router.post("/responder")
async def responder(data: RespuestaInput):
    """
    ✅ MEJORADO: Envía respuesta y la guarda
    """
    numero = data.numero
    mensaje = data.mensaje
    
    logger.info(f"📨 Respuesta a {numero}: {mensaje[:50]}...")
    
    try:
        # Validar
        if not numero or len(numero) < 7:
            raise ValueError("Número inválido")
        
        if not mensaje:
            raise ValueError("Mensaje vacío")
        
        # Enviar por WhatsApp
        logger.info(f"   → Enviando a WhatsApp...")
        try:
            await enviar_texto(numero, mensaje)
            logger.info(f"   ✅ Enviado a WhatsApp")
        except Exception as e:
            logger.error(f"   ❌ Error WhatsApp: {e}")
            raise HTTPException(status_code=500, detail=f"Error WhatsApp: {str(e)}")
        
        # Guardar en historial
        logger.info(f"   → Guardando en historial...")
        try:
            guardar_interaccion(numero, "assistant", mensaje)
            logger.info(f"   ✅ Guardado en historial")
        except Exception as e:
            logger.warning(f"   ⚠️  Error historial: {e}")
        
        # Cambiar modo a HUMANO (asesor respondiendo)
        logger.info(f"   → Cambiar modo a HUMANO...")
        try:
            cambiar_modo(numero, "HUMANO")
            logger.info(f"   ✅ Modo HUMANO")
        except Exception as e:
            logger.warning(f"   ⚠️  Error modo: {e}")
        
        logger.info(f"✅ Respuesta enviada a {numero}")
        
        return {
            "status": "ok",
            "numero": numero,
            "mensaje": "Respuesta enviada correctamente"
        }
    
    except ValueError as e:
        logger.error(f"❌ Validación: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
 
 
@router.post("/modo")
async def cambiar_modo_endpoint(data: ModoInput):
    """
    Cambia el modo de un usuario
    """
    numero = data.numero
    nuevo_modo = data.modo
    
    logger.info(f"🔄 Cambiando modo de {numero} a {nuevo_modo}...")
    
    try:
        cambiar_modo(numero, nuevo_modo)
        logger.info(f"✅ Modo: {numero} → {nuevo_modo}")
        
        return {
            "status": "ok",
            "numero": numero,
            "modo": nuevo_modo
        }
    
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
 
 
if __name__ == "__main__":
    logger.info("🧪 Testing panel.py")
    logger.info(f"   Imports: {'✅' if IMPORTS_OK else '❌'}")
from fastapi import FastAPI
from routes.webhook import router as webhook_router
from fastapi.staticfiles import StaticFiles
from routes.panel import router as panel_router

app = FastAPI()

@app.get("/")
async def home():
    return {"status": "ok", "server": "activo"}

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(webhook_router)

app.include_router(panel_router)
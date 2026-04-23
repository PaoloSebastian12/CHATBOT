from fastapi import FastAPI
from routes.webhook import router as webhook_router
from fastapi.staticfiles import StaticFiles

app = FastAPI()

@app.get("/")
async def home():
    return {"status": "ok", "server": "activo"}

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(webhook_router)
"""
╔══════════════════════════════════════════════════════════════╗
║          J.A.R.V.I.S  v3.0  —  Cloud Server                  ║
║   FastAPI + WebSocket + Edge-TTS + Multi-Provider AI          ║
║   By Ashish Laheri                                            ║
╚══════════════════════════════════════════════════════════════╝

Run locally:   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
Docker:        docker compose up
"""

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api.routes import router as api_router
from api.websocket_handler import handle_websocket
import os

app = FastAPI(title="J.A.R.V.I.S.", version="3.0")

# ── API routes ──────────────────────────────────────
app.include_router(api_router)

# ── WebSocket endpoint ──────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await handle_websocket(ws)

# ── Serve the PWA frontend ─────────────────────────
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    async def root():
        return FileResponse(os.path.join(static_dir, "index.html"))

    @app.get("/manifest.json")
    async def manifest():
        return FileResponse(os.path.join(static_dir, "manifest.json"))

    @app.get("/sw.js")
    async def service_worker():
        return FileResponse(os.path.join(static_dir, "sw.js"), media_type="application/javascript")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

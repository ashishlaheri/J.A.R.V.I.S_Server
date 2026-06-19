"""
╔══════════════════════════════════════════════════════════════╗
║          J.A.R.V.I.S  v3.1  —  Cloud Server                  ║
║   FastAPI + WebSocket + Edge-TTS + Multi-Provider AI          ║
║   By Ashish Laheri                                            ║
╚══════════════════════════════════════════════════════════════╝

Run locally:   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
Docker:        docker compose up
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api.routes import router as api_router
from api.websocket_handler import handle_websocket, broadcast_notification
from skills import reminders
import os
import asyncio


# ── Reminder Scheduler ─────────────────────────────
async def reminder_checker():
    """Background task that checks for due reminders every 60 seconds."""
    while True:
        try:
            due = await reminders.get_due_reminders()
            for r in due:
                await broadcast_notification(
                    "⏰ Reminder",
                    r["text"]
                )
                print(f"[REMINDER] Fired: {r['text']}")
        except Exception as e:
            print(f"[REMINDER] Check error: {e}")
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup & shutdown events."""
    # Startup
    print("=" * 55)
    print("  J.A.R.V.I.S. v3.1 — Server Starting")
    print("=" * 55)
    task = asyncio.create_task(reminder_checker())
    print("[SCHEDULER] Reminder checker started (60s interval)")
    yield
    # Shutdown
    task.cancel()
    print("[SCHEDULER] Reminder checker stopped")


app = FastAPI(title="J.A.R.V.I.S.", version="3.1", lifespan=lifespan)

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

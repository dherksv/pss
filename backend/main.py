"""
main.py — FastAPI application entry point
OWNER: Engineer C

This is the API layer. Add routes by importing routers from routes/.
WebSocket endpoint for live genome streaming is here.
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from routes import projects, signals, analysis, sources, alerts
from storage.sqlite_store import init_db

# ── Startup / Shutdown ──────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()          # initialise SQLite tables
    yield
    # cleanup on shutdown if needed

app = FastAPI(
    title="Patient Safety Sentinel API",
    description="Real-time social listening for patient safety signals",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(projects.router,  prefix="/api/projects",  tags=["projects"])
app.include_router(signals.router,   prefix="/api/signals",   tags=["signals"])
app.include_router(analysis.router,  prefix="/api/analysis",  tags=["analysis"])
app.include_router(sources.router,   prefix="/api/sources",   tags=["sources"])
app.include_router(alerts.router,    prefix="/api/alerts",    tags=["alerts"])

# ── WebSocket — live genome feed ─────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)

    async def broadcast(self, data: dict):
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                pass

manager = ConnectionManager()

@app.websocket("/ws/feed")
async def websocket_feed(websocket: WebSocket):
    """Live genome stream — frontend connects here for real-time updates."""
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()   # keep alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/health")
async def health():
    return {"status": "ok"}

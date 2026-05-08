"""
main.py - FastAPI application entry point | OWNER: Engineer C
WebSocket manager for live genome streaming lives here.
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os, json

from routes import projects, signals, analysis, sources, alerts
from storage.sqlite_store import init_db


# ── WebSocket connection manager ──────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


# ── Startup / Shutdown ────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("Database initialised.")
    yield


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Patient Safety Sentinel API",
    description="Real-time social listening for patient safety signals",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip() for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8501"
        ).split(",") if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(signals.router,  prefix="/api/signals",  tags=["signals"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(sources.router,  prefix="/api/sources",  tags=["sources"])
app.include_router(alerts.router,   prefix="/api/alerts",   tags=["alerts"])


# ── WebSocket — live genome feed ──────────────────────────────────────────────
@app.websocket("/ws/feed")
async def websocket_feed(websocket: WebSocket):
    """
    Frontend connects here to receive live genome stream.
    Every processed genome is pushed here by the worker via /internal/broadcast.
    """
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive ping
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ── Internal broadcast endpoint (called by worker.py) ────────────────────────
@app.post("/internal/broadcast")
async def internal_broadcast(genome: dict):
    """
    Worker calls this after processing each genome.
    We push it to all connected dashboard WebSocket clients.
    """
    await manager.broadcast(genome)
    return {"pushed_to": len(manager.active)}


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "connected_clients": len(manager.active)}
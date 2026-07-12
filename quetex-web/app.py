"""
app.py — FastAPI web application.
Serves the dashboard + REST API + WebSocket for real-time updates.
Run: uvicorn app:app --host 0.0.0.0 --port 8000
"""
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config as C
import database as db
from signal_engine import scan_all, scan_one
from data_client import get_price

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("quetex.app")

# ─── Active WebSocket clients ─────────────────────────────────
_ws_clients: list[WebSocket] = []

# ─── Scheduler ────────────────────────────────────────────────
scheduler = AsyncIOScheduler(timezone="UTC")
auto_scan_on = True
last_scan_ts = "Never"
latest_signals: list[dict] = []


async def _broadcast(msg: dict):
    """Send JSON message to all connected WebSocket clients."""
    dead = []
    for ws in _ws_clients:
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in _ws_clients:
            _ws_clients.remove(ws)


async def _do_scan():
    """Core scan logic — called by scheduler and manual trigger."""
    global last_scan_ts, latest_signals
    logger.info("Running signal scan...")
    last_scan_ts = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    await _broadcast({"type": "scan_start", "ts": last_scan_ts})

    signals = await scan_all(force=False, max_results=6)
    latest_signals = signals

    for s in signals:
        sid = db.save(
            asset=s["asset"], direction=s["direction"],
            confidence=s["confidence"], entry_price=s["price"],
            expiry=s["expiry"], timeframe=s["timeframe"],
            pattern=s["pattern"], buy_pct=s["buy_pct"],
            sell_pct=s["sell_pct"], adx=s["adx"]
        )
        s["id"] = sid

    await _broadcast({
        "type":    "signals",
        "signals": signals,
        "ts":      last_scan_ts,
    })
    logger.info("Scan complete: %d signals found", len(signals))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup + shutdown lifecycle."""
    db.init()
    scheduler.add_job(
        _do_scan, "interval", minutes=C.SCAN_INTERVAL,
        id="auto_scan", replace_existing=True
    )
    scheduler.start()
    logger.info("Quetex Web started. Scan interval: %dm", C.SCAN_INTERVAL)
    yield
    scheduler.shutdown()
    logger.info("Quetex Web stopped.")


app = FastAPI(title="Quetex Signal System", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")


# ─── Routes ────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    stats = db.get_stats()
    best  = db.get_best_assets(5)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "stats":   stats,
        "best":    best,
        "assets":  C.ALL_ASSETS,
        "interval": C.SCAN_INTERVAL,
        "min_conf": C.MIN_CONFIDENCE,
        "version": "2.0",
    })


@app.get("/api/scan")
async def api_scan(asset: Optional[str] = None):
    """Trigger manual scan. ?asset=EURUSD-OTC to scan one asset."""
    if asset:
        signals = await scan_one(asset.upper())
    else:
        signals = await scan_all(force=True, max_results=6)
    # Save to DB
    for s in signals:
        sid = db.save(
            s["asset"], s["direction"], s["confidence"], s["price"],
            s["expiry"], s["timeframe"], s.get("pattern",""),
            s.get("buy_pct",0), s.get("sell_pct",0), s.get("adx",0)
        )
        s["id"] = sid
    await _broadcast({"type": "signals", "signals": signals,
                      "ts": datetime.now(timezone.utc).strftime("%H:%M:%S UTC")})
    return JSONResponse({"success": True, "count": len(signals), "signals": signals})


@app.get("/api/signals")
async def api_signals():
    """Return latest signals from this session."""
    return JSONResponse({"signals": latest_signals})


@app.get("/api/history")
async def api_history(limit: int = 20):
    """Return last N signals from database."""
    return JSONResponse({"signals": db.get_recent(limit)})


@app.get("/api/stats")
async def api_stats():
    """Return statistics."""
    return JSONResponse({
        "stats": db.get_stats(),
        "best": db.get_best_assets(5),
        "last_scan": last_scan_ts,
        "auto_scan": auto_scan_on,
    })


@app.post("/api/result/{signal_id}/{result}")
async def api_result(signal_id: int, result: str):
    """Mark signal result: WIN or LOSS."""
    if result.upper() not in ("WIN", "LOSS"):
        raise HTTPException(400, "result must be WIN or LOSS")
    db.mark_result(signal_id, result.upper())
    return JSONResponse({"success": True})


@app.post("/api/auto/{state}")
async def api_auto(state: str):
    """Toggle auto-scan: /api/auto/on or /api/auto/off"""
    global auto_scan_on
    if state == "on":
        auto_scan_on = True
        if not scheduler.get_job("auto_scan"):
            scheduler.add_job(_do_scan, "interval", minutes=C.SCAN_INTERVAL,
                              id="auto_scan", replace_existing=True)
    else:
        auto_scan_on = False
        try: scheduler.remove_job("auto_scan")
        except: pass
    return JSONResponse({"auto_scan": auto_scan_on})


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket for real-time signal delivery to browser."""
    await ws.accept()
    _ws_clients.append(ws)
    logger.info("WS client connected. Total: %d", len(_ws_clients))
    try:
        # Send current signals immediately
        if latest_signals:
            await ws.send_json({"type": "signals", "signals": latest_signals,
                                "ts": last_scan_ts})
        while True:
            # Keep alive — wait for ping from client
            data = await asyncio.wait_for(ws.receive_text(), timeout=60)
            if data == "ping":
                await ws.send_text("pong")
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        if ws in _ws_clients:
            _ws_clients.remove(ws)
        logger.info("WS client disconnected. Total: %d", len(_ws_clients))

"""API FastAPI — capa de lectura + sirve el frontend.

Arranque local:  uvicorn api.main:app --reload
Railway:         uvicorn api.main:app --host 0.0.0.0 --port $PORT
"""
from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from . import queries as Q

app = FastAPI(title="Xbox Price Atlas", version="0.1.0")

# CORS: permitir que el frontend (Vite dev en :5173, o el desplegado) llame a la API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

WEB = Path(__file__).resolve().parent.parent / "web"


@app.get("/health")
def health():
    return {"status": "ok"}


# ==== Análisis / actualización del catálogo (lo que antes era "scraping") ====
# Corre la etapa inicial completa: sitemaps -> catálogo -> precios -> USD.
# Es una acción ocasional (semanal), en segundo plano, con estado consultable.
import threading

_ingest = {"running": False, "phase": "idle", "detail": "", "started_at": None}


def _run_analysis(markets=None):
    from atlas import run_ingest, fx, db, config
    from atlas.http_client import CatalogClient
    import time as _t
    _ingest.update(running=True, phase="discovery",
                   detail="Analizando sitemaps y catálogo…", started_at=_t.time())
    try:
        client = CatalogClient()
        conn = db.connect()
        try:
            run_ingest.phase_discovery(conn, client)
            _ingest.update(phase="pricing", detail="Obteniendo precios por mercado…")
            run_ingest.phase_pricing(conn, client, markets or config.PRICING_MARKETS)
        finally:
            conn.close()
        _ingest.update(phase="fx", detail="Convirtiendo a USD…")
        fx.main()
        _ingest.update(phase="done", detail="Análisis completo.")
    except Exception as e:
        _ingest.update(phase="error", detail=str(e)[:300])
    finally:
        _ingest["running"] = False


@app.post("/api/analysis/start")
def analysis_start():
    """Dispara el análisis completo del catálogo (sitemaps + precios)."""
    if _ingest["running"]:
        return {"status": "already_running", **_ingest}
    threading.Thread(target=_run_analysis, daemon=True).start()
    return {"status": "started"}


@app.get("/api/analysis/status")
def analysis_status():
    return _ingest


@app.get("/api/stats")
def api_stats():
    return Q.stats()


@app.get("/api/search")
def api_search(term: str = Query(..., min_length=1), limit: int = 40):
    return Q.search(term, min(limit, 100))


@app.get("/api/cheapest")
def api_cheapest(market: str = "US", limit: int = 50):
    return Q.cheapest(market, min(limit, 5000))


@app.get("/api/deals")
def api_deals(market: str = "US", limit: int = 50):
    return Q.best_deals(market, min(limit, 200))


@app.get("/api/exclusives")
def api_exclusives(max_markets: int = 5, limit: int = 100):
    return Q.exclusives(max_markets, min(limit, 300))


@app.get("/api/spread")
def api_spread(limit: int = 50):
    return Q.spread(min(limit, 200))


@app.get("/api/markets")
def api_markets():
    return Q.markets_list()


@app.get("/api/subscriptions")
def api_subscriptions(limit: int = 100):
    return Q.subscriptions(min(limit, 300))


@app.get("/api/variant-world")
def api_variant_world(product_id: str, sku_id: str):
    return Q.variant_world(product_id, sku_id)


@app.get("/api/product/{product_id}")
def api_product(product_id: str, market: str | None = None):
    p = Q.product(product_id)
    if not p:
        raise HTTPException(404, "producto no encontrado")
    p["prices"] = Q.product_prices(product_id)
    # variantes (duraciones/promos) del mercado mas barato, o el pedido
    vmarket = (market or Q.cheapest_market_for(product_id) or "US").upper()
    p["variants"] = Q.product_variants(product_id, vmarket)
    p["variants_market"] = vmarket
    return p


# ---- frontend (app React de Figma, build en frontend/) ----
FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
_INDEX = (FRONTEND / "index.html") if (FRONTEND / "index.html").exists() else (WEB / "index.html")

# assets del build de Vite (/assets/index-xxx.js , .css)
if (FRONTEND / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND / "assets")), name="assets")


@app.get("/")
def index():
    return FileResponse(_INDEX)


# fallback SPA: cualquier ruta que no sea /api ni un asset devuelve el index
@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    if full_path.startswith("api/") or full_path.startswith("assets/"):
        raise HTTPException(404)
    return FileResponse(_INDEX)

"""API FastAPI — capa de lectura + sirve el frontend.

Arranque local:  uvicorn api.main:app --reload
Railway:         uvicorn api.main:app --host 0.0.0.0 --port $PORT
"""
from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from . import queries as Q

app = FastAPI(title="Xbox Price Atlas", version="0.1.0")

WEB = Path(__file__).resolve().parent.parent / "web"


@app.get("/api/stats")
def api_stats():
    return Q.stats()


@app.get("/api/search")
def api_search(term: str = Query(..., min_length=1), limit: int = 40):
    return Q.search(term, min(limit, 100))


@app.get("/api/cheapest")
def api_cheapest(market: str = "US", limit: int = 50):
    return Q.cheapest(market, min(limit, 200))


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


@app.get("/api/product/{product_id}")
def api_product(product_id: str):
    p = Q.product(product_id)
    if not p:
        raise HTTPException(404, "producto no encontrado")
    p["prices"] = Q.product_prices(product_id)
    return p


# ---- frontend ----
@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


if (WEB).exists():
    app.mount("/static", StaticFiles(directory=str(WEB)), name="static")

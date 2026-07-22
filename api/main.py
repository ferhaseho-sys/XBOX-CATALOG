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


@app.get("/api/games")
def api_games(limit: int = 1000, after: str = ""):
    """Catálogo con paginación keyset (IO liviano para free-tier)."""
    return Q.all_games(min(limit, 2000), after)


@app.get("/api/catalog")
def api_catalog(sort: str = "savings", page: int = 1, min_savings: int = 0,
                limit: int = 24, preset: str = "", include: str = "", exclude: str = ""):
    """Catálogo estilo xbox-now: presets + incluir/excluir países + paginación.
    Devuelve {total, items}. Con países filtrados recalcula la región más barata
    sobre el subconjunto (protegido con timeout para no saturar el free-tier)."""
    page = max(page, 1)
    lim = min(limit, 60)
    inc = [m for m in include.split(",") if m.strip()]
    exc = [m for m in exclude.split(",") if m.strip()]
    try:
        return Q.catalog(sort, lim, (page - 1) * lim, preset, min_savings, inc, exc)
    except Q.TooHeavy:
        raise HTTPException(
            503, "La selección de países es demasiado amplia para el free-tier. "
                 "Probá incluir menos países (o excluir menos).")


@app.get("/api/trending")
def api_trending(limit: int = 12):
    """'What's Trending': juegos más valorados con su mejor precio."""
    return Q.trending(limit)


@app.get("/api/catalog/markets")
def api_catalog_markets():
    """Mercados con precios guardados (para el selector de incluir/excluir países).
    El front resuelve nombre/bandera con Intl.DisplayNames a partir del código."""
    return Q.markets_list()


@app.get("/api/fx")
def api_fx():
    """Tasas {moneda: usd_rate} para convertir precios a la moneda elegida."""
    return Q.fx_rates_map()


# cliente HTTP compartido para las consultas en vivo (se crea una sola vez)
_live_client = {"c": None}


def _get_live_client():
    if _live_client["c"] is None:
        from atlas.http_client import CatalogClient
        _live_client["c"] = CatalogClient()
    return _live_client["c"]


@app.get("/api/markets/all")
def api_markets_all():
    """Los 242 mercados disponibles (para el selector de regiones)."""
    from atlas.markets import MARKETS, locale_for
    return [{"code": m, "locale": locale_for(m)} for m in MARKETS]


@app.get("/api/live/product/{product_id}")
def api_live_product(product_id: str, markets: str = ""):
    """Consulta EN VIVO a Microsoft el precio de un producto en los mercados
    pedidos (por defecto los 242), concurrente, con conversión a USD.
    Permite explorar cualquier producto en cualquier región sin pre-guardar."""
    from atlas.parse import parse_price, parse_variants
    from atlas.markets import MARKETS, locale_for
    from concurrent.futures import ThreadPoolExecutor

    codes = [m.strip().upper() for m in markets.split(",") if m.strip()] or MARKETS
    client = _get_live_client()
    rates = Q.fx_rates_map()
    title = {"v": None}

    def to_usd(row):
        lp, cur = row.get("list_price"), row.get("currency")
        if lp is not None and cur in rates:
            row["price_usd"] = round(lp * rates[cur], 2)
        return row

    def one(mk):
        prods = client.batch([product_id], market=mk, locale=locale_for(mk))
        if not prods:
            return None, []
        p = prods[0]
        if title["v"] is None:
            try:
                title["v"] = p.get("LocalizedProperties", [{}])[0].get("ProductTitle")
            except Exception:
                pass
        # variantes/denominaciones (SKUs) comprables de ESTE mercado, con USD
        variants = [to_usd(v) for v in parse_variants(p, mk)
                    if v.get("purchasable") and v.get("list_price")]
        pr = parse_price(p, mk)
        price = to_usd(pr) if pr.get("purchasable") else None
        return price, variants

    prices, all_variants = [], []
    with ThreadPoolExecutor(max_workers=20) as ex:
        for price, variants in ex.map(one, codes):
            if price:
                prices.append(price)
            all_variants.extend(variants)
    prices.sort(key=lambda x: (x.get("price_usd") is None, x.get("price_usd") or 1e18))
    all_variants.sort(key=lambda x: (x.get("price_usd") is None, x.get("price_usd") or 1e18))
    return {"product_id": product_id, "title": title["v"],
            "n_markets": len(prices), "prices": prices, "variants": all_variants}


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

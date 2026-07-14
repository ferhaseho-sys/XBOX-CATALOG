"""Orquestador de ingesta: discovery -> metadata -> pricing.

Uso:
  python -m atlas.run_ingest discovery              # sitemaps -> products (seed)
  python -m atlas.run_ingest metadata               # rellena metadata de products
  python -m atlas.run_ingest pricing                # precios en TODOS los mercados
  python -m atlas.run_ingest pricing US GB JP NG    # precios solo en esos mercados
  python -m atlas.run_ingest all                    # las tres fases seguidas

Es resumible: cada fase hace upsert idempotente y registra en ingest_runs.
"""
from __future__ import annotations
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from . import config, db
from .http_client import CatalogClient
from .markets import MARKETS
from .discovery import discover_ids
from .pricing import fetch_metadata, fetch_prices_for_market


def phase_discovery(conn, client):
    ids = sorted(discover_ids())
    print(f"[discovery] universo = {len(ids)} ProductIDs. Poblando metadata inicial...")
    # metadata inicial para tener filas en products (necesario para el FK de prices)
    metas = fetch_metadata(client, ids)
    n = db.upsert_products(conn, metas)
    db.log_run(conn, "discovery", None, "done", n, f"{len(ids)} ids")
    print(f"[discovery] {n} products upserted")


def phase_metadata(conn, client):
    ids = sorted(db.known_product_ids(conn))
    print(f"[metadata] refrescando {len(ids)} products")
    metas = fetch_metadata(client, ids)
    n = db.upsert_products(conn, metas)
    db.log_run(conn, "metadata", None, "done", n)
    print(f"[metadata] {n} products actualizados")


def _price_one_market(client, market):
    """Worker: abre su propia conexion (psycopg2 no es thread-safe por conexion)."""
    conn = db.connect()
    try:
        ids = db.products_for_market(conn, market)
        if not ids:
            db.log_run(conn, "pricing", market, "done", 0, "sin ids")
            return market, 0
        prices = fetch_prices_for_market(client, ids, market)
        n = db.upsert_prices(conn, prices)
        db.log_run(conn, "pricing", market, "done", n)
        return market, n
    except Exception as e:
        db.log_run(conn, "pricing", market, "error", 0, str(e))
        return market, -1
    finally:
        conn.close()


def phase_pricing(client, markets):
    print(f"[pricing] {len(markets)} mercados, {config.MARKET_WORKERS} en paralelo")
    with ThreadPoolExecutor(max_workers=config.MARKET_WORKERS) as ex:
        futs = {ex.submit(_price_one_market, client, m): m for m in markets}
        for fut in as_completed(futs):
            market, n = fut.result()
            status = "ERROR" if n < 0 else f"{n} precios"
            print(f"[pricing] {market}: {status}")


def main(argv):
    if not argv:
        print(__doc__)
        return
    phase = argv[0]
    markets = [m.upper() for m in argv[1:]] or MARKETS
    client = CatalogClient(rate=config.REQ_RATE)
    conn = db.connect()
    try:
        if phase in ("discovery", "all"):
            phase_discovery(conn, client)
        if phase == "metadata":
            phase_metadata(conn, client)
        if phase in ("pricing", "all"):
            phase_pricing(client, markets)
    finally:
        conn.close()
    print("listo.")


if __name__ == "__main__":
    main(sys.argv[1:])

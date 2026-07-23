"""Orquestador de ingesta: discovery -> metadata -> pricing.

Uso:
  python -m atlas.run_ingest discovery              # sitemaps -> products (seed)
  python -m atlas.run_ingest metadata               # rellena metadata de products
  python -m atlas.run_ingest pricing                # precios en TODOS los mercados
  python -m atlas.run_ingest pricing US GB JP NG    # precios solo en esos mercados
  python -m atlas.run_ingest browse                 # Emerald: disponibilidad por mercado
  python -m atlas.run_ingest browse es-AR en-US     # solo esos locales
  python -m atlas.run_ingest all                    # las tres fases seguidas

`browse` es independiente: escribe en `market_catalog` y no toca products/prices.

Es resumible: cada fase hace upsert idempotente y registra en ingest_runs.
"""
from __future__ import annotations
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import time
from . import config, db
from .http_client import CatalogClient
from .discovery import discover_ids
from .pricing import fetch_metadata, fetch_price_chunk, market_chunks


def _incremental_upserter(conn):
    """Callback que hace upsert de cada lote y acumula el total (con progreso)."""
    state = {"n": 0}

    def _on_batch(metas):
        state["n"] += db.upsert_products(conn, metas)
        print(f"[db] products acumulados: {state['n']}", flush=True)

    return state, _on_batch


def phase_discovery(conn, client):
    universe = discover_ids()
    done = db.known_product_ids(conn)          # resumible: saltea lo ya cargado
    ids = sorted(universe - done)
    print(f"[discovery] universo={len(universe)} | ya en DB={len(done)} | faltan={len(ids)}",
          flush=True)
    if not ids:
        print("[discovery] nada pendiente, ya esta completo", flush=True)
        return
    state, on_batch = _incremental_upserter(conn)
    fetch_metadata(client, ids, on_batch=on_batch)
    db.log_run(conn, "discovery", None, "done", state["n"], f"{len(ids)} ids nuevos")
    print(f"[discovery] {state['n']} products upserted", flush=True)


def phase_metadata(conn, client):
    ids = sorted(db.known_product_ids(conn))
    print(f"[metadata] refrescando {len(ids)} products")
    state, on_batch = _incremental_upserter(conn)
    fetch_metadata(client, ids, on_batch=on_batch)
    db.log_run(conn, "metadata", None, "done", state["n"])
    print(f"[metadata] {state['n']} products actualizados")


def phase_pricing(conn, client, markets):
    """Cola plana: TODOS los lotes de los 48 mercados en un solo pool de fetchers.
    Los workers solo descargan+parsean (I/O + parse); el hilo principal hace el
    upsert incremental con UNA conexion (sin locks ni contencion en Postgres, ya
    que cada fila es de un mercado distinto). Evita la cola de espera por mercados
    grandes que tenia el modelo 1-worker-por-mercado."""
    t0 = time.monotonic()
    t_start = datetime.now(timezone.utc)     # reloj de pared, para medir duraciones
    # 1) armar todas las tareas (market, chunk) leyendo los ids una vez por mercado
    tasks = []
    pending = {}   # market -> lotes restantes
    for m in markets:
        ids = db.products_for_market(conn, m)
        chunks = list(market_chunks(ids, m))
        if not chunks:
            db.log_run(conn, "pricing", m, "done", 0, "sin ids")
            continue
        pending[m] = len(chunks)
        tasks.extend(chunks)
    print(f"[pricing] {len(pending)} mercados, {len(tasks)} lotes, "
          f"{config.WORKERS} workers, batch={config.BATCH_SIZE}", flush=True)

    counts = {m: 0 for m in pending}
    total_rows = 0
    done_lotes = 0
    with ThreadPoolExecutor(max_workers=config.WORKERS) as ex:
        futs = {ex.submit(fetch_price_chunk, client, m, chunk): m
                for (m, chunk) in tasks}
        for fut in as_completed(futs):
            m = futs[fut]
            try:
                rows = fut.result()
            except Exception as e:
                rows = []
                print(f"[pricing:{m}] lote error: {e}", flush=True)
            n = db.upsert_prices(conn, rows)          # upsert incremental (hilo principal)
            counts[m] += n
            total_rows += n
            done_lotes += 1
            pending[m] -= 1
            if pending[m] == 0:                        # mercado completo -> log
                db.log_run(conn, "pricing", m, "done", counts[m], started_at=t_start)
                print(f"[pricing] {m}: {counts[m]} precios", flush=True)
            if done_lotes % 25 == 0:
                dt = time.monotonic() - t0
                print(f"[pricing] {done_lotes}/{len(tasks)} lotes, "
                      f"{total_rows} precios, {dt:.0f}s", flush=True)
    dt = time.monotonic() - t0
    # fila resumen de TODA la fase (market=None): es la que responde
    # "¿cuánto tarda el refresh?" y si entra en la ventana del cron.
    db.log_run(conn, "pricing", None, "done", total_rows,
               f"{len(pending)} mercados, {len(tasks)} lotes, {dt:.0f}s",
               started_at=t_start)
    print(f"[pricing] LISTO: {total_rows} precios en {dt:.0f}s "
          f"({len(tasks)} lotes)", flush=True)


def main(argv):
    if not argv:
        print(__doc__)
        return
    phase = argv[0]
    # browse indexa por LOCALE ('es-AR'), no por mercado: delega tal cual
    if phase == "browse":
        from . import browse
        browse.main(argv[1:])
        return
    # sin mercados explicitos => set representativo por moneda (~50), no los 243
    markets = [m.upper() for m in argv[1:]] or config.PRICING_MARKETS
    client = CatalogClient(rate=config.REQ_RATE)
    conn = db.connect()
    try:
        if phase in ("discovery", "all"):
            phase_discovery(conn, client)
        if phase == "metadata":
            phase_metadata(conn, client)
        if phase in ("pricing", "all"):
            phase_pricing(conn, client, markets)
    finally:
        conn.close()
    print("listo.")


if __name__ == "__main__":
    main(sys.argv[1:])

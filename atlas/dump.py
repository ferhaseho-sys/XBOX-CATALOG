"""Dump rápido de TODOS los productos (JSON crudo de displaycatalog) a disco.

Baja los ~43k productos en lotes grandes (500) y concurrentes, y escribe cada uno
como una línea NDJSON. Pensado para análisis offline (categorización, detectar
delisted vs free, ver qué campos sirven), sin tocar la DB salvo para leer los IDs.

Uso:
  python -m atlas.dump                # todos, market=US -> dump_us.ndjson
  python -m atlas.dump AR 2000        # market=AR, solo 2000 (test) -> dump_ar.ndjson
"""
from __future__ import annotations
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import orjson
    def _dumps(o): return orjson.dumps(o)
except Exception:
    import json
    def _dumps(o): return json.dumps(o).encode("utf-8")

from . import db, config
from .http_client import CatalogClient
from .markets import locale_for

BATCH = 500
WORKERS = 16


def all_ids(limit: int = 0) -> list[str]:
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute("select product_id from products order by product_id")
            ids = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()
    return ids[:limit] if limit else ids


def dump(market: str = "US", limit: int = 0, out: str | None = None):
    out = out or f"dump_{market.lower()}.ndjson"
    ids = all_ids(limit)
    chunks = [ids[i:i + BATCH] for i in range(0, len(ids), BATCH)]
    print(f"[dump] {len(ids)} productos en {len(chunks)} lotes -> {out}", flush=True)

    client = CatalogClient()
    loc = locale_for(market)
    lock = threading.Lock()
    state = {"prods": 0, "done": 0}
    t0 = time.monotonic()
    f = open(out, "wb")

    def work(chunk):
        prods = client.batch(chunk, market=market, locale=loc)
        blob = b"".join(_dumps(p) + b"\n" for p in prods)
        with lock:
            f.write(blob)
            state["prods"] += len(prods)
            state["done"] += 1
            if state["done"] % 10 == 0 or state["done"] == len(chunks):
                dt = time.monotonic() - t0
                print(f"[dump] {state['done']}/{len(chunks)} lotes | "
                      f"{state['prods']} productos | {dt:.0f}s", flush=True)
        return len(prods)

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        list(as_completed(ex.submit(work, c) for c in chunks))
    f.close()
    dt = time.monotonic() - t0
    print(f"[dump] LISTO: {state['prods']} productos en {dt:.0f}s -> {out}", flush=True)


def main(argv):
    market = (argv[0].upper() if len(argv) > 0 else "US")
    limit = int(argv[1]) if len(argv) > 1 else 0
    dump(market, limit)


if __name__ == "__main__":
    main(sys.argv[1:])

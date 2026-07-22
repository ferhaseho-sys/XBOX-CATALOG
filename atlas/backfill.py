"""Backfill offline de categorización: popula products.kind / products.is_demo
desde el dump NDJSON y corrige prices.is_free (el fix del 'free' sobre datos vivos).

NO re-ingesta (ahorra IO del free-tier): lee `dump_us.ndjson` (kind/is_demo son
market-independientes: ProductType, IsDemo, título), y hace UPDATE en lote.

Después corrige is_free: un demo o cualquier no-Juego NUNCA es un juego gratis,
así que `is_free=false` para todo product cuyo kind != 'Juego' o is_demo=true.

Uso:
  python -m atlas.backfill                 # todo, desde dump_us.ndjson
  python -m atlas.backfill dump_us.ndjson  # dump explícito
"""
from __future__ import annotations
import sys
import collections
from psycopg2.extras import execute_values
from . import db
from .parse import is_demo, category, platforms

try:
    import orjson
    def _loads(b): return orjson.loads(b)
except Exception:
    import json
    def _loads(b): return json.loads(b)

BATCH = 2000


def rows_from_dump(path: str):
    """Genera (product_id, kind, is_demo, on_pc, on_xbox) por cada línea del dump."""
    with open(path, "rb") as f:
        for line in f:
            if not line.strip():
                continue
            p = _loads(line)
            pid = p.get("ProductId")
            if not pid:
                continue
            pc, xb = platforms(p)
            yield (pid, category(p), is_demo(p), pc, xb)


def backfill_products(conn, path: str) -> collections.Counter:
    kinds = collections.Counter()
    n_demo = n_pc = n_xbox = n_xpa = 0
    total = 0
    batch = []
    sql = ("update products as p set kind = v.kind, is_demo = v.is_demo, "
           "on_pc = v.on_pc, on_xbox = v.on_xbox "
           "from (values %s) as v(product_id, kind, is_demo, on_pc, on_xbox) "
           "where p.product_id = v.product_id")

    def flush():
        nonlocal batch
        if not batch:
            return
        with conn.cursor() as cur:
            execute_values(cur, sql, batch,
                           template="(%s, %s, %s::boolean, %s::boolean, %s::boolean)",
                           page_size=BATCH)
        conn.commit()
        batch = []

    for pid, kind, demo, pc, xb in rows_from_dump(path):
        kinds[kind] += 1
        n_demo += 1 if demo else 0
        n_pc += 1 if pc else 0
        n_xbox += 1 if xb else 0
        n_xpa += 1 if (pc and xb) else 0
        total += 1
        batch.append((pid, kind, demo, pc, xb))
        if len(batch) >= BATCH:
            flush()
            print(f"[backfill] {total} products actualizados…", flush=True)
    flush()
    print(f"[backfill] LISTO products: {total} | demos: {n_demo}", flush=True)
    print(f"[backfill] distribución kind: {dict(kinds.most_common())}", flush=True)
    print(f"[backfill] plataformas: PC={n_pc} Xbox={n_xbox} PlayAnywhere={n_xpa}", flush=True)
    return kinds


def fix_is_free(conn) -> int:
    """is_free=false para todo lo que no sea un Juego real (no-Juego o demo)."""
    with conn.cursor() as cur:
        cur.execute(
            "update prices set is_free = false "
            "where is_free = true and product_id in ("
            "  select product_id from products where kind is distinct from 'Juego' or is_demo = true"
            ")"
        )
        n = cur.rowcount
    conn.commit()
    return n


def main(argv):
    path = argv[0] if argv else "dump_us.ndjson"
    conn = db.connect()
    try:
        # estado previo del is_free (para comparar)
        with conn.cursor() as cur:
            cur.execute("select count(*) from prices where is_free = true")
            before = cur.fetchone()[0]
        print(f"[backfill] is_free=true ANTES: {before}", flush=True)

        backfill_products(conn, path)

        flipped = fix_is_free(conn)
        with conn.cursor() as cur:
            cur.execute("select count(*) from prices where is_free = true")
            after = cur.fetchone()[0]
        print(f"[backfill] is_free corregidos a false: {flipped} | is_free=true AHORA: {after}", flush=True)
    finally:
        conn.close()
    print("[backfill] listo.")


if __name__ == "__main__":
    main(sys.argv[1:])

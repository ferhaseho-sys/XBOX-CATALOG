"""Suscripciones (PASS): siembra las conocidas y las precia en TODOS los mercados.

Las suscripciones no estan en los sitemaps de juegos, y desde US reportan
available_markets=[US] (mal). Este pase:
  1. Siembra KNOWN_SUBSCRIPTIONS (metadata) en `products`.
  2. Toma todas las PASS de la DB y las precia en los PRICING_MARKETS
     (parse.py ya saltea SKUs ocultos y captura la recurrencia).

Uso:  python -m atlas.subs
"""
from __future__ import annotations
from . import config, db
from .http_client import CatalogClient
from .markets import locale_for
from .parse import parse_product, parse_price, parse_variants


def seed_known(conn, client) -> int:
    ids = config.KNOWN_SUBSCRIPTIONS
    if not ids:
        return 0
    prods = client.batch(ids, market="US", locale="en-US")
    metas = [parse_product(p, "US") for p in prods]
    n = db.upsert_products(conn, metas)
    print(f"[subs] sembradas {n} suscripciones conocidas", flush=True)
    return n


def all_pass_ids(conn) -> list[str]:
    with conn.cursor() as cur:
        cur.execute("select product_id from products where product_type = 'PASS'")
        return [r[0] for r in cur.fetchall()]


def main():
    client = CatalogClient()
    # 1) sembrar + leer PASS ids (conexion corta)
    conn = db.connect()
    try:
        seed_known(conn, client)
        ids = all_pass_ids(conn)
    finally:
        conn.close()
    print(f"[subs] {len(ids)} suscripciones a precificar en {len(config.PRICING_MARKETS)} mercados",
          flush=True)

    # 2) fetch de todos los mercados (solo HTTP, sin DB) -> acumular precio + variantes
    all_rows = []
    all_variants = []
    for m in config.PRICING_MARKETS:
        prods = client.batch(ids, market=m, locale=locale_for(m))
        all_rows.extend(parse_price(p, m) for p in prods)
        for p in prods:
            all_variants.extend(parse_variants(p, m))
        print(f"[subs] {m}: {len(prods)} productos", flush=True)

    # 3) upsert al final (conexion fresca, sin idle durante el HTTP)
    conn = db.connect()
    try:
        total, cambios = db.upsert_prices(conn, all_rows)
        nv = db.upsert_variants(conn, all_variants)
    finally:
        conn.close()
    print(f"[subs] LISTO: {total} precios ({cambios} cambios) + {nv} variantes "
          f"de suscripciones", flush=True)


if __name__ == "__main__":
    main()

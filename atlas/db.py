"""Acceso a Postgres (Supabase): conexion y upserts en lote."""
from __future__ import annotations
import json
import psycopg2
from psycopg2.extras import execute_values
from . import config

PRODUCT_COLS = [
    "product_id", "title", "short_title", "short_desc", "description",
    "product_type", "product_kind", "product_family", "developer", "publisher",
    "category", "kind", "is_demo", "on_pc", "on_xbox", "categories",
    "release_date", "min_user_age",
    "is_ms_product", "has_addons", "console_gen", "gold_required", "image_hero",
    "image_boxart", "image_poster", "trailer", "avg_rating", "rating_count",
    "ratings", "xbox_title_id", "available_markets", "n_available_markets",
    "last_modified",
]

PRICE_COLS = [
    "product_id", "market", "currency", "list_price", "msrp", "discount_pct",
    "on_sale", "sale_ends", "is_free", "n_paid_offers", "recurrence",
]

VARIANT_COLS = [
    "product_id", "market", "sku_id", "title", "duration", "is_hidden",
    "is_recurring", "purchasable", "currency", "list_price",
]

MARKET_CATALOG_COLS = [
    "product_id", "market", "source", "locale", "rank", "available_on",
    "in_gamepass", "pass_ids", "pass_exit_date", "pass_entry_date",
    "on_xcloud", "on_handheld",
    "handheld_tier", "badges", "avg_rating", "rating_count",
    "list_price", "msrp", "discount_pct", "currency",
]


def connect():
    if not config.DATABASE_URL:
        raise RuntimeError("DATABASE_URL no configurada (ver .env.example)")
    conn = psycopg2.connect(config.DATABASE_URL)
    conn.autocommit = False
    return conn


def _row(d: dict, cols: list[str]) -> tuple:
    out = []
    for c in cols:
        v = d.get(c)
        if c == "ratings" and isinstance(v, dict):
            v = json.dumps(v)
        out.append(v)
    return tuple(out)


def upsert_products(conn, products: list[dict]) -> int:
    if not products:
        return 0
    rows = [_row(p, PRODUCT_COLS) for p in products]
    updates = ", ".join(f"{c}=excluded.{c}" for c in PRODUCT_COLS if c not in ("product_id", "first_seen"))
    sql = (f"insert into products ({', '.join(PRODUCT_COLS)}) values %s "
           f"on conflict (product_id) do update set {updates}, updated_at=now()")
    with conn.cursor() as cur:
        execute_values(cur, sql, rows, page_size=500)
    conn.commit()
    return len(rows)


def upsert_prices(conn, prices: list[dict]) -> int:
    """Solo inserta filas comprables (purchasable=True)."""
    rows = [_row(p, PRICE_COLS) for p in prices if p.get("purchasable")]
    if not rows:
        return 0
    updates = ", ".join(f"{c}=excluded.{c}" for c in PRICE_COLS if c not in ("product_id", "market"))
    sql = (f"insert into prices ({', '.join(PRICE_COLS)}) values %s "
           f"on conflict (product_id, market) do update set {updates}, updated_at=now()")
    with conn.cursor() as cur:
        execute_values(cur, sql, rows, page_size=500)
    conn.commit()
    return len(rows)


def upsert_variants(conn, variants: list[dict]) -> int:
    """Guarda TODAS las variantes (SKUs) de un producto por mercado."""
    rows = [_row(v, VARIANT_COLS) for v in variants if v.get("sku_id")]
    if not rows:
        return 0
    updates = ", ".join(f"{c}=excluded.{c}" for c in VARIANT_COLS
                        if c not in ("product_id", "market", "sku_id"))
    sql = (f"insert into variants ({', '.join(VARIANT_COLS)}) values %s "
           f"on conflict (product_id, market, sku_id) do update set {updates}, updated_at=now()")
    with conn.cursor() as cur:
        execute_values(cur, sql, rows, page_size=500)
    conn.commit()
    return len(rows)


def upsert_market_catalog(conn, rows: list[dict]) -> int:
    """Disponibilidad por mercado (Emerald Browse). Tabla independiente: no toca
    `products` ni `prices`."""
    data = [_row(r, MARKET_CATALOG_COLS) for r in rows if r.get("product_id")]
    if not data:
        return 0
    keys = ("product_id", "market", "source")
    updates = ", ".join(f"{c}=excluded.{c}" for c in MARKET_CATALOG_COLS if c not in keys)
    sql = (f"insert into market_catalog ({', '.join(MARKET_CATALOG_COLS)}) values %s "
           f"on conflict (product_id, market, source) do update set {updates}, seen_at=now()")
    with conn.cursor() as cur:
        execute_values(cur, sql, data, page_size=500)
    conn.commit()
    return len(data)


def known_product_ids(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("select product_id from products")
        return {r[0] for r in cur.fetchall()}


def products_for_market(conn, market: str) -> list[str]:
    """IDs a precificar en `market`: los distribuidos ahi (available_markets) MAS
    todas las suscripciones (PASS). Los PASS reportan available_markets=[US] mal
    desde US, asi que se precian en todos los mercados y la API decide si estan
    disponibles (los no comprables se descartan en upsert_prices)."""
    with conn.cursor() as cur:
        cur.execute(
            "select product_id from products "
            "where %s = any(available_markets) or product_type = 'PASS'",
            (market,),
        )
        return [r[0] for r in cur.fetchall()]


def log_run(conn, phase: str, market: str | None, status: str, n: int = 0,
            detail: str = "", started_at=None) -> None:
    """Registra una fase terminada.

    `started_at` (datetime) es opcional pero IMPORTANTE: sin él, started_at toma
    su default now() en el momento del insert y queda igual a finished_at, con lo
    que toda duración da 0 y no hay forma de saber cuánto tarda una ingesta."""
    with conn.cursor() as cur:
        cur.execute(
            "insert into ingest_runs (phase, market, status, n_products, "
            "started_at, finished_at, detail) "
            "values (%s,%s,%s,%s, coalesce(%s, now()), now(), %s)",
            (phase, market, status, n, started_at, detail[:500]),
        )
    conn.commit()

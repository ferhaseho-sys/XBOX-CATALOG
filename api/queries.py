"""Consultas de lectura para la API. Devuelven listas de dicts."""
from __future__ import annotations
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
from atlas import config

_pool: SimpleConnectionPool | None = None


def pool() -> SimpleConnectionPool:
    global _pool
    if _pool is None:
        _pool = SimpleConnectionPool(1, 8, dsn=config.DATABASE_URL)
    return _pool


def q(sql: str, args: tuple = ()) -> list[dict]:
    p = pool()
    conn = p.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, args)
            return [dict(r) for r in cur.fetchall()]
    finally:
        p.putconn(conn)


def stats() -> dict:
    r = q("select "
          "(select count(*) from products) as products, "
          "(select count(*) from prices) as price_rows, "
          "(select count(distinct market) from prices) as markets, "
          "(select count(*) from prices where on_sale) as on_sale")
    return r[0] if r else {}


def search(term: str, limit: int = 40) -> list[dict]:
    return q(
        "select product_id, title, publisher, product_type, image_boxart, "
        "avg_rating, rating_count, n_available_markets "
        "from products where title ilike %s order by rating_count desc nulls last limit %s",
        (f"%{term}%", limit),
    )


def cheapest(market: str, limit: int = 50) -> list[dict]:
    return q(
        "select pr.product_id, p.title, p.image_boxart, pr.currency, pr.list_price, "
        "pr.price_usd, pr.discount_pct, p.n_available_markets "
        "from prices pr join products p using (product_id) "
        "where pr.market = %s and pr.price_usd is not null and pr.list_price > 0 "
        "order by pr.price_usd asc limit %s",
        (market.upper(), limit),
    )


def best_deals(market: str, limit: int = 50) -> list[dict]:
    return q(
        "select pr.product_id, p.title, p.image_boxart, pr.currency, pr.list_price, "
        "pr.msrp, pr.price_usd, pr.discount_pct, pr.sale_ends "
        "from prices pr join products p using (product_id) "
        "where pr.market = %s and pr.discount_pct > 0 "
        "order by pr.discount_pct desc limit %s",
        (market.upper(), limit),
    )


def exclusives(max_markets: int = 5, limit: int = 100) -> list[dict]:
    """Juegos con baja cobertura (rarezas regionales)."""
    return q(
        "select product_id, title, publisher, product_type, image_boxart, "
        "available_markets, n_available_markets "
        "from products where n_available_markets <= %s and n_available_markets > 0 "
        "order by n_available_markets asc, rating_count desc nulls last limit %s",
        (max_markets, limit),
    )


def spread(limit: int = 50) -> list[dict]:
    """Mayor diferencia de precio (USD) del mismo juego entre mercados."""
    return q(
        "select p.product_id, p.title, p.image_boxart, "
        "min(pr.price_usd) as min_usd, max(pr.price_usd) as max_usd, "
        "count(*) as n_markets, round(max(pr.price_usd)-min(pr.price_usd),2) as spread_usd "
        "from prices pr join products p using (product_id) "
        "where pr.price_usd is not null and pr.list_price > 0 "
        "group by p.product_id, p.title, p.image_boxart "
        "having count(*) >= 5 order by spread_usd desc limit %s",
        (limit,),
    )


def product(product_id: str) -> dict | None:
    r = q("select * from products where product_id = %s", (product_id,))
    return r[0] if r else None


def product_prices(product_id: str) -> list[dict]:
    """Mapa de precios por mercado, ordenado de mas barato a mas caro (USD)."""
    return q(
        "select market, currency, list_price, msrp, discount_pct, on_sale, "
        "is_free, price_usd from prices where product_id = %s "
        "order by price_usd asc nulls last",
        (product_id,),
    )


def markets_list() -> list[dict]:
    return q("select market, count(*) as n, round(avg(price_usd),2) as avg_usd "
             "from prices where price_usd is not null group by market order by market")

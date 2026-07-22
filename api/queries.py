"""Consultas de lectura para la API. Devuelven listas de dicts."""
from __future__ import annotations
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
from atlas import config

_pool: SimpleConnectionPool | None = None


def pool() -> SimpleConnectionPool:
    global _pool
    if _pool is None:
        # Pool chico + timeouts para no saturar el pooler de Supabase (free tier)
        # ni colgar requests: si la DB no responde, la query falla en ~15-20s.
        _pool = SimpleConnectionPool(
            1, 3, dsn=config.DATABASE_URL,
            connect_timeout=10,
            options="-c statement_timeout=20000",
        )
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


def all_games(limit: int = 1000, after: str = "") -> list[dict]:
    """Catálogo con paginación KEYSET por product_id (índice PK = IO mínimo,
    sin sort de toda la tabla). `after` = último product_id de la tanda previa."""
    return q(
        "select p.product_id, p.title, p.image_boxart, p.publisher, p.developer, "
        "p.product_type, p.kind, p.is_demo, p.on_pc, p.on_xbox, p.avg_rating, p.n_available_markets, "
        "pr.currency, pr.list_price, pr.msrp, pr.price_usd, pr.discount_pct, pr.on_sale, pr.is_free "
        "from products p "
        "left join prices pr on pr.product_id = p.product_id and pr.market = 'US' "
        "where p.product_id > %s order by p.product_id limit %s",
        (after, limit),
    )


def catalog_page(limit: int = 20, after: str = "") -> list[dict]:
    """Página del catálogo estilo xbox-now: cada juego con su precio US Y el de la
    región más barata (2 columnas). Keyset por product_id = IO liviano."""
    games = q(
        "select p.product_id, p.title, p.image_boxart, p.publisher, p.developer, "
        "p.product_type, p.console_gen, p.has_addons, p.release_date, p.short_desc, "
        "pr.currency as us_currency, pr.list_price as us_list, pr.msrp as us_msrp, "
        "pr.price_usd as us_usd, pr.discount_pct as us_disc, pr.on_sale as us_onsale "
        "from products p "
        "left join prices pr on pr.product_id = p.product_id and pr.market = 'US' "
        "where p.product_id > %s order by p.product_id limit %s",
        (after, limit),
    )
    if not games:
        return []
    ids = [g["product_id"] for g in games]
    cheapest = q(
        "select distinct on (product_id) product_id, market, currency, list_price, "
        "price_usd, discount_pct, on_sale, sale_ends from prices "
        "where product_id = any(%s) and price_usd is not null and list_price > 0 "
        "order by product_id, price_usd asc",
        (ids,),
    )
    cmap = {c["product_id"]: c for c in cheapest}
    for g in games:
        g["cheapest"] = cmap.get(g["product_id"])
    return games


def catalog_deals(sort: str = "savings", limit: int = 24, offset: int = 0,
                  min_savings: int = 0) -> list[dict]:
    """Catálogo ordenable desde el resumen `deals` (index-scan liviano).
    sort: savings (mayor ahorro), cheapest (más barato USD), name."""
    order = {
        "savings": "d.savings_pct desc, d.product_id",
        "cheapest": "d.cheapest_usd asc nulls last, d.product_id",
        "name": "p.title asc",
    }.get(sort, "d.savings_pct desc, d.product_id")
    rows = q(
        "select p.product_id, p.title, p.image_boxart, p.publisher, p.product_type, "
        "p.kind, p.is_demo, p.on_pc, p.on_xbox, p.console_gen, p.has_addons, p.release_date, p.short_desc, "
        "d.us_usd, d.cheapest_market, d.cheapest_currency, d.cheapest_list, "
        "d.cheapest_usd, d.savings_pct, d.on_sale, d.sale_ends "
        "from deals d join products p using (product_id) "
        "where d.savings_pct >= %s "
        f"order by {order} limit %s offset %s",
        (min_savings, min(limit, 60), offset),
    )
    for r in rows:
        r["us_currency"] = "USD"
        r["us_list"] = r.get("us_usd")
        r["us_disc"] = 0
        r["cheapest"] = {
            "market": r.pop("cheapest_market"), "currency": r.pop("cheapest_currency"),
            "list_price": r.pop("cheapest_list"), "price_usd": r.pop("cheapest_usd"),
            "discount_pct": 0, "on_sale": r.pop("on_sale"), "sale_ends": r.pop("sale_ends"),
        }
    return rows


def fx_rates_map() -> dict:
    """{CURRENCY: usd_rate} desde fx_rates, para convertir precios en vivo."""
    return {r["currency"]: float(r["usd_rate"]) for r in q("select currency, usd_rate from fx_rates")}


def stats() -> dict:
    r = q("select "
          "(select count(*) from products) as products, "
          "(select count(*) from prices) as price_rows, "
          "(select count(distinct market) from prices) as markets, "
          "(select count(*) from prices where on_sale) as on_sale")
    return r[0] if r else {}


def search(term: str, limit: int = 40) -> list[dict]:
    return q(
        "select product_id, title, publisher, product_type, kind, is_demo, on_pc, on_xbox, image_boxart, "
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


def subscriptions(limit: int = 100) -> list[dict]:
    """Todas las suscripciones (PASS) con su precio titular mas barato (USD)."""
    return q(
        "select p.product_id, p.title, p.publisher, p.image_boxart, "
        "min(pr.price_usd) as min_usd, count(distinct pr.market) as n_markets, "
        "max(pr.recurrence) as recurrence "
        "from products p join prices pr using (product_id) "
        "where p.product_type = 'PASS' and pr.price_usd is not null and pr.list_price > 0 "
        "group by p.product_id, p.title, p.publisher, p.image_boxart "
        "order by min_usd asc limit %s",
        (limit,),
    )


def product_variants(product_id: str, market: str) -> list[dict]:
    """Variantes (duraciones/promos) de un producto en un mercado, con precio."""
    return q(
        "select sku_id, title, duration, is_hidden, is_recurring, purchasable, "
        "currency, list_price, price_usd from variants "
        "where product_id = %s and market = %s and list_price > 0 "
        "order by price_usd asc nulls last",
        (product_id, market.upper()),
    )


def variant_world(product_id: str, sku_id: str) -> list[dict]:
    """Una variante (SKU) especifica comparada en TODOS los paises, por USD."""
    return q(
        "select market, currency, list_price, price_usd, title "
        "from variants where product_id = %s and sku_id = %s "
        "and price_usd is not null and list_price > 0 "
        "order by price_usd asc",
        (product_id, sku_id),
    )


def cheapest_market_for(product_id: str) -> str | None:
    r = q("select market from prices where product_id = %s and price_usd is not null "
          "and list_price > 0 order by price_usd asc limit 1", (product_id,))
    return r[0]["market"] if r else None


def markets_list() -> list[dict]:
    return q("select market, count(*) as n, round(avg(price_usd),2) as avg_usd "
             "from prices where price_usd is not null group by market order by market")

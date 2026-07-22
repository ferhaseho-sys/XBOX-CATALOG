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
        conn.rollback()          # cerrar la tx implícita (no dejar idle-in-transaction)
        p.putconn(conn)


class TooHeavy(Exception):
    """La query de subconjunto excedió el presupuesto de tiempo (protección free-tier)."""


def q_guarded(sql: str, args: tuple = (), ms: int = 9000) -> list[dict]:
    """Como q() pero con presupuesto de tiempo REAL, para proteger a Supabase NANO
    de agregaciones pesadas (incluir/excluir países sobre muchos mercados).
    Doble red: SET LOCAL statement_timeout + watchdog client-side conn.cancel().
    Si se pasa del presupuesto, levanta TooHeavy."""
    import threading
    import psycopg2
    import psycopg2.errors
    p = pool()
    conn = p.getconn()
    conn.rollback()                                   # limpiar cualquier tx previa
    timer = threading.Timer(ms / 1000 + 2.0, conn.cancel)
    timer.start()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("set local statement_timeout = %s", (ms,))
            cur.execute(sql, args)
            return [dict(r) for r in cur.fetchall()]
    except (psycopg2.errors.QueryCanceled, psycopg2.extensions.QueryCanceledError):
        raise TooHeavy()
    finally:
        timer.cancel()
        conn.rollback()
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


# ---- Catálogo estilo xbox-now: presets + orden + incluir/excluir países ----

_CAT_COLS = (
    "p.product_id, p.title, p.image_boxart, p.publisher, p.product_type, "
    "p.kind, p.is_demo, p.on_pc, p.on_xbox, p.console_gen, p.has_addons, "
    "p.release_date, p.short_desc"
)

# presets que SÍ tienen datos (los demás se muestran deshabilitados en la UI).
# Referencian columnas de SALIDA del INNER (sin prefijo p.), válidas en ambos caminos.
_PRESET_WHERE = {
    "": "",
    "everything": "",
    "discounts": "savings_pct >= 1",
    "non_gold": "on_sale and (gold_required is not true) and savings_pct >= 1",
    "free": "is_free",
    "play_anywhere": "on_pc and on_xbox",
    "series_x": "'ConsoleGen9' = any(console_gen)",
    "dlc": "kind = 'DLC'",
    "games": "kind = 'Juego'",
}

_SORT = {
    "savings": "savings_pct desc nulls last, product_id",
    "cheapest": "cheapest_usd asc nulls last, product_id",
    "price_desc": "cheapest_usd desc nulls last, product_id",
    "name": "title asc",
    "last_added": "release_date desc nulls last, product_id",
}


def _priced_markets() -> list[str]:
    return [r["market"] for r in q("select distinct market from prices")]


# Cache chico de totales: solo cambian tras un refresh de datos, así que no vale
# pagar el count (join sobre ~38k) en cada carga de página. TTL 10 min.
import time as _time
_count_cache: dict[str, tuple[float, int]] = {}


def _cached_total(key: str, fn, ttl: float = 600.0) -> int:
    hit = _count_cache.get(key)
    if hit and (_time.monotonic() - hit[0]) < ttl:
        return hit[1]
    val = fn()
    _count_cache[key] = (_time.monotonic(), val)
    return val


_CAT_EXTRA = "p.is_free, p.gold_required"   # columnas extra que los presets necesitan


def catalog(sort: str = "savings", limit: int = 24, offset: int = 0,
            preset: str = "", min_savings: int = 0,
            include: list[str] | None = None, exclude: list[str] | None = None) -> dict:
    """Catálogo estilo xbox-now. Sin países => usa `deals` (rápido). Con países =>
    recalcula la región más barata sobre el subconjunto (más pesado, gated).
    Ambos caminos producen un INNER normalizado; el preset filtra sobre sus columnas."""
    order = _SORT.get(sort, _SORT["savings"])

    # "Free Games": los F2P tienen precio $0, así que NO están en `deals`
    # (exige list_price>0). Se listan directo desde products.
    if preset == "free":
        forder = {"name": "p.title asc", "last_added": "p.release_date desc nulls last, p.product_id"}\
            .get(sort, "p.rating_count desc nulls last, p.product_id")
        total = _cached_total("free", lambda: q("select count(*) as n from products where is_free")[0]["n"])
        rows = q(f"select {_CAT_COLS}, {_CAT_EXTRA}, 0 as us_usd, null as cheapest_market, "
                 "null as cheapest_currency, null as cheapest_list, 0 as cheapest_usd, "
                 "0 as savings_pct, false as on_sale, null::timestamptz as sale_ends "
                 f"from products p where p.is_free order by {forder} limit %s offset %s",
                 (limit, offset))
        for r in rows:
            r["us_currency"] = "USD"; r["us_list"] = 0; r["us_disc"] = 0; r["cheapest"] = None
        return {"total": total, "items": rows}

    where_parts = []
    filt_args: list = []
    pw = _PRESET_WHERE.get(preset or "", "")
    if pw:
        where_parts.append(pw)
    if min_savings > 0:
        where_parts.append("savings_pct >= %s")
        filt_args.append(min_savings)
    w = (" where " + " and ".join(where_parts)) if where_parts else ""

    include = [m.upper() for m in (include or []) if m.strip()]
    exclude = [m.upper() for m in (exclude or []) if m.strip()]

    # total SIEMPRE por el camino rápido (deals), directo sobre el join (las columnas
    # del preset son inambiguas entre deals y products). Con países filtrados el total
    # cambia poquísimo, y así evitamos una 2ª agregación pesada: solo pagamos la página.
    ckey = f"{preset}|{min_savings}"
    total = _cached_total(
        ckey,
        lambda: q(f"select count(*) as n from deals d join products p using (product_id){w}",
                  tuple(filt_args))[0]["n"])

    if include or exclude:
        markets = include if include else [m for m in _priced_markets() if m not in set(exclude)]
        savings_expr = ("case when us.us_usd > 0 and sub.cheapest_usd is not null "
                        "then greatest(0, round(100*(us.us_usd - sub.cheapest_usd)/us.us_usd)) "
                        "else 0 end")
        inner = (
            "with sub as ("
            "  select distinct on (product_id) product_id, market as cheapest_market, "
            "  currency as cheapest_currency, list_price as cheapest_list, "
            "  price_usd as cheapest_usd, on_sale, sale_ends "
            "  from prices where market = any(%s) and price_usd is not null and list_price > 0 "
            "  order by product_id, price_usd asc"
            "), us as (select product_id, price_usd as us_usd from prices where market = 'US') "
            f"select {_CAT_COLS}, {_CAT_EXTRA}, us.us_usd, sub.cheapest_market, "
            f"sub.cheapest_currency, sub.cheapest_list, sub.cheapest_usd, {savings_expr} as savings_pct, "
            "sub.on_sale, sub.sale_ends "
            "from sub join products p using (product_id) left join us using (product_id)"
        )
        rows = q_guarded(f"select * from ({inner}) c{w} order by {order} limit %s offset %s",
                         tuple([markets] + filt_args + [limit, offset]), ms=9000)
    else:
        rows = q(f"select {_CAT_COLS}, d.us_usd, d.cheapest_market, d.cheapest_currency, "
                 "d.cheapest_list, d.cheapest_usd, d.savings_pct, d.on_sale, d.sale_ends "
                 f"from deals d join products p using (product_id){w} "
                 f"order by {order} limit %s offset %s",
                 tuple(filt_args + [limit, offset]))

    return {"total": total, "items": _shape_catalog_rows(rows)}


def _shape_catalog_rows(rows: list[dict]) -> list[dict]:
    """Da a cada fila la forma que consume la tarjeta del catálogo (us_* + cheapest)."""
    for r in rows:
        r["us_currency"] = "USD"
        r["us_list"] = r.get("us_usd")
        r["us_disc"] = 0
        if r.get("cheapest_market"):
            r["cheapest"] = {
                "market": r.pop("cheapest_market"), "currency": r.pop("cheapest_currency"),
                "list_price": r.pop("cheapest_list"), "price_usd": r.pop("cheapest_usd"),
                "discount_pct": 0, "on_sale": r.pop("on_sale"), "sale_ends": r.pop("sale_ends"),
            }
        else:
            for k in ("cheapest_market", "cheapest_currency", "cheapest_list",
                      "cheapest_usd", "on_sale", "sale_ends"):
                r.pop(k, None)
            r["cheapest"] = None
    return rows


def search_catalog(term: str, limit: int = 40) -> list[dict]:
    """Búsqueda por título con forma de catálogo (incluye la región más barata desde
    `deals`), para que los resultados muestren precios como las tarjetas normales."""
    rows = q(
        f"select {_CAT_COLS}, {_CAT_EXTRA}, d.us_usd, d.cheapest_market, d.cheapest_currency, "
        "d.cheapest_list, d.cheapest_usd, d.savings_pct, d.on_sale, d.sale_ends "
        "from products p left join deals d using (product_id) "
        "where p.title ilike %s order by p.rating_count desc nulls last, p.title limit %s",
        (f"%{term}%", min(limit, 60)),
    )
    return _shape_catalog_rows(rows)


def catalog_by_ids(ids: list[str]) -> list[dict]:
    """Filas de catálogo para una lista de product_ids (para 'relacionados'),
    respetando el orden pedido y descartando los que no están en la DB."""
    if not ids:
        return []
    rows = q(
        f"select {_CAT_COLS}, {_CAT_EXTRA}, d.us_usd, d.cheapest_market, d.cheapest_currency, "
        "d.cheapest_list, d.cheapest_usd, d.savings_pct, d.on_sale, d.sale_ends "
        "from products p left join deals d using (product_id) where p.product_id = any(%s)",
        (ids,),
    )
    by_id = {r["product_id"]: r for r in _shape_catalog_rows(rows)}
    return [by_id[i] for i in ids if i in by_id]


def trending(limit: int = 12) -> list[dict]:
    """'What's Trending': juegos más valorados (rating_count) con su mejor precio."""
    return q(
        "select p.product_id, p.title, p.image_boxart, p.on_pc, p.on_xbox, "
        "d.cheapest_market, d.cheapest_currency, d.cheapest_list, d.cheapest_usd "
        "from products p join deals d using (product_id) "
        "where p.kind = 'Juego' and p.rating_count is not null "
        "order by p.rating_count desc nulls last limit %s",
        (min(limit, 24),),
    )


# Microsoft aún factura algunos mercados con el código de moneda VIEJO (pre-redenominación),
# pero las APIs de FX usan el código nuevo. Sin esto, esas monedas quedan sin rate y el precio
# se toma como $0 (falso "más barato", ej. Mauritania MRO). factor = cuántas unidades VIEJAS
# equivalen a 1 NUEVA => rate(viejo) = rate(nuevo) / factor.
_CURRENCY_ALIASES = {
    "MRO": ("MRU", 10),      # Uguiya (Mauritania), redenominado 2018 (10:1)
    "STD": ("STN", 1000),    # Dobra (Santo Tomé), redenominado 2018 (1000:1)
}


def fx_rates_map() -> dict:
    """{CURRENCY: usd_rate} desde fx_rates (+ alias de monedas legacy), para convertir
    precios en vivo. Incluye los códigos viejos que Microsoft todavía usa."""
    m = {r["currency"]: float(r["usd_rate"]) for r in q("select currency, usd_rate from fx_rates")}
    for legacy, (modern, factor) in _CURRENCY_ALIASES.items():
        if legacy not in m and modern in m:
            m[legacy] = m[modern] / factor
    return m


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

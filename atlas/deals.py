"""Resumen `deals` precalculado por producto: región más barata + ahorro vs US.

Se calcula UNA sola vez (una agregación en la DB), y así ordenar/filtrar el
catálogo por 'mejor oferta' o 'mayor ahorro' es un index-scan liviano (clave en
free-tier). Correr después de pricing + fx.

Uso:  python -m atlas.deals
"""
from __future__ import annotations
from . import db

DDL = """
create table if not exists deals (
    product_id         text primary key references products(product_id) on delete cascade,
    cheapest_market    text,
    cheapest_currency  text,
    cheapest_list      numeric(12,2),
    cheapest_usd       numeric(12,2),
    us_usd             numeric(12,2),
    savings_pct        int,
    on_sale            boolean,
    sale_ends          timestamptz,
    n_markets          int,
    updated_at         timestamptz default now()
);
create index if not exists idx_deals_savings on deals (savings_pct desc);
create index if not exists idx_deals_cheapest on deals (cheapest_usd);
"""

FILL = """
insert into deals (product_id, cheapest_market, cheapest_currency, cheapest_list,
                   cheapest_usd, us_usd, savings_pct, on_sale, sale_ends, n_markets)
select c.product_id, c.market, c.currency, c.list_price, c.price_usd,
       u.price_usd,
       case when u.price_usd > 0 and c.price_usd is not null
            then greatest(0, round(100 * (u.price_usd - c.price_usd) / u.price_usd))
            else 0 end,
       c.on_sale, c.sale_ends, c.n
from (
    select distinct on (product_id) product_id, market, currency, list_price,
           price_usd, on_sale, sale_ends,
           count(*) over (partition by product_id) as n
    from prices
    where price_usd is not null and list_price > 0
    order by product_id, price_usd asc
) c
left join (select product_id, price_usd from prices where market = 'US') u
       using (product_id)
on conflict (product_id) do update set
    cheapest_market=excluded.cheapest_market, cheapest_currency=excluded.cheapest_currency,
    cheapest_list=excluded.cheapest_list, cheapest_usd=excluded.cheapest_usd,
    us_usd=excluded.us_usd, savings_pct=excluded.savings_pct,
    on_sale=excluded.on_sale, sale_ends=excluded.sale_ends,
    n_markets=excluded.n_markets, updated_at=now();
"""


def main():
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(DDL)
            conn.commit()
            print("[deals] tabla lista, calculando resumen…")
            cur.execute(FILL)
            n = cur.rowcount
            conn.commit()
            print(f"[deals] {n} productos con resumen de oferta")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

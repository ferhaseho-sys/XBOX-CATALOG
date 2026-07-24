"""Tasas de cambio -> normalizacion de precios a USD.

Usa la API gratuita open.er-api.com (sin key). Guarda en `fx_rates` el valor de
1 unidad de cada moneda en USD y recalcula `prices.price_usd`.

Uso:
  python -m atlas.fx            # refresca tasas y recalcula price_usd
"""
from __future__ import annotations
from datetime import datetime, timezone
import requests
from . import db

FX_URL = "https://open.er-api.com/v6/latest/USD"


def fetch_rates() -> dict[str, float]:
    """Devuelve {CURRENCY: usd_rate} donde usd_rate = USD por 1 unidad de moneda."""
    r = requests.get(FX_URL, timeout=20)
    r.raise_for_status()
    data = r.json()
    # data['rates'][CUR] = cuantas unidades de CUR equivalen a 1 USD
    rates = data.get("rates") or {}
    out = {}
    for cur, per_usd in rates.items():
        if per_usd and per_usd > 0:
            out[cur.upper()] = 1.0 / float(per_usd)
    return out


def upsert_rates(conn, rates: dict[str, float]) -> int:
    from psycopg2.extras import execute_values
    rows = [(cur, usd, "open.er-api.com") for cur, usd in rates.items()]
    sql = ("insert into fx_rates (currency, usd_rate, source) values %s "
           "on conflict (currency) do update set usd_rate=excluded.usd_rate, "
           "source=excluded.source, updated_at=now()")
    with conn.cursor() as cur:
        execute_values(cur, sql, rows)
    conn.commit()
    return len(rows)


def recalc_price_usd(conn) -> int:
    """price_usd = list_price * fx_rates.usd_rate (match por moneda), en prices y variants."""
    with conn.cursor() as cur:
        cur.execute(
            "update prices p set price_usd = round(p.list_price * f.usd_rate, 2) "
            "from fx_rates f where f.currency = p.currency and p.list_price is not null"
        )
        n = cur.rowcount
        # las variantes (subs) tambien
        cur.execute(
            "update variants v set price_usd = round(v.list_price * f.usd_rate, 2) "
            "from fx_rates f where f.currency = v.currency and v.list_price is not null"
        )
    conn.commit()
    return n


def main():
    conn = db.connect()
    t0 = datetime.now(timezone.utc)
    try:
        rates = fetch_rates()
        n = upsert_rates(conn, rates)
        print(f"[fx] {n} tasas actualizadas")
        m = recalc_price_usd(conn)
        print(f"[fx] {m} filas de prices con price_usd recalculado")
        # queda registrado para que el panel sepa qué tan fresco está
        db.log_run(conn, "fx", None, "done", n, f"{m} filas con price_usd",
                   started_at=t0)
    finally:
        conn.close()


if __name__ == "__main__":
    main()

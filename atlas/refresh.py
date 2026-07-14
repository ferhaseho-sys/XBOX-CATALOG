"""Refresco diario (para el cron de Railway): precios de un set de mercados + FX.

Mercados a refrescar: env MARKETS_REFRESH (coma-separado) o un core por defecto.
La metadata (discovery/metadata) se refresca aparte, con menos frecuencia.

Uso:  python -m atlas.refresh
"""
from __future__ import annotations
import os
from . import config, db, fx
from .http_client import CatalogClient
from .run_ingest import phase_pricing

CORE_MARKETS = ["US", "GB", "AR", "TR", "BR", "NG", "IN", "JP", "MX",
                "ZA", "DE", "PL", "UA", "CL", "CO", "TW", "KR", "ID"]


def main():
    markets = [m.strip().upper() for m in os.environ.get("MARKETS_REFRESH", "").split(",") if m.strip()]
    if not markets:
        markets = CORE_MARKETS
    print(f"[refresh] mercados: {markets}")

    client = CatalogClient(rate=config.REQ_RATE)
    phase_pricing(client, markets)

    # tasas de cambio + price_usd
    conn = db.connect()
    try:
        rates = fx.fetch_rates()
        fx.upsert_rates(conn, rates)
        n = fx.recalc_price_usd(conn)
        print(f"[refresh] FX ok, {n} filas con price_usd")
    finally:
        conn.close()
    print("[refresh] listo")


if __name__ == "__main__":
    main()

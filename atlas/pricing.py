"""Fases 2 y 3 — Metadata y Pricing via displaycatalog batch."""
from __future__ import annotations
from . import config
from .http_client import CatalogClient
from .markets import locale_for
from .parse import parse_product, parse_price


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def fetch_metadata(client: CatalogClient, ids: list[str], progress=print) -> list[dict]:
    """Fase 2: metadata canonica (market=US) para poblar `products`.
    La metadata (titulo, imagenes, Markets[]) llega igual aunque el juego no se
    venda en US, asi que un solo pase cubre todo el universo."""
    out = []
    total = len(ids)
    for i, chunk in enumerate(_chunks(ids, config.BATCH_SIZE), 1):
        prods = client.batch(chunk, market="US", locale="en-US")
        out.extend(parse_product(p, "US") for p in prods)
        progress(f"[metadata] lote {i} ({min(i*config.BATCH_SIZE, total)}/{total}) +{len(prods)}")
    return out


def fetch_prices_for_market(client: CatalogClient, ids: list[str], market: str,
                            progress=print) -> list[dict]:
    """Fase 3: precios de un mercado. `ids` debe venir ya filtrado a los que se
    distribuyen en ese mercado (db.products_for_market)."""
    loc = locale_for(market)
    out = []
    for chunk in _chunks(ids, config.BATCH_SIZE):
        prods = client.batch(chunk, market=market, locale=loc)
        out.extend(parse_price(p, market) for p in prods)
    n_buy = sum(1 for p in out if p.get("purchasable"))
    progress(f"[pricing:{market}] {len(ids)} pedidos -> {n_buy} comprables")
    return out

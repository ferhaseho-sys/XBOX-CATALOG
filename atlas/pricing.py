"""Fases 2 y 3 — Metadata y Pricing via displaycatalog batch."""
from __future__ import annotations
from . import config
from .http_client import CatalogClient
from .markets import locale_for
from .parse import parse_product, parse_price


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def fetch_metadata(client: CatalogClient, ids: list[str], progress=print,
                   on_batch=None) -> list[dict]:
    """Fase 2: metadata canonica (market=US) para poblar `products`.
    La metadata (titulo, imagenes, Markets[]) llega igual aunque el juego no se
    venda en US, asi que un solo pase cubre todo el universo.

    Si se pasa `on_batch(list_metas)`, se llama por cada lote (upsert incremental)
    y NO se acumula en memoria; devuelve [] en ese caso."""
    out = []
    total = len(ids)
    for i, chunk in enumerate(_chunks(ids, config.BATCH_SIZE), 1):
        prods = client.batch(chunk, market="US", locale="en-US")
        metas = [parse_product(p, "US") for p in prods]
        progress(f"[metadata] lote {i}/{-(-total // config.BATCH_SIZE)} "
                 f"({min(i*config.BATCH_SIZE, total)}/{total}) +{len(metas)}")
        if on_batch is not None:
            on_batch(metas)
        else:
            out.extend(metas)
    return out


def market_chunks(ids: list[str], market: str):
    """Genera tareas (market, chunk) para la cola plana de pricing."""
    for chunk in _chunks(ids, config.BATCH_SIZE):
        yield market, chunk


def fetch_price_chunk(client: CatalogClient, market: str, ids: list[str]) -> list[dict]:
    """Un solo lote: descarga + parsea precios. Pensado para correr en un pool
    de fetchers; NO toca la DB (el hilo principal hace el upsert).

    Usa `fieldsTemplate=Browse` (config.PRICING_FIELDS): trae lo mismo que
    'details' para precificar pero pesa 4,45x menos. Con 24 workers eso es la
    diferencia entre ~500 MB y ~120 MB en vuelo, que es lo que hacía que el
    contenedor se quedara sin memoria y reiniciara a mitad del trabajo."""
    prods = client.batch(ids, market=market, locale=locale_for(market),
                         fields=config.PRICING_FIELDS)
    return [parse_price(p, market) for p in prods]


def fetch_prices_for_market(client: CatalogClient, ids: list[str], market: str,
                            progress=print) -> list[dict]:
    """Version secuencial (se mantiene por compatibilidad)."""
    out = []
    for _, chunk in market_chunks(ids, market):
        out.extend(fetch_price_chunk(client, market, chunk))
    n_buy = sum(1 for p in out if p.get("purchasable"))
    progress(f"[pricing:{market}] {len(ids)} pedidos -> {n_buy} comprables")
    return out

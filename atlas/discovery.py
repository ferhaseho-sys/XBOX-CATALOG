"""Fase 1 — Discovery: sitemaps de Xbox -> universo de ProductIDs.

Descarga el indice de sitemaps, filtra los PDP de los locales sembradores,
descomprime cada .xml.gz y extrae los ProductIDs (12 chars al final de la URL).
La union de todos los mercados sembradores es el universo de IDs a precificar.
"""
from __future__ import annotations
import gzip
import io
import re
import requests
from . import config

PID_RE = re.compile(r"/([0-9A-Z]{12})</loc>")
SMAP_RE = re.compile(r"<loc>(https://www\.xbox\.com/sitemap/pdp-[^<]+\.xml\.gz)</loc>")
UA = {"User-Agent": "Mozilla/5.0"}


def _fetch(url: str, binary: bool = False, tries: int = 4):
    for i in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=30)
            r.raise_for_status()
            return r.content if binary else r.text
        except Exception:
            if i == tries - 1:
                raise
    return None


def sitemap_urls_for_seed() -> list[str]:
    """URLs de los .xml.gz de PDP para los locales sembradores de config."""
    index = _fetch(config.SITEMAP_INDEX)
    all_urls = SMAP_RE.findall(index)
    wanted = []
    for loc in config.SEED_LOCALES:
        token = f"pdp-{loc}-sitemap-"
        wanted += [u for u in all_urls if token in u]
    return wanted


def ids_from_sitemap(url: str) -> set[str]:
    raw = _fetch(url, binary=True)
    try:
        xml = gzip.decompress(raw).decode("utf-8", "replace")
    except OSError:
        xml = raw.decode("utf-8", "replace")
    return set(PID_RE.findall(xml))


def discover_ids(progress=print) -> set[str]:
    urls = sitemap_urls_for_seed()
    progress(f"[discovery] {len(urls)} sitemaps a procesar")
    ids: set[str] = set()
    for i, u in enumerate(urls, 1):
        try:
            got = ids_from_sitemap(u)
            ids |= got
            progress(f"[discovery] {i}/{len(urls)} +{len(got)} (union={len(ids)})")
        except Exception as e:
            progress(f"[discovery] fallo {u}: {e}")
    # subs conocidas que no estan en sitemaps (Fortnite Crew, etc.)
    ids |= set(config.KNOWN_SUBSCRIPTIONS)
    return ids

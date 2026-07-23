"""Fase Browse — Emerald (BFF de xbox.com) -> disponibilidad real por mercado.

Complementa a displaycatalog; NO lo reemplaza. Aporta lo que displaycatalog no
devuelve: Game Pass, popularidad, xCloud y compatibilidad handheld. A cambio,
solo cubre `productFamily=Games` (≈44% del catálogo: los DLC/consumibles siguen
viniendo de discovery+pricing).

Guarda SIEMPRE el crudo NDJSON antes de parsear: una página pesa ~450 KB y ya
trae los summaries hidratados, así que si mañana descubrimos un campo nuevo se
re-parsea offline en vez de volver a barrer la API.

Es RESUMIBLE: si el barrido se corta, volver a correrlo retoma en la última
página bajada (según el crudo en disco). Una página que falla se saltea y se
reporta; no aborta el barrido.

Uso:
  python -m atlas.browse                 # locales de config.BROWSE_LOCALES
  python -m atlas.browse es-AR en-US     # locales explícitos
  python -m atlas.browse es-AR 5         # solo 5 páginas (prueba rápida)
  python -m atlas.browse es-AR --restart # ignora lo bajado y arranca de cero
  python -m atlas.browse es-AR --reparse # re-parsea el crudo, sin tocar la red
  python -m atlas.browse es-AR --hydrate # rescata por /products lo que browse no dio
"""
from __future__ import annotations
import os
import sys
import time
from datetime import datetime, timezone

try:
    import orjson
    def _dumps(o) -> bytes: return orjson.dumps(o)
    def _loads(b): return orjson.loads(b)
except Exception:
    import json
    def _dumps(o) -> bytes: return json.dumps(o).encode("utf-8")
    def _loads(b): return json.loads(b)

# Reintentos POR PÁGINA, por encima de los del cliente HTTP. Emerald devuelve
# rachas de 500 (visto en la 249 de es-AR); esperar más largo suele destrabarlo.
PAGE_RETRIES = 3
PAGE_BACKOFF = 5      # segundos, se multiplica por el nº de intento
# ResultsPerPage está capado en 50 del lado del server. Las páginas rinden ~47
# (algunos items se filtran), pero 50 es el paso nominal para anclar el rank.
PAGE_SIZE = 50
# Microsoft usa 9998-12-30 como "sin fecha de fin" (mismo centinela que en
# displaycatalog). Cualquier fecha >= a esto no es una salida real del pass.
PERMANENT_SENTINEL = "9998-12-30"

from . import config, db
from .http_client import EmeraldClient

DDL = """
create table if not exists market_catalog (
    product_id       text not null,
    market           text not null,
    source           text not null default 'browse',
    locale           text,
    rank             int,
    available_on     text[],
    in_gamepass      boolean,
    pass_ids         text[],
    pass_exit_date   timestamptz,
    pass_entry_date  timestamptz,
    on_xcloud        boolean,
    on_handheld      boolean,
    handheld_tier    int,
    badges           int[],
    avg_rating       real,
    rating_count     int,
    list_price       numeric(12,2),
    msrp             numeric(12,2),
    discount_pct     int,
    currency         text,
    seen_at          timestamptz default now(),
    primary key (product_id, market, source)
);
create index if not exists idx_mktcat_market   on market_catalog (market);
create index if not exists idx_mktcat_gamepass on market_catalog (market, in_gamepass)
    where in_gamepass;
create index if not exists idx_mktcat_rank     on market_catalog (market, rank);
-- la tabla puede existir de una corrida anterior: el create no agrega columnas
alter table market_catalog add column if not exists pass_entry_date timestamptz;
-- "llega al Game Pass": pocas filas, se consulta seguido -> índice parcial
create index if not exists idx_mktcat_gp_coming on market_catalog (market, pass_entry_date)
    where pass_entry_date is not null;
"""

RAW_DIR = os.environ.get("BROWSE_RAW_DIR", ".")


def market_of(locale: str) -> str:
    """'es-AR' -> 'AR'. Emerald indexa por locale; nuestra DB, por mercado."""
    return locale.split("-")[-1].upper()


def _by_product_id(blob) -> dict[str, dict]:
    """`productSummaries`/`availabilitySummaries` llegan como LISTA desde la API
    (cada item trae su productId), pero el estado SSR de xbox.com los expone como
    dict indexado por productId. Se indexa por el productId del propio item, que
    está en las dos formas."""
    items = blob.values() if isinstance(blob, dict) else (blob or [])
    return {it["productId"]: it for it in items
            if isinstance(it, dict) and it.get("productId")}


def _price_from(summary: dict, avail: dict | None) -> dict:
    """Menor precio comprable. Prioriza `specificPrices.purchaseable`; si no está,
    cae al `price` de la availability. Mismo criterio que `parse.py` usa sobre
    displaycatalog, para que las dos fuentes sean comparables."""
    offers = ((summary.get("specificPrices") or {}).get("purchaseable")) or []
    if not offers and avail:
        p = avail.get("price")
        if p:
            offers = [p]
    # las claves se devuelven SIEMPRE (aunque sea en None) para que la fila tenga
    # forma estable: los consumidores acceden por clave, no con .get()
    if not offers:
        return {"list_price": None, "msrp": None, "discount_pct": None, "currency": None}
    best = min(offers, key=lambda o: o.get("listPrice") if o.get("listPrice") is not None else 1e18)
    return {
        "list_price": best.get("listPrice"),
        "msrp": best.get("msrp"),
        "discount_pct": best.get("discountPercentage"),
        "currency": best.get("currency"),
    }


def parse_summary(pid: str, summary: dict, avail: dict | None,
                  locale: str, rank: int) -> dict:
    available_on = summary.get("availableOn") or []
    pass_ids = summary.get("includedWithPassesProductIds") or []
    pass_meta = summary.get("passMetadataByPassProductId") or {}
    # OJO: passMetadataByPassProductId es el HISTORIAL de membresía, no el estado
    # actual. Trae entradas/salidas de temporadas viejas (vistas desde 2021) y el
    # centinela 9998-12-30 = permanente. Para "sale del pass el X" solo valen:
    #   1) los passes en los que HOY está (pass_ids), y
    #   2) fechas futuras y no centinela.
    # Y se toma la MÁS PRÓXIMA de esas, no el min() global (que daría la más vieja).
    current = set(pass_ids)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    exits = [m.get("exitDateUTC") for pid, m in pass_meta.items()
             if pid in current and isinstance(m, dict) and m.get("exitDateUTC")]
    exits = [e for e in exits if now_iso < e < PERMANENT_SENTINEL]

    # Entradas FUTURAS = "llega al Game Pass el X" (day-one anunciados). Acá NO se
    # filtra por `current`: justamente lo interesante son los que todavía no están
    # en el pass. El mismo juego aparece una vez por tier (Console/Ultimate/PC),
    # así que se toma la fecha más próxima.
    entries = [m.get("entryDateUTC") for m in pass_meta.values()
               if isinstance(m, dict) and m.get("entryDateUTC")]
    entries = [e for e in entries if now_iso < e < PERMANENT_SENTINEL]
    hh = summary.get("hhVerified") or {}

    row = {
        "product_id": pid,
        "market": market_of(locale),
        "source": "browse",
        "locale": locale,
        "rank": rank,
        "available_on": available_on or None,
        "in_gamepass": bool(pass_ids),
        "pass_ids": pass_ids or None,
        "pass_exit_date": min(exits) if exits else None,
        "pass_entry_date": min(entries) if entries else None,
        "on_xcloud": "XCloud" in available_on,
        "on_handheld": "Handheld" in available_on,
        "handheld_tier": hh.get("deviceEvaluation"),
        "badges": [b.get("type") for b in (summary.get("badges") or [])
                   if isinstance(b, dict) and b.get("type") is not None] or None,
        "avg_rating": summary.get("averageRating"),
        "rating_count": summary.get("ratingCount"),
    }
    row.update(_price_from(summary, avail))
    return row


def parse_page(page_json: dict, locale: str, rank_start: int) -> tuple[list[dict], int]:
    """(filas, totalItems). El orden de `products` define el rank."""
    channels = page_json.get("channels") or {}
    if not channels:
        return [], 0
    channel = next(iter(channels.values()))
    summaries = _by_product_id(page_json.get("productSummaries"))
    avails = _by_product_id(page_json.get("availabilitySummaries"))

    rows = []
    for i, entry in enumerate(channel.get("products") or []):
        pid = entry.get("productId")
        if not pid:
            continue
        rows.append(parse_summary(pid, summaries.get(pid) or {}, avails.get(pid),
                                  locale, rank_start + i))
    return rows, channel.get("totalItems") or 0


def resume_state(raw_path: str, locale: str) -> tuple[set[str], set[int]]:
    """(ids ya vistos, páginas ya bajadas) releyendo el crudo local.

    Un barrido son ~340 requests de varios segundos: si se corta en la 249 hay
    que retomar ahí, no volver a empezar. El crudo ya en disco es la fuente de
    verdad del progreso (más fiable que la DB, que dedupea entre locales).

    Devuelve el CONJUNTO de páginas, no la última: si la 249 se salteó y la 250
    salió bien, retomar en 251 la perdería para siempre. Con el conjunto, los
    huecos se reintentan solos en la corrida siguiente."""
    if not os.path.exists(raw_path):
        return set(), set()
    seen: set[str] = set()
    pages: set[int] = set()
    with open(raw_path, "rb") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = _loads(line)
            except Exception:
                continue          # línea truncada por un corte abrupto: se descarta
            page = rec.get("page") or 0
            rows, _ = parse_page(rec.get("data") or {}, locale, page)
            if rows:
                pages.add(page)
                seen.update(r["product_id"] for r in rows)
    return seen, pages


def browse_locale(conn, client: EmeraldClient, locale: str,
                  max_pages: int | None = None, resume: bool = True) -> int:
    """Barre un locale entero. Corta cuando una página vuelve VACÍA (fin real del
    catálogo). Una página que FALLA no corta el barrido: se reintenta y, si sigue
    fallando, se saltea y se reporta al final."""
    max_pages = max_pages or config.BROWSE_MAX_PAGES
    raw_path = os.path.join(RAW_DIR, f"browse_{locale.lower()}.ndjson")

    seen: set[str] = set()
    have: set[int] = set()
    if resume:
        seen, have = resume_state(raw_path, locale)
        if have:
            print(f"[browse:{locale}] retomo: {len(have)} páginas ya bajadas "
                  f"(hasta la {max(have)}), {len(seen)} únicos", flush=True)
    raw = open(raw_path, "ab" if have else "wb")

    t0 = time.monotonic()
    total_items = 0
    n_rows = 0
    failed: list[int] = []
    start = 1
    page = start
    try:
        while page <= max_pages:
            if page in have:       # ya está en el crudo: ni se pide
                page += 1
                continue
            data = None
            for attempt in range(1, PAGE_RETRIES + 1):
                data = client.browse_page(locale, page)
                if data:
                    break
                # el cliente ya reintentó por dentro; acá esperamos MÁS por si es
                # un rate-limit sostenido y no un error puntual de esa página
                wait = PAGE_BACKOFF * attempt
                print(f"[browse:{locale}] pag {page}: sin respuesta "
                      f"({attempt}/{PAGE_RETRIES}), espero {wait}s", flush=True)
                time.sleep(wait)

            if not data:
                failed.append(page)
                print(f"[browse:{locale}] pag {page}: SALTEADA tras "
                      f"{PAGE_RETRIES} intentos", flush=True)
                page += 1
                continue

            raw.write(_dumps({"locale": locale, "page": page, "data": data}) + b"\n")
            raw.flush()       # que un corte no se lleve el buffer

            # rank anclado a la página, NO a len(seen): así no depende de en qué
            # orden se bajaron las páginas y un resume no corrompe el orden.
            rows, total = parse_page(data, locale, (page - 1) * PAGE_SIZE + 1)
            total_items = total or total_items
            if not rows:
                # vacía POR DETRÁS de la frontera = hueco raro, no el final
                if have and page < max(have):
                    failed.append(page)
                    print(f"[browse:{locale}] pag {page}: vacía pero hay páginas "
                          f"posteriores; la marco y sigo", flush=True)
                    page += 1
                    continue
                print(f"[browse:{locale}] pag {page}: vacía, fin del catálogo", flush=True)
                break

            # las páginas traen cantidades variables y podrían repetir: dedup por ID
            fresh = [r for r in rows if r["product_id"] not in seen]
            for r in fresh:
                seen.add(r["product_id"])
            n_rows += db.upsert_market_catalog(conn, fresh)

            if page % 20 == 0:
                dt = time.monotonic() - t0
                print(f"[browse:{locale}] pag {page} | únicos={len(seen)}/{total_items} "
                      f"| {dt:.0f}s", flush=True)
            page += 1
    except KeyboardInterrupt:
        print(f"[browse:{locale}] interrumpido en la página {page}; "
              f"volvé a correr para retomar", flush=True)
    finally:
        raw.close()

    dt = time.monotonic() - t0
    detail = (f"{locale}: {len(seen)} únicos / {total_items} totalItems")
    if failed:
        detail += f" | {len(failed)} páginas salteadas: {failed[:20]}"
        print(f"[browse:{locale}] ATENCIÓN: {len(failed)} páginas salteadas "
              f"{failed[:20]} — volvé a correr para reintentarlas", flush=True)
    print(f"[browse:{locale}] LISTO: {len(seen)} únicos de {total_items} declarados, "
          f"páginas {start}..{page - 1}, {dt:.0f}s -> {raw_path}", flush=True)
    db.log_run(conn, "browse", market_of(locale), "done", n_rows, detail)
    return len(seen)


def reparse_locale(conn, locale: str) -> int:
    """Reconstruye market_catalog desde el crudo, SIN tocar la red.

    Para esto se guarda el NDJSON: cuando se corrige el parseo (o se agrega un
    campo que antes se ignoraba) se rehace el barrido entero en segundos, en vez
    de volver a pedirle 339 páginas a Microsoft."""
    raw_path = os.path.join(RAW_DIR, f"browse_{locale.lower()}.ndjson")
    if not os.path.exists(raw_path):
        print(f"[reparse:{locale}] no existe {raw_path}", flush=True)
        return 0

    t0 = time.monotonic()
    seen: set[str] = set()
    n_rows = 0
    with open(raw_path, "rb") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = _loads(line)
            except Exception:
                continue
            page = rec.get("page") or 0
            rows, _ = parse_page(rec.get("data") or {}, locale, (page - 1) * PAGE_SIZE + 1)
            fresh = [r for r in rows if r["product_id"] not in seen]
            for r in fresh:
                seen.add(r["product_id"])
            n_rows += db.upsert_market_catalog(conn, fresh)

    dt = time.monotonic() - t0
    print(f"[reparse:{locale}] {len(seen)} productos reescritos en {dt:.0f}s", flush=True)
    db.log_run(conn, "browse-reparse", market_of(locale), "done", n_rows, locale)
    return len(seen)


HYDRATE_BATCH = 25     # con 26+ el endpoint responde "Too many products requested"


def missing_ids(conn, market: str, kind: str = "Juego") -> list[str]:
    """Productos COMPRABLES en `market` (según displaycatalog) que /browse no lista.

    /browse tiene entradas muertas: declara ~17k pero sirve ~15,4k en AR, y entre
    los que faltan hay títulos grandes (Star Wars Outlaws, AC Mirage). Esos IDs
    salen de `prices`, que es la verdad de comprabilidad."""
    with conn.cursor() as cur:
        cur.execute(
            "select pr.product_id from prices pr "
            "join products p on p.product_id = pr.product_id "
            "left join market_catalog m "
            "  on m.product_id = pr.product_id and m.market = pr.market "
            "where pr.market = %s and p.kind = %s and m.product_id is null "
            "order by pr.product_id",
            (market, kind),
        )
        return [r[0] for r in cur.fetchall()]


def hydrate_missing(conn, client: EmeraldClient, locale: str,
                    kind: str = "Juego") -> int:
    """Rescata por /products los que /browse no sirvió, y los guarda con
    source='products' para poder distinguir de dónde vino cada fila."""
    market = market_of(locale)
    ids = missing_ids(conn, market, kind)
    if not ids:
        print(f"[hydrate:{locale}] nada que rescatar", flush=True)
        return 0

    raw_path = os.path.join(RAW_DIR, f"hydrate_{locale.lower()}.ndjson")
    chunks = [ids[i:i + HYDRATE_BATCH] for i in range(0, len(ids), HYDRATE_BATCH)]
    print(f"[hydrate:{locale}] {len(ids)} faltantes en {len(chunks)} lotes "
          f"de {HYDRATE_BATCH}", flush=True)

    t0 = time.monotonic()
    n_rows = 0
    fallidos = 0
    with open(raw_path, "wb") as raw:
        for i, chunk in enumerate(chunks, 1):
            data = client.products(chunk, locale)
            if not data:
                fallidos += len(chunk)
                continue
            raw.write(_dumps({"locale": locale, "batch": i, "data": data}) + b"\n")

            summaries = _by_product_id(data.get("productSummaries"))
            avails = _by_product_id(data.get("availabilitySummaries"))
            rows = []
            for pid in chunk:
                s = summaries.get(pid)
                if not s:                     # el endpoint tampoco lo conoce
                    continue
                row = parse_summary(pid, s, avails.get(pid), locale, None)
                row["source"] = "products"    # NO pisa la fila de browse (PK incluye source)
                rows.append(row)
            n_rows += db.upsert_market_catalog(conn, rows)

            if i % 20 == 0 or i == len(chunks):
                print(f"[hydrate:{locale}] lote {i}/{len(chunks)} | "
                      f"{n_rows} filas | {time.monotonic() - t0:.0f}s", flush=True)

    dt = time.monotonic() - t0
    detail = f"{locale}: {n_rows} rescatados de {len(ids)} faltantes"
    if fallidos:
        detail += f" | {fallidos} en lotes fallidos"
    print(f"[hydrate:{locale}] LISTO: {detail}, {dt:.0f}s -> {raw_path}", flush=True)
    db.log_run(conn, "browse-hydrate", market, "done", n_rows, detail)
    return n_rows


def main(argv: list[str]) -> None:
    restart = "--restart" in argv          # ignora el crudo y arranca de cero
    reparse = "--reparse" in argv          # solo re-parsea el crudo, sin red
    hydrate = "--hydrate" in argv          # rescata por /products lo que browse no dio
    args = [a for a in argv if not a.startswith("--")]
    locales = [a for a in args if not a.isdigit()] or config.BROWSE_LOCALES
    pages = next((int(a) for a in args if a.isdigit()), None)

    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()
        if reparse:
            for loc in locales:
                reparse_locale(conn, loc)
            return
        client = EmeraldClient()
        if hydrate:
            for loc in locales:
                hydrate_missing(conn, client, loc)
            return
        for loc in locales:
            browse_locale(conn, client, loc, pages, resume=not restart)
    finally:
        conn.close()


if __name__ == "__main__":
    main(sys.argv[1:])

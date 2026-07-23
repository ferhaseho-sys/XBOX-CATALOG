"""Extraccion normalizada de un producto de DisplayCatalog (Xbox/Microsoft Store).

parse_product(json, market) -> fila para tabla `products`
parse_price(json, market)   -> fila para tabla `prices`

Reglas (derivadas de la auditoria del JSON US):
 - disponibilidad real = existe una Availability con 'Purchase' en Actions
 - mejor precio = min(ListPrice > 0) entre availabilities comprables
 - MSRP = precio tachado; descuento derivado
 - F2P real solo si TODAS las ofertas comprables son 0.0
 - ignora SKUs trial y ventanas de validez sin descuento
"""
from __future__ import annotations

IMAGE_PRIORITY = ["BoxArt", "Poster", "TitledHeroArt", "SuperHeroArt",
                  "BrandedKeyArt", "FeaturePromotionalSquareArt", "Screenshot"]

PERMANENT_END = "9998-12-30"


def _fix_uri(u: str) -> str:
    if not u:
        return ""
    return "https:" + u if u.startswith("//") else u


def _purchasable_prices(product: dict) -> list[dict]:
    out = []
    preferred = product.get("PreferredSkuId")
    for dsa in product.get("DisplaySkuAvailabilities", []) or []:
        sku = dsa.get("Sku", {}) or {}
        skp = sku.get("Properties", {}) or {}
        if (sku.get("SkuType") or "").lower() == "trial":
            continue
        # suscripciones: saltear SKUs ocultos (promos "2 months for $2", trials,
        # variantes legacy) para no tomar un precio irreal como el principal.
        if skp.get("IsSubscriptionHidden"):
            continue
        # recurrencia (subs): esta en Sku.RecurrencePolicy
        rp = sku.get("RecurrencePolicy") or {}
        dur = rp.get("Duration") or {}
        recurrence = None
        if rp.get("IsRecurring"):
            recurrence = f"{dur.get('Units', 1)} {dur.get('UnitType', 'Month')}"
        for av in dsa.get("Availabilities", []) or []:
            if "Purchase" not in (av.get("Actions") or []):
                continue
            price = (av.get("OrderManagementData", {}) or {}).get("Price", {}) or {}
            cond = av.get("Conditions", {}) or {}
            end = cond.get("EndDate") or ""
            out.append({
                "sku_id": sku.get("SkuId"),
                "is_preferred": sku.get("SkuId") == preferred,
                "currency": price.get("CurrencyCode"),
                "list_price": price.get("ListPrice"),
                "msrp": price.get("MSRP"),
                "start": cond.get("StartDate"),
                "end": end,
                "on_sale_window": bool(end) and not end.startswith(PERMANENT_END),
                "recurrence": recurrence,   # ej. "1 Month" para subs; None si no recurre
            })
    return out


def is_demo(product: dict) -> bool:
    """True si el producto es un demo/trial (no un juego gratis real)."""
    if (product.get("Properties", {}) or {}).get("IsDemo"):
        return True
    title = ((product.get("LocalizedProperties") or [{}])[0].get("ProductTitle") or "").lower()
    return "demo" in title or "trial edition" in title or "trial version" in title


def platforms(product: dict) -> tuple[bool, bool]:
    """(on_pc, on_xbox) según AllowedPlatforms de las availabilities comprables.
    Windows.Desktop = PC, Windows.Xbox = consola. Play Anywhere = ambos.
    (XboxXPA viene null en el JSON, así que las plataformas son la señal fiable.)"""
    pc = xb = False
    for dsa in product.get("DisplaySkuAvailabilities", []) or []:
        for av in dsa.get("Availabilities", []) or []:
            if not ({"Purchase", "Preorder"} & set(av.get("Actions") or [])):
                continue
            aps = (((av.get("Conditions") or {}).get("ClientConditions") or {})
                   .get("AllowedPlatforms") or [])
            for ap in aps:
                n = ap.get("PlatformName")
                if n == "Windows.Desktop":
                    pc = True
                elif n == "Windows.Xbox":
                    xb = True
    return pc, xb


def category(product: dict) -> str:
    """Categoría legible a partir de ProductType."""
    t = (product.get("ProductType") or "").upper()
    return {
        "GAME": "Juego", "DURABLE": "DLC", "CONSUMABLE": "Moneda",
        "UNMANAGEDCONSUMABLE": "Moneda", "PASS": "Suscripción", "CSV": "Gift card",
    }.get(t, product.get("ProductType") or "Otro")


def parse_price(product: dict, market: str) -> dict:
    pid = product.get("ProductId")
    offers = _purchasable_prices(product)
    if not offers:
        return {"product_id": pid, "market": market, "purchasable": False,
                "currency": None, "list_price": None, "msrp": None,
                "discount_pct": 0, "on_sale": False, "sale_ends": None,
                "is_free": False, "n_offers": 0, "n_paid_offers": 0}

    paid = [o for o in offers if (o["list_price"] or 0.0) > 0.0]
    # "Free" SOLO para juegos F2P reales: Game, no demo, y todo comprable a 0.
    # (demos y DLC/consumibles a $0 tienen precio 0 pero NO son juegos gratis)
    # `fieldsTemplate=Browse` no devuelve ProductType, pero sí ProductKind, y en
    # los 43k productos los dos campos coinciden siempre. Se acepta cualquiera
    # para que el mismo parseo sirva con las dos plantillas.
    kind = product.get("ProductType") or product.get("ProductKind")
    is_free = (len(paid) == 0 and kind == "Game" and not is_demo(product))

    pool = paid if paid else offers
    best = min(pool, key=lambda o: (o["list_price"] if o["list_price"] is not None else 1e18))
    list_price = best["list_price"] or 0.0
    msrp = best["msrp"] if best["msrp"] is not None else list_price
    discount = int(round(100 * (msrp - list_price) / msrp)) if msrp and msrp > 0 else 0

    return {
        "product_id": pid,
        "market": market,
        "purchasable": True,
        "currency": best["currency"],
        "list_price": round(float(list_price), 2),
        "msrp": round(float(msrp), 2),
        "discount_pct": max(0, discount),
        "on_sale": discount > 0,
        "sale_ends": best["end"] if (discount > 0 and best["on_sale_window"]) else None,
        "is_free": is_free,
        "n_offers": len(offers),
        "n_paid_offers": len(paid),
        "recurrence": best.get("recurrence"),   # "1 Month" para subs; None si no
    }


def parse_variants(product: dict, market: str) -> list[dict]:
    """TODAS las variantes (SKUs) de un producto: duraciones, promos, ocultas.
    Para el drill-down 'ver producto -> ver sus variantes'. No filtra nada:
    el precio principal (parse_price) es el titular; esto es el menu completo."""
    pid = product.get("ProductId")
    out = []
    for dsa in product.get("DisplaySkuAvailabilities", []) or []:
        sku = dsa.get("Sku", {}) or {}
        skp = sku.get("Properties", {}) or {}
        slp = (sku.get("LocalizedProperties") or [{}])[0]
        rp = sku.get("RecurrencePolicy") or {}
        dur = rp.get("Duration") or {}
        price = cur = None
        purchasable = False
        for av in dsa.get("Availabilities", []) or []:
            acts = av.get("Actions") or []
            pr = (av.get("OrderManagementData", {}) or {}).get("Price", {}) or {}
            if "Purchase" in acts:
                purchasable = True
            if pr.get("ListPrice") is not None and price is None:
                price = pr.get("ListPrice"); cur = pr.get("CurrencyCode")
        title = slp.get("SkuTitle") or slp.get("SkuButtonTitle") or sku.get("SkuId")
        out.append({
            "product_id": pid,
            "market": market,
            "sku_id": sku.get("SkuId"),
            "title": title,
            "duration": (f"{dur.get('Units')} {dur.get('UnitType')}"
                         if dur.get("Units") else None),
            "is_hidden": bool(skp.get("IsSubscriptionHidden")),
            "is_recurring": bool(rp.get("IsRecurring")),
            "purchasable": purchasable,
            "currency": cur,
            "list_price": (round(float(price), 2) if price is not None else None),
        })
    return out


def parse_media(product: dict) -> dict:
    """Medios ricos para la ficha: screenshots, tráiler, descripción larga,
    capacidades (Attributes) y géneros. Se extrae en vivo (no se guarda en DB)."""
    lp = (product.get("LocalizedProperties") or [{}])[0]
    props = product.get("Properties", {}) or {}
    shots = [_fix_uri(im.get("Uri", "")) for im in (lp.get("Images") or [])
             if (im.get("ImagePurpose") or "") == "Screenshot" and im.get("Uri")]
    trailer = ""
    for v in lp.get("CMSVideos", []) or []:
        if (v.get("VideoPurpose") or "") == "trailer":
            trailer = v.get("HLS") or v.get("DASH") or ""
            break
    attrs = [a.get("Name") for a in (props.get("Attributes") or []) if a.get("Name")]
    return {
        "product_id": product.get("ProductId"),
        "title": lp.get("ProductTitle"),
        "description": lp.get("ProductDescription") or lp.get("ShortDescription"),
        "developer": lp.get("DeveloperName"),
        "publisher": lp.get("PublisherName"),
        "screenshots": shots[:12],
        "trailer": trailer,
        "capabilities": attrs[:24],
        "categories": props.get("Categories") or [],
    }


def parse_product(product: dict, market: str = "US") -> dict:
    pid = product.get("ProductId")
    props = product.get("Properties", {}) or {}
    lp = (product.get("LocalizedProperties") or [{}])[0]
    mp = (product.get("MarketProperties") or [{}])[0]
    _plats = platforms(product)   # (on_pc, on_xbox)

    imgs = {}
    for im in lp.get("Images", []) or []:
        imgs.setdefault(im.get("ImagePurpose"), _fix_uri(im.get("Uri", "")))
    hero = next((imgs[p] for p in IMAGE_PRIORITY if imgs.get(p)), "")

    trailer = ""
    for v in lp.get("CMSVideos", []) or []:
        if (v.get("VideoPurpose") or "") == "trailer":
            trailer = v.get("HLS") or v.get("DASH") or ""
            break

    avg_rating = rating_count = None
    for u in mp.get("UsageData", []) or []:
        if u.get("AggregateTimeSpan") == "AllTime":
            avg_rating = u.get("AverageRating")
            rating_count = u.get("RatingCount")

    ratings = {r.get("RatingSystem"): r.get("RatingId")
               for r in mp.get("ContentRatings", []) or []}
    alt = {a.get("IdType"): a.get("Value") for a in product.get("AlternateIds", []) or []}
    markets = lp.get("Markets") or []

    return {
        "product_id": pid,
        "title": lp.get("ProductTitle"),
        "short_title": lp.get("ShortTitle"),
        "short_desc": (lp.get("ShortDescription") or "")[:600] or None,
        "description": lp.get("ProductDescription"),
        "product_type": product.get("ProductType"),
        "product_kind": product.get("ProductKind"),
        "product_family": product.get("ProductFamily"),
        "developer": lp.get("DeveloperName"),
        "publisher": lp.get("PublisherName"),
        "category": props.get("Category"),
        "kind": category(product),          # legible: Juego/DLC/Moneda/Suscripción/Gift card
        "is_demo": is_demo(product),        # demo/trial (no F2P real)
        "on_pc": _plats[0],                 # Windows.Desktop -> corre en PC
        "on_xbox": _plats[1],               # Windows.Xbox -> corre en consola
        "categories": props.get("Categories") or [],
        "release_date": (mp.get("OriginalReleaseDate") or "")[:10] or None,
        "min_user_age": mp.get("MinimumUserAge"),
        "is_ms_product": product.get("IsMicrosoftProduct"),
        "has_addons": props.get("HasAddOns"),
        "console_gen": props.get("XboxConsoleGenOptimized") or props.get("XboxConsoleGenCompatible") or [],
        "gold_required": props.get("XboxLiveGoldRequired"),
        "image_hero": hero,
        "image_boxart": imgs.get("BoxArt", ""),
        "image_poster": imgs.get("Poster", ""),
        "trailer": trailer,
        "avg_rating": avg_rating,
        "rating_count": rating_count,
        "ratings": ratings,
        "xbox_title_id": alt.get("XboxTitleId"),
        "available_markets": [m for m in markets if m != "NEUTRAL"],
        "n_available_markets": len([m for m in markets if m != "NEUTRAL"]),
        "last_modified": product.get("LastModifiedDate"),
    }

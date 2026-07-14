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


def parse_price(product: dict, market: str) -> dict:
    pid = product.get("ProductId")
    offers = _purchasable_prices(product)
    if not offers:
        return {"product_id": pid, "market": market, "purchasable": False,
                "currency": None, "list_price": None, "msrp": None,
                "discount_pct": 0, "on_sale": False, "sale_ends": None,
                "is_free": False, "n_offers": 0, "n_paid_offers": 0}

    paid = [o for o in offers if (o["list_price"] or 0.0) > 0.0]
    is_free = len(paid) == 0

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


def parse_product(product: dict, market: str = "US") -> dict:
    pid = product.get("ProductId")
    props = product.get("Properties", {}) or {}
    lp = (product.get("LocalizedProperties") or [{}])[0]
    mp = (product.get("MarketProperties") or [{}])[0]

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

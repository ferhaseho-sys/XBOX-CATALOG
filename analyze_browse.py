"""Medición de la Fase 1: qué aporta Emerald Browse sobre el catálogo actual.

Trabaja sobre el NDJSON crudo (offline). Solo toca la DB para pedir la lista de
product_id y, si se pide, los precios del mercado a contrastar.

Uso:
  python analyze_browse.py browse_es-ar.ndjson          # solo el crudo
  python analyze_browse.py browse_es-ar.ndjson --db     # + comparar con la DB
"""
import collections
import sys

try:
    import orjson as J
    loads = J.loads
except Exception:
    import json as J
    loads = J.loads

from atlas.browse import parse_page


def read_rows(path):
    """Reconstruye las filas parseadas desde el crudo, igual que la ingesta."""
    rows, seen, total_items, pages = [], set(), 0, 0
    for line in open(path, "rb"):
        if not line.strip():
            continue
        rec = loads(line)
        pages += 1
        page_rows, total = parse_page(rec["data"], rec["locale"], len(seen) + 1)
        total_items = total or total_items
        for r in page_rows:
            if r["product_id"] not in seen:
                seen.add(r["product_id"])
                rows.append(r)
    return rows, total_items, pages


def report_raw(rows, total_items, pages):
    print(f"=== crudo: {pages} páginas, {len(rows)} productos únicos "
          f"(totalItems declarado: {total_items}) ===")
    if pages and total_items:
        por_pag = len(rows) / pages
        faltan = total_items - len(rows)
        # las páginas rinden ~47, no 50: proyectar antes de gritar "faltan"
        print(f"  {por_pag:.1f} productos únicos por página; "
              f"para {total_items} harían falta ~{total_items / por_pag:.0f} páginas")
        if faltan > 0:
            print(f"  faltan {faltan} -> seguí paginando (o revisá páginas salteadas)")

    def pct(n):
        return f"{n:6d}  ({100 * n / max(len(rows), 1):5.1f}%)"

    print(f"  en Game Pass      : {pct(sum(1 for r in rows if r['in_gamepass']))}")
    print(f"  en xCloud         : {pct(sum(1 for r in rows if r['on_xcloud']))}")
    print(f"  handheld          : {pct(sum(1 for r in rows if r['on_handheld']))}")
    print(f"  con precio         : {pct(sum(1 for r in rows if r['list_price'] is not None))}")
    print(f"  con rating         : {pct(sum(1 for r in rows if r['rating_count']))}")
    print(f"  con fecha salida GP: {pct(sum(1 for r in rows if r['pass_exit_date']))}")

    plats = collections.Counter()
    for r in rows:
        for p in (r["available_on"] or []):
            plats[p] += 1
    print("  plataformas:", dict(plats.most_common()))

    badges = collections.Counter()
    for r in rows:
        for b in (r["badges"] or []):
            badges[b] += 1
    print("  badges (type -> n):", dict(badges.most_common(12)))

    ranked = [r for r in rows if r["list_price"]]
    if ranked:
        top = sorted(ranked, key=lambda r: r["rank"])[:5]
        print("  top 5 por rank:")
        for r in top:
            gp = " [GamePass]" if r["in_gamepass"] else ""
            print(f"    #{r['rank']:<4} {r['product_id']}  "
                  f"{r['list_price']} {r['currency']}{gp}")


def report_db(rows):
    from atlas import db
    conn = db.connect()
    try:
        known = db.known_product_ids(conn)
        ids = {r["product_id"] for r in rows}
        inter = ids & known
        print(f"\n=== contra la DB ({len(known)} productos en `products`) ===")
        print(f"  Browse ∩ DB     : {len(inter)}  ({100 * len(inter) / max(len(ids), 1):.1f}% de Browse)")
        print(f"  nuevos (Browse∖DB): {len(ids - known)}")
        print(f"  en DB y no en Browse: {len(known - ids)}  "
              f"(esperado: DLC/consumibles, Browse solo trae Games)")
        nuevos = sorted(ids - known)[:15]
        if nuevos:
            print(f"  muestra de nuevos: {nuevos}")

        # contraste de precios: Browse vs displaycatalog para el mismo mercado
        market = rows[0]["market"]
        with conn.cursor() as cur:
            cur.execute("select product_id, list_price from prices where market=%s", (market,))
            db_prices = {p: lp for p, lp in cur.fetchall()}
        comunes = [r for r in rows
                   if r["list_price"] is not None and r["product_id"] in db_prices]
        difs = [(r["product_id"], r["list_price"], db_prices[r["product_id"]])
                for r in comunes
                if abs(float(r["list_price"]) - float(db_prices[r["product_id"]])) > 0.01]
        print(f"\n  precios comparables en {market}: {len(comunes)}")
        print(f"  divergencias Browse vs displaycatalog: {len(difs)}"
              f"  ({100 * len(difs) / max(len(comunes), 1):.1f}%)")
        for d in difs[:10]:
            print(f"    {d[0]}  browse={d[1]}  displaycatalog={d[2]}")
    finally:
        conn.close()


def main(argv):
    path = argv[0] if argv else "browse_es-ar.ndjson"
    rows, total_items, pages = read_rows(path)
    report_raw(rows, total_items, pages)
    if "--db" in argv:
        report_db(rows)


if __name__ == "__main__":
    main(sys.argv[1:])

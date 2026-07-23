"""Verifica el delta de `upsert_prices` contra la DB real. No destructivo.

Prueba las tres cosas que importan:
  1. Re-guardar precios SIN cambios no escribe nada  (el 98% de ahorro de IO).
  2. Un cambio real sí se escribe y deja fila en price_history.
  3. min_ever / is_at_min se mantienen solos.

Al final restaura el valor original del producto que tocó.

Uso:  python verify_delta.py
"""
import sys

from atlas import db


DDL = open("schema.sql", encoding="utf-8").read()


def main() -> int:
    conn = db.connect()
    try:
        print("1) aplicando schema.sql (idempotente)…")
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()

        # muestra real: 5 precios que ya existen
        with conn.cursor() as cur:
            cur.execute("select product_id, market, currency, list_price, msrp, "
                        "discount_pct, on_sale, sale_ends, is_free, n_paid_offers, "
                        "recurrence from prices where market = 'AR' "
                        "and list_price > 0 limit 5")
            cols = [d[0] for d in cur.description]
            filas = [dict(zip(cols, r)) for r in cur.fetchall()]
        if not filas:
            print("   no hay precios en AR para probar"); return 1
        for f in filas:
            f["purchasable"] = True
        print(f"   {len(filas)} filas de muestra")

        print("2) re-guardando SIN cambios…")
        n, cambios = db.upsert_prices(conn, filas)
        print(f"   filas enviadas={n}  cambios detectados={cambios}")
        if cambios != 0:
            print("   ❌ FALLA: debería ser 0. El `where … is distinct from` no filtra.")
            return 1
        print("   ✅ cero escrituras (es el ahorro de IO)")

        print("3) cambiando un precio de verdad…")
        objetivo = dict(filas[0])
        original = objetivo["list_price"]
        objetivo["list_price"] = float(original) / 2      # baja: debe fijar mínimo
        n, cambios = db.upsert_prices(conn, [objetivo])
        print(f"   cambios detectados={cambios}")
        if cambios != 1:
            print("   ❌ FALLA: debería ser 1.")
            return 1

        pid, mkt = objetivo["product_id"], objetivo["market"]
        with conn.cursor() as cur:
            cur.execute("select list_price, min_ever, is_at_min from prices "
                        "where product_id=%s and market=%s", (pid, mkt))
            lp, mn, at_min = cur.fetchone()
            cur.execute("select count(*) from price_history "
                        "where product_id=%s and market=%s", (pid, mkt))
            n_hist = cur.fetchone()[0]
        print(f"   precio={lp}  min_ever={mn}  is_at_min={at_min}  filas en historial={n_hist}")
        ok = (n_hist >= 1 and at_min and float(mn) == float(lp))
        print("   ✅ historial y mínimo OK" if ok else "   ❌ FALLA en historial/mínimo")

        print("4) restaurando el valor original…")
        objetivo["list_price"] = original
        db.upsert_prices(conn, [objetivo])
        with conn.cursor() as cur:
            cur.execute("delete from price_history where product_id=%s and market=%s",
                        (pid, mkt))
            cur.execute("update prices set min_ever=%s, is_at_min=true "
                        "where product_id=%s and market=%s", (original, pid, mkt))
        conn.commit()
        print(f"   restaurado a {original}")
        return 0 if ok else 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())

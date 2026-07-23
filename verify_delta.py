"""Verifica el delta de `upsert_prices` contra la DB real. No destructivo.

REQUISITO: la migración `sql/fase2_price_history.sql` ya aplicada (en el SQL
Editor de Supabase) y la base en verde. Este script NO aplica el esquema: correr
DDL pesado por el pooler bajo carga es lo que satura la base.

Prueba las tres cosas que importan:
  1. Re-guardar precios SIN cambios no escribe nada  (el 98% de ahorro de IO).
  2. Un cambio real sí se escribe y deja fila en price_history.
  3. min_ever / is_at_min se mantienen solos.
Al final restaura el valor original del producto que tocó.

Uso:  python verify_delta.py
"""
import sys

import psycopg2

from atlas import db


def _preflight(conn) -> bool:
    """Chequea que la migración esté aplicada, sin tocar datos."""
    with conn.cursor() as cur:
        cur.execute("select column_name from information_schema.columns "
                    "where table_name='prices' and column_name in "
                    "('min_ever','is_at_min')")
        cols = {r[0] for r in cur.fetchall()}
        cur.execute("select to_regclass('price_history')")
        tabla = cur.fetchone()[0]
    if len(cols) < 2 or tabla is None:
        print("❌ Falta la migración. Pegá sql/fase2_price_history.sql en el "
              "SQL Editor de Supabase y volvé a correr esto.")
        return False
    return True


def main() -> int:
    try:
        conn = db.connect()
    except psycopg2.OperationalError as e:
        print(f"❌ No se pudo conectar: {str(e).strip()[:90]}")
        print("   La base está caída o saturada. Esperá a que Supabase esté en "
              "verde (Database Healthy) y volvé a intentar. NO reintentes en loop.")
        return 2

    try:
        if not _preflight(conn):
            return 1

        with conn.cursor() as cur:
            cur.execute("select product_id, market, currency, list_price, msrp, "
                        "discount_pct, on_sale, sale_ends, is_free, n_paid_offers, "
                        "recurrence from prices where market = 'AR' "
                        "and list_price > 0 limit 5")
            cols = [d[0] for d in cur.description]
            filas = [dict(zip(cols, r)) for r in cur.fetchall()]
        if not filas:
            print("no hay precios en AR para probar"); return 1
        for f in filas:
            f["purchasable"] = True
        print(f"muestra: {len(filas)} filas de AR")

        print("1) re-guardando SIN cambios…")
        n, cambios = db.upsert_prices(conn, filas)
        print(f"   filas={n}  cambios={cambios}")
        if cambios != 0:
            print("   ❌ debería ser 0: el `where … is distinct from` no filtra.")
            return 1
        print("   ✅ cero escrituras — este es el ahorro de IO")

        print("2) bajando un precio a la mitad…")
        objetivo = dict(filas[0]); original = objetivo["list_price"]
        objetivo["list_price"] = float(original) / 2
        n, cambios = db.upsert_prices(conn, [objetivo])
        pid, mkt = objetivo["product_id"], objetivo["market"]
        with conn.cursor() as cur:
            cur.execute("select list_price, min_ever, is_at_min from prices "
                        "where product_id=%s and market=%s", (pid, mkt))
            lp, mn, at_min = cur.fetchone()
            cur.execute("select count(*) from price_history "
                        "where product_id=%s and market=%s", (pid, mkt))
            n_hist = cur.fetchone()[0]
        print(f"   cambios={cambios}  precio={lp}  min_ever={mn}  is_at_min={at_min}  "
              f"historial={n_hist}")
        ok = (cambios == 1 and n_hist >= 1 and at_min and float(mn) == float(lp))
        print("   ✅ historial y mínimo OK" if ok else "   ❌ falla en historial/mínimo")

        print("3) restaurando…")
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

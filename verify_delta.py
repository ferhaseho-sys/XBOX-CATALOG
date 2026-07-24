"""Verifica el delta de `upsert_prices` contra Postgres real.

AUTOSUFICIENTE: crea su propio producto de prueba, lo usa, y lo borra al final.
No lee ni toca datos reales, así que corre igual con la base vacía o llena.

Prueba las cuatro cosas que importan:
  1. Insertar precios nuevos.
  2. Re-guardar SIN cambios no escribe nada  -> el 98% de ahorro de IO.
  3. Un cambio real se escribe y deja fila en price_history.
  4. min_ever / min_ever_on / is_at_min se mantienen solos, y un precio que SUBE
     no pisa el mínimo histórico.

Uso:  python verify_delta.py
"""
import sys
from datetime import date

import psycopg2

from atlas import db

PID = "__TESTDELTA"       # id reservado; no colisiona con los de Microsoft (12 hex)
MKT = "AR"


def _limpiar(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("delete from price_history where product_id = %s", (PID,))
        cur.execute("delete from prices        where product_id = %s", (PID,))
        cur.execute("delete from products      where product_id = %s", (PID,))
    conn.commit()


def _precio(valor: float) -> dict:
    return {"product_id": PID, "market": MKT, "purchasable": True, "currency": "ARS",
            "list_price": valor, "msrp": valor, "discount_pct": 0, "on_sale": False,
            "sale_ends": None, "is_free": False, "n_paid_offers": 1, "recurrence": None}


def _estado(conn):
    with conn.cursor() as cur:
        cur.execute("select list_price, min_ever, min_ever_on, is_at_min from prices "
                    "where product_id=%s and market=%s", (PID, MKT))
        fila = cur.fetchone()
        cur.execute("select count(*) from price_history where product_id=%s", (PID,))
        n_hist = cur.fetchone()[0]
    return fila, n_hist


def main() -> int:
    try:
        conn = db.connect()
    except psycopg2.OperationalError as e:
        print(f"FALLA: No se pudo conectar: {str(e).strip()[:100]}")
        print("   Revisá DATABASE_URL (desde tu PC va la URL PÚBLICA).")
        return 2

    fallas = []
    try:
        with conn.cursor() as cur:
            cur.execute("select to_regclass('price_history'), "
                        "(select count(*) from information_schema.columns "
                        " where table_name='prices' and column_name in ('min_ever','is_at_min'))")
            tabla, n_cols = cur.fetchone()
        if tabla is None or n_cols < 2:
            print("FALLA: Falta la migración. Corré `python apply_schema.py` primero.")
            return 1

        _limpiar(conn)
        db.upsert_products(conn, [{"product_id": PID, "title": "Producto de prueba",
                                   "kind": "Juego"}])

        print("1) insertando precio nuevo (1000)…")
        n, cambios = db.upsert_prices(conn, [_precio(1000)])
        (lp, mn, mn_on, at_min), n_hist = _estado(conn)
        print(f"   precio={lp}  min_ever={mn}  is_at_min={at_min}  historial={n_hist}")
        if not (float(lp) == 1000 and float(mn) == 1000 and at_min):
            fallas.append("el insert no sembró bien el mínimo")

        print("2) re-guardando el MISMO precio…")
        n, cambios = db.upsert_prices(conn, [_precio(1000)])
        print(f"   cambios detectados = {cambios}")
        if cambios != 0:
            fallas.append(f"debería ser 0 cambios y dio {cambios}: el "
                          "`where … is distinct from` no filtra (sin ahorro de IO)")
        else:
            print("   OK: cero escrituras - este es el ahorro de IO")

        print("3) bajando el precio a 400…")
        n, cambios = db.upsert_prices(conn, [_precio(400)])
        (lp, mn, mn_on, at_min), n_hist = _estado(conn)
        print(f"   cambios={cambios}  precio={lp}  min_ever={mn}  min_ever_on={mn_on}  "
              f"is_at_min={at_min}  historial={n_hist}")
        if cambios != 1:
            fallas.append("una baja de precio no se detectó como cambio")
        if not (float(mn) == 400 and at_min and mn_on == date.today()):
            fallas.append("la baja no actualizó el mínimo histórico")
        if n_hist < 1:
            fallas.append("la baja no dejó fila en price_history")

        print("4) subiendo el precio a 900 (el mínimo NO debe moverse)…")
        n, cambios = db.upsert_prices(conn, [_precio(900)])
        (lp, mn, mn_on, at_min), n_hist = _estado(conn)
        print(f"   cambios={cambios}  precio={lp}  min_ever={mn}  is_at_min={at_min}  "
              f"historial={n_hist}")
        if float(mn) != 400:
            fallas.append(f"una SUBA pisó el mínimo histórico (quedó {mn}, debía ser 400)")
        if at_min:
            fallas.append("is_at_min quedó en true con el precio por encima del mínimo")

        print("\n" + ("FALLA: FALLAS:" if fallas else "OK: TODO OK - el delta funciona"))
        for f in fallas:
            print("   -", f)
        return 1 if fallas else 0
    finally:
        _limpiar(conn)
        conn.close()
        print("(datos de prueba borrados)")


if __name__ == "__main__":
    sys.exit(main())

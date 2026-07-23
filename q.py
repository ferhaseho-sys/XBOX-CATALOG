"""Consola SQL mínima contra la DB del proyecto (reemplaza a `psql`, que no está
instalado en Windows). Usa el mismo DATABASE_URL que la ingesta.

Uso:
  python q.py "select market, count(*) from market_catalog group by market"
  python q.py -f consulta.sql
  echo "select 1" | python q.py

Solo lectura por convención: para DDL/DML usá el SQL Editor de Supabase.
"""
import sys

from atlas import db


def run(sql: str) -> None:
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            if cur.description is None:
                print(f"OK ({cur.rowcount} filas afectadas)")
                conn.commit()
                return
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
    finally:
        conn.close()

    widths = [len(c) for c in cols]
    text = [[("" if v is None else str(v)) for v in r] for r in rows]
    for r in text:
        widths = [max(w, len(v)) for w, v in zip(widths, r)]
    line = "  ".join(c.ljust(w) for c, w in zip(cols, widths))
    print(line)
    print("-" * len(line))
    for r in text:
        print("  ".join(v.ljust(w) for v, w in zip(r, widths)))
    print(f"\n({len(rows)} filas)")


def main(argv: list[str]) -> None:
    if argv and argv[0] == "-f":
        sql = open(argv[1], encoding="utf-8").read()
    elif argv:
        sql = " ".join(argv)
    else:
        sql = sys.stdin.read()
    if not sql.strip():
        print(__doc__)
        return
    run(sql)


if __name__ == "__main__":
    main(sys.argv[1:])

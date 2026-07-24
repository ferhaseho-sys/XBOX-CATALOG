"""Aplica schema.sql completo a la base de DATABASE_URL.

Pensado para inicializar una base NUEVA (ej. Railway Postgres) desde cero. Es
idempotente (`create ... if not exists`), así que correrlo dos veces no rompe
nada. Sobre una base vacía es instantáneo.

Uso (con la URL de la base nueva en el .env o en el entorno):
    python apply_schema.py
"""
import sys

import psycopg2

from atlas import db


def main() -> int:
    sql = open("schema.sql", encoding="utf-8").read()
    try:
        conn = db.connect()
    except psycopg2.OperationalError as e:
        print(f"FALLA: No se pudo conectar: {str(e).strip()[:100]}")
        print("   Revisá que DATABASE_URL apunte a la base nueva y que esté arriba.")
        return 2
    try:
        with conn.cursor() as cur:
            cur.execute(sql)          # psycopg2 acepta varios statements juntos
        conn.commit()
        # confirmación: contar las tablas que deberían existir
        with conn.cursor() as cur:
            cur.execute("select count(*) from information_schema.tables "
                        "where table_schema='public' and table_name in "
                        "('products','prices','price_history','market_catalog',"
                        "'variants','deals','fx_rates','ingest_runs','product_relations')")
            n = cur.fetchone()[0]
        print(f"OK: schema aplicado - {n}/9 tablas principales presentes")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())

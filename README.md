# Xbox Price Atlas

Ingesta del catálogo mundial de la Microsoft Store (Xbox) y sus precios en los
**243 mercados**, para construir una página de comparación de precios y análisis
de cobertura (qué juego está en qué país y a cuánto).

No usa scraping de terceros: descubre el catálogo por los **sitemaps oficiales**
de Xbox y obtiene precio/disponibilidad de la **API pública `displaycatalog`**.

## Arquitectura

```
sitemaps xbox.com  ──▶  discovery  ──▶  products (IDs + metadata + Markets[243])
                                            │
displaycatalog API ──▶  pricing   ──▶  prices (product_id × market, comprables)
                                            │
                        fx_rates  ──▶  price_usd (normalización)
```

- **Datos:** Supabase (Postgres). Esquema en [`schema.sql`](schema.sql).
- **Ingesta:** worker Python (este repo), desplegable en Railway.
- **Verdad de disponibilidad:** una availability con `Purchase` en `Actions`
  (no basta con estar listado en el sitemap).
- **Precio:** menor `ListPrice > 0` entre ofertas comprables; `MSRP` = tachado.

## Puesta en marcha

1. Crear proyecto en Supabase y ejecutar `schema.sql` en el SQL Editor.
2. `cp .env.example .env` y poner el `DATABASE_URL` del **pooler** (puerto 6543).
3. `pip install -r requirements.txt`
4. Ingesta:
   ```bash
   python -m atlas.run_ingest discovery          # sitemaps -> products
   python -m atlas.run_ingest pricing US GB JP NG # precios de prueba en 4 mercados
   python -m atlas.run_ingest pricing             # todos los 243 (largo)
   ```

## Escala (a tener en cuenta)

- Universo ≈ 45k productos. La fase pricing recorre hasta 243 mercados, pero solo
  pide precio donde `available_markets` incluye el mercado (menos llamadas).
- Es **resumible**: cada fase hace upsert idempotente y registra en `ingest_runs`.
  Se puede correr por tandas de mercados.

## Pendiente (siguientes pasos)

- `fx.py`: cargar `fx_rates` y calcular `price_usd`.
- API de lectura (FastAPI/Flask) + frontend: rankings, ficha con mapa de precios,
  cobertura/rareza, mayor spread mundial.

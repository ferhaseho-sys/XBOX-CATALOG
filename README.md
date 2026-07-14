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

## Deploy (Railway + Supabase)

Un solo repo, **dos servicios** en el mismo proyecto de Railway:

1. **Servicio web (API + frontend)** — usa `railway.json`:
   `uvicorn api.main:app` con healthcheck en `/health`.
2. **Servicio cron (refresco diario)** — mismo repo, *Custom Start Command*:
   `python -m atlas.refresh` y un *Cron Schedule* (ej. `0 6 * * *`).

Variables de entorno (ambos servicios): `DATABASE_URL` (pooler Supabase :6543),
`REQ_RATE`, `BATCH_SIZE`, `MARKET_WORKERS`. En el cron, opcional
`MARKETS_REFRESH=US,GB,AR,...` para limitar los mercados del refresco.

La primera carga (`discovery` + `pricing` completo de 243 mercados) conviene
correrla a mano una vez: `railway run python -m atlas.run_ingest discovery`, etc.

## API

`/api/search?term=` · `/api/cheapest?market=US` · `/api/deals?market=US` ·
`/api/exclusives?max_markets=5` · `/api/spread` · `/api/product/{id}` ·
`/api/stats` · `/api/markets` · `/health`

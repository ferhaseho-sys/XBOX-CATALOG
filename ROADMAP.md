# Xbox Price Atlas — Handoff & Roadmap

Documento para continuar el proyecto en un chat nuevo. Leé esto primero.

---

## 1. Qué es

Comparador mundial de precios de la Microsoft Store (Xbox), estilo xbox-now pero
con **datos oficiales de la API de Microsoft** (sin scraping). Muestra cada juego
con su precio en US y en la región más barata, ordenado por mejor oferta.

## 2. Dónde vive todo

- **Repo (deploy):** https://github.com/ferhaseho-sys/XBOX-CATALOG — dueño `ferhaseho-sys`.
  Carpeta local: `C:\Users\User\Desktop\Python\Python\xbox-price-atlas` (Python backend + API + build del frontend).
- **Repo (frontend fuente):** `C:\Users\User\Desktop\Python\Python\XboxNow Professional Scraper Web Application`
  (app React/Vite exportada de Figma; su propio git). **No tiene remoto**, solo local.
- **App en vivo:** https://web-production-2b5be.up.railway.app (Railway).
- **Base de datos:** Supabase (proyecto `qvwtvjbxzdmfrmmdueoo`), **plan free NANO**.

## 3. Arquitectura

```
sitemaps xbox.com ─▶ discovery ─▶ products (catálogo, ~43k)
displaycatalog API ─▶ pricing ─▶ prices (juego × mercado, 47 mercados)
open.er-api.com ─▶ fx ─▶ price_usd
prices ─▶ deals (resumen: región más barata + ahorro% por juego)  ← ordenar rápido
FastAPI (api/) ─▶ sirve la API + el build del frontend React
```

**Backend** (`atlas/`): `discovery.py` (sitemaps→IDs), `pricing.py` + `run_ingest.py`
(precios, cola plana + orjson), `fx.py` (USD), `deals.py` (resumen de ofertas),
`refresh.py` (cron diario: pricing+fx+deals), `parse.py` (extracción JSON),
`http_client.py` (cliente resiliente), `markets.py` (242 mercados), `config.py`, `db.py`.

**API** (`api/`): `main.py` (endpoints + CORS + sirve `frontend/`), `queries.py` (lecturas).
Endpoints clave: `/api/catalog` (ordenable, desde `deals`), `/api/product/{id}`,
`/api/live/product/{id}` (consulta EN VIVO a Microsoft, con variantes), `/api/search`,
`/api/fx`, `/api/markets/all`, `/api/analysis/start` (dispara ingesta).

**Frontend** (Figma app): `src/app/App.tsx` + `components/` + `hooks/useScraper.ts`
(catálogo) + `hooks/useXboxAPI.ts` (precios regionales en vivo). Componentes propios:
`GameCards.tsx` (catálogo estilo xbox-now), `RegionalPriceExplorer`, `XboxProductViewer`,
`VariantExplorer`, `GameTable`. Apunta a la API vía `VITE_ATLAS_API` (`.env.production`).

## 4. Flujo de build/deploy (IMPORTANTE)

El frontend React se compila y se **copia** al repo Python, que Railway sirve:
```
cd "XboxNow Professional Scraper Web Application" && npm run build   # -> dist/
cp -r dist/* ../xbox-price-atlas/frontend/
cd ../xbox-price-atlas && git add -A && git commit -m "..." && git push   # Railway redespliega
```
(Committear también el repo del frontend como backup.)

## 5. Cómo correr / operar

- **Local:** `pip install -r requirements.txt` + `pip install pip-system-certs` (obligatorio: proxy TLS).
  `.env` con `DATABASE_URL` del **pooler** de Supabase (`...pooler.supabase.com:6543`, NO la directa IPv6).
- **Ingesta:** `python -m atlas.run_ingest discovery` · `... pricing` · `python -m atlas.fx` · `python -m atlas.deals`.
- **API local:** `python -m uvicorn api.main:app --port 8000`.
- **Frontend local:** `npm run dev` (Vite, apunta a `http://127.0.0.1:8000`).

## 6. Restricciones y gotchas (LEER antes de tocar)

- **Supabase free NANO:** presupuesto de **Disk IO** limitado + **500 MB**. Ya causó una
  caída por cargar 43k juegos repetidamente. **Reglas:** queries livianas (keyset por PK o
  índices; nada de `ORDER BY` sobre toda la tabla; paginación server-side; no cargar todo el
  catálogo de una). El `deals` precalculado existe justo para esto.
- **displaycatalog:** disponibilidad = `Actions` contiene `'Purchase'`. Subscripciones (PASS)
  desde `market=US` devuelven `Markets=[US]` (bug de MS) → hay que precificarlas en todos los
  mercados igual. Consumibles/V-Bucks (ej. `9N09WW6KJJ2N`) NO tienen precio de compra directa
  (Actions `Redeem`). Multi-SKU = variantes/denominaciones (`parse_variants`); saltar
  `IsSubscriptionHidden` para el precio titular.
- **Ético/legal:** NO construir features de evasión regional (tutoriales VPN, "truco de Brasil").
  Comparar precios = OK; enseñar a evadir ToS = NO.
- **Consulta en vivo de 242 regiones** tarda ~20-40s → usar set curado (~48) o dará timeout.
- **Python 3.14 local / 3.12 Railway** (`.python-version` fija 3.12). `psycopg2-binary==2.9.12`
  y `orjson==3.11.9` (tienen wheels para ambos).

## 7. Roadmap (pendiente, priorizado)

**Alto valor:**
1. **Badges reales** en las tarjetas: `+PC`, `GAME PASS`, `Play Anywhere`, `Preorder`.
   Falta sumar esos flags al ingest (de `Properties`: `XboxLiveTier`, `IsXboxPlayAnywhere`,
   `IsPreOrder`, y un check de Game Pass). Hoy `GameCards` solo usa `console_gen`/tipo/add-ons.
2. **Incluir/Excluir países** en la comparación (que "región más barata" respete la selección
   del usuario). xbox-now lo hace con dos tablas +/−. El `deals` habría que recalcularlo por
   subconjunto, o filtrar client-side sobre `/api/live/product`.
3. **Presets de 1 clic**: AAA / Free / Game Pass / Ofertas / Play Anywhere (mapean a
   `product_type`, `is_free`, `discount_pct`, badges).
4. **Discovery completo de suscripciones** (Fortnite Crew, etc.): NO están en sitemaps; se
   descubren por los add-ons/related de cada juego. Hoy hay `config.KNOWN_SUBSCRIPTIONS`.

**Medio:**
5. **Historial de precios** (`price_history`): snapshot por refresco → feed "cambios recientes"
   + gráfico (el `PriceHistoryChart` del Figma ya existe). Ojo: multiplica storage.
6. **Tab Analytics real** (StatsCharts, hoy mock).
7. **Settings** funcionales (el engranaje abre `AdvancedSettings` pero sus controles son mock).
8. **Cron de Railway** para la ingesta: crear 2º servicio (mismo repo) con Start Command
   `python -m atlas.run_ingest pricing && python -m atlas.fx && python -m atlas.deals` + Cron Schedule.
   (El botón "Actualizar catálogo" en la web dispara `/api/analysis/start`, pero es pesado.)

**Bajo / futuro:**
9. **Metascore/ratings IGDB** (fuente nueva).
10. **SEO/SSR**: el frontend es una SPA (Google no la indexa). Para tráfico orgánico (como
    xbox-now) las fichas deberían renderizarse server-side con meta/canonical/hreflang.
11. **Escala:** si supera el free-tier, Supabase Pro (8 GB) o Postgres en Railway.

## 8. Estado actual (qué YA anda)

- ✅ Catálogo estilo xbox-now: tarjetas (2 regiones + ahorro% + deal-until + Xbox Store),
  **ordenable por mejor oferta / más barato / nombre**, filtro "solo ofertas ≥30%",
  **selector de moneda**, paginación numerada, búsqueda server-side.
- ✅ Precios por país: consulta EN VIVO las regiones (set curado ~48) sin colgarse.
- ✅ Producto: datos reales (título, precio, dev, imagen).
- ✅ Variantes: denominaciones/duraciones por región (gift cards, subs, monedas).
- ✅ 47 mercados con precios en la DB; `deals` con 37.687 juegos.

## 9. Para el chat nuevo

Empezá leyendo este archivo + [RUNBOOK.md](RUNBOOK.md) (errores típicos y comandos).
Antes de cualquier cambio pesado, chequeá que Supabase no esté "Unhealthy" (IO). Trabajá
sobre la rama `main`. Después de tocar el frontend, seguí el flujo de build/deploy (sección 4).

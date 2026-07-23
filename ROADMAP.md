# Xbox Price Atlas — Handoff & Roadmap

Documento para continuar el proyecto en un chat nuevo. Leé esto primero.

---

## 0. Visión de negocio (LEER ANTES QUE NADA)

Esto NO es un comparador de precios. El comparador es la **puerta de entrada** de
un ecosistema de venta de productos digitales de Xbox.

- **El primer peso sale de las ventas** (juegos, cuentas, suscripciones, V-Bucks).
  El comparador existe para bajar el costo de adquisición de clientes: tráfico
  orgánico por SEO en vez de publicidad paga.
- **Monetización múltiple, no una sola:** ventas propias · AdSense/banners ·
  afiliados cuando no se vende directo · automatizaciones (Gameflip, Discord,
  Instagram, Ko-fi).
- **El activo es el DATO, no la página.** Cada cambio de precio detectado puede
  disparar: una publicación en Gameflip, una alerta a un usuario, un mensaje en
  Discord, un posteo en redes, una oportunidad de compra para el dueño.
- **El sistema también es herramienta interna del vendedor:** detectar
  oportunidades entre 243 mercados, automatizar publicaciones, administrar
  catálogo.

### Qué implica esto para la arquitectura (importante)

1. **`price_history` no es una feature de usuario: es el bus de eventos del
   negocio.** Alertas, Gameflip, Discord y redes son todos *suscriptores* del
   evento "cambió el precio". Por eso pasa de prioridad Media a **P0**.
2. **SEO no es "bajo/futuro": es el canal de adquisición.** Sin fichas
   indexables no hay tráfico orgánico, y sin tráfico orgánico el modelo entero
   (bajar el costo de adquisición) no existe.
3. **Impuestos argentinos** (21% IVA + PAÍS + percepciones) sobre el precio de
   MS: xbox-now nunca los va a calcular. Es ventaja competitiva local y además
   el dueño los necesita para calcular su propio margen.
4. **Guardar el crudo siempre.** El dato es el activo; re-scrapear es caro y a
   veces imposible (Microsoft no da histórico).

### Tensión a resolver

La plataforma tiene dos caras: **pública** (comparador, SEO, publicidad) e
**interna** (panel, integraciones de venta, automatizaciones). Ya están
separadas por el token de admin (§6d). Toda feature nueva debe declarar de qué
lado cae antes de escribirse.

---

## 1. Qué es

Comparador mundial de precios de la Microsoft Store (Xbox) con **datos oficiales
de APIs de Microsoft**, más un panel interno de administración y venta.

## 2. Dónde vive todo

- **Repo único (deploy):** https://github.com/ferhaseho-sys/XBOX-CATALOG — dueño `ferhaseho-sys`.
  Carpeta local: `C:\Users\User\Desktop\Python\Python\xbox-price-atlas`. Contiene TODO:
  backend Python (`atlas/`), API (`api/`), fuente del frontend (`frontend-src/`) y su
  build (`frontend/`, servido por FastAPI). **Monorepo** desde jul-2026 (ver §4).
- **App en vivo:** https://web-production-2b5be.up.railway.app (Railway).
- **Base de datos:** Supabase (proyecto `qvwtvjbxzdmfrmmdueoo`), **plan free NANO**.
- **Backup histórico del frontend:** `...\XboxNow Professional Scraper Web Application`
  (ex-Figma, git local sin remoto). Ya NO se desarrolla ahí.

## 3. Arquitectura

```
sitemaps xbox.com     ─▶ discovery ─▶ products        (universo, ~43k)
displaycatalog API    ─▶ pricing   ─▶ prices          (juego × mercado)
emerald (BFF xbox.com)─▶ browse    ─▶ market_catalog  (Game Pass, rank, xCloud)
open.er-api.com       ─▶ fx        ─▶ price_usd
prices                ─▶ deals     (región más barata + ahorro%)  ← ordenar rápido
FastAPI (api/) ─▶ API pública + /api/admin/* (token) + build del frontend
```

**Tres fuentes PARCIALES cuya unión es el catálogo.** Ninguna lo tiene todo:
- sitemaps: universo amplio (incluye DLC/consumibles) pero sin precio localizado.
- displaycatalog: precio y disponibilidad en 243 mercados.
- Emerald Browse: solo `productFamily=Games`, pero aporta Game Pass, ranking,
  xCloud y handheld, que displaycatalog NO da.

**Backend** (`atlas/`): `discovery.py` (sitemaps→IDs) · `pricing.py` +
`run_ingest.py` (precios, cola plana) · `browse.py` (Emerald) · `fx.py` ·
`deals.py` · `refresh.py` (cron) · `parse.py` · `http_client.py`
(`CatalogClient` + `EmeraldClient`) · `markets.py` · `config.py` · `db.py` ·
`dump.py` / `backfill.py` (análisis offline).

**API** (`api/`): `main.py` (público + sirve `frontend/`) · `admin.py` (panel,
TODO detrás de `require_admin`) · `queries.py`.

**Frontend** (`frontend-src/src/app/`): `App.tsx` + `components/` +
`lib/admin.ts` (gating por token). `AdminPanel.tsx` es el panel interno.

**Herramientas:** `q.py` (consola SQL; NO hay psql en Windows) ·
`analyze.py` / `analyze_browse.py` (análisis sobre los NDJSON crudos).

## 4. Flujo de build/deploy (IMPORTANTE) — MONOREPO

```
cd frontend-src && npm run build      # -> escribe en ../frontend/ (lo que Railway sirve)
cd .. && git add -A && git commit -m "..." && git push   # Railway redespliega
```
- Se commitea **el build** (`frontend/`); `node_modules/` está gitignored.
- `.env.production` hornea `VITE_ATLAS_API` en el bundle. **Ojo al probar local:**
  un build de producción apunta a Railway, no a tu localhost. Para probar contra
  la API local usá `npm run dev` (Vite), que cae al fallback `127.0.0.1:8000`.

**Railway usa DOS servicios con config separada:**

| Servicio | Config | Comando |
|---|---|---|
| web | `railway.json` (default) | `uvicorn api.main:app` |
| cron | `railway.cron.json` | `python -m atlas.refresh` |

⚠️ La config **en código le gana a la del dashboard** ("Configuration defined in
code will always override values from the dashboard"). Un único `railway.json`
con `startCommand=uvicorn` hacía que el servicio cron levantara el servidor web
en vez de la ingesta: corría 6 h, Railway lo mataba, y `pricing` no corrió por
9 días sin que nadie se enterara. **El servicio cron debe apuntar a
`railway.cron.json` en Settings → Config-as-code.**

## 5. Cómo correr / operar

- **Local:** `pip install -r requirements.txt` + `pip install pip-system-certs`
  (obligatorio: proxy TLS). `.env` con `DATABASE_URL` del **pooler** de Supabase
  (`...pooler.supabase.com:6543`, NO la directa IPv6) y `ADMIN_TOKEN`.
- **Ingesta:**
  ```
  python -m atlas.run_ingest discovery         # sitemaps -> products
  python -m atlas.run_ingest pricing           # precios
  python -m atlas.run_ingest browse es-AR      # Emerald (resumible)
  python -m atlas.browse es-AR --hydrate       # rescata lo que browse no lista
  python -m atlas.browse es-AR --reparse       # re-parsea el crudo, SIN red
  python -m atlas.refresh                      # lo que corre el cron
  ```
- **API local:** `python -m uvicorn api.main:app --port 8000`
- **Frontend local:** `cd frontend-src && npm run dev`
- **SQL:** `python q.py "select ..."`
- **Panel admin:** en el navegador, `localStorage.setItem('atlas_admin_token','<token>')`.
  Debe coincidir con `ADMIN_TOKEN` de la API.

## 6. Restricciones y gotchas (LEER antes de tocar)

- **Supabase free NANO:** IO limitado + 500 MB. Ya causó una caída. **Reglas:**
  queries livianas; nada de `ORDER BY` ni `count(*)` sobre tablas grandes;
  paginación server-side. Para conteos usar `pg_class.reltuples`. Para
  `count(distinct col)` sobre tablas grandes usar **skip-scan recursivo**
  (`count(distinct market) from prices` colgaba un endpoint >20 s).
- **NUL (0x00):** algunos títulos de MS traen 0x00 y Postgres no lo acepta en
  `text` ("A string literal cannot contain NUL characters"). Un solo producto
  envenenado cortaba la fase entera. Se limpia en `db._clean()`.
- **Memoria en Railway:** 24 workers × lotes de 400 con `fieldsTemplate=details`
  = ~537 MB en vuelo → OOM y reinicio del contenedor a mitad del trabajo.
- **Los trabajos pesados NO deberían correr en el servicio web:** si crashean se
  llevan el sitio puesto. Ese es el rol del cron.
- **displaycatalog:** disponibilidad = `Actions` contiene `'Purchase'`.
  Suscripciones (PASS) desde `market=US` devuelven `Markets=[US]` (bug de MS).
  Consumibles/V-Bucks no tienen compra directa (Action `Redeem`).
- **`fieldsTemplate` es la palanca de velocidad** (medido, 10 productos reales):
  `details` = 56,1 KB/producto · `Browse` = 12,6 KB (**4,45× menos**).
  `Browse` trae igual `DisplaySkuAvailabilities`, `Actions` y
  `ListPrice`/`MSRP`/`CurrencyCode`. No trae `Properties` (metadata lo necesita)
  ni `ProductType` — pero sí `ProductKind`, y se verificó que **coinciden en los
  43.081 productos**. `config.PRICING_FIELDS` controla esto.
- **Ético/legal:** NO construir features de evasión regional (tutoriales VPN,
  "truco de Brasil"). Comparar precios = OK; enseñar a evadir ToS = NO.
- **Python 3.14 local / 3.12 Railway** (`.python-version`).

## 6b. Categorización — hallazgos (análisis de los 43k, jul-2026)

`atlas/dump.py` baja los 43k JSON crudos a `dump_us.ndjson` (~1.4 GB, gitignored).

Distribución (US): **Durable 21.830 (51%) · Game 18.921 (44%) · Consumable 2.313
· PASS 16.** Más de la MITAD del catálogo son DLC/add-ons.

**✅ HECHO:** `products.kind` (Juego/DLC/Moneda/Suscripción/Gift card) + `is_demo`,
backfill offline con `atlas/backfill.py`, y `is_free` corregido (solo F2P reales:
722, no 2.449). Badges Play Anywhere / PC desde `AllowedPlatforms`.

**Relación juego ↔ DLC:** `MarketProperties[0].RelatedProducts` está poblado en el
dump (1.046 de los primeros 4.000). La tabla `product_relations` ya existe **vacía**;
falta poblarla. Es la pieza que falta para trabajar el 51% del catálogo.

## 6c. Emerald / xbox.com BFF — hallazgos (jul-2026)

`https://emerald.xboxservices.com/xboxcomfd` es el **Backend-For-Frontend** de
xbox.com. Sin auth ni cookies: solo exige el header **`MS-CV`** (correlation
vector; no valida el contenido). Funciona server-side desde Python con
`Origin`/`Referer` de xbox.com.

| Endpoint | Uso |
|---|---|
| `GET /browse?Locale=es-AR&PageNumber=N` | catálogo paginado + summaries hidratados |
| `POST /products?Locale=` body `{"productIds":[…]}` | hidrata por ID, **máx 25** |
| `GET /filters?PageKey=Browse` | vocabulario de facetas |
| `/search`, `/home` | existen pero piden `api-version` que no se encontró |

- **`Locale` es lo que define el mercado**, no `Market` (que se ignora).
- `ResultsPerPage` está **capado en 50**; `orderBy` y `filters` se ignoran o dan
  500 en la API (los filtros SÍ funcionan por la página SSR de xbox.com).
- **`totalItems` miente:** declara 16.948 en AR y sirve 15.399. 101 de 342
  páginas vienen cortas, **de forma determinística** (la página 134 devuelve 48
  siempre). Son entradas muertas del índice. **La web de Xbox tampoco puede
  mostrarlas.** No es un bug del scraper.
- El hueco se cierra con `--hydrate` (POST /products): en AR bajó de 2.852 a **4**.
- **`passMetadataByPassProductId` es el HISTORIAL de membresía, no el estado
  actual.** Sin filtrar, 801 de 811 fechas de salida eran pasadas (la más vieja
  de 2021). Solo valen fechas futuras, no centinela (`9998-12-30`), y de passes
  en los que el juego HOY está.
- **"Ofertas con Game Pass" NO es calculable:** se verificó que `hasXPriceOffer`
  no coincide con la página oficial. Es una **lista curada** que hay que levantar
  de `xbox.com/es-AR/xbox-game-pass/deals`.

Cobertura AR lograda: **18.251 productos** (15.403 browse + 2.848 rescatados),
1.058 en Game Pass, 15 con fecha de entrada, 9 con fecha de salida.

## 6d. Seguridad

`/api/analysis/*` y todo `/api/admin/*` exigen el header **`X-Admin-Token`**
(comparado con `secrets.compare_digest`). Es **fail-closed**: sin `ADMIN_TOKEN`
configurado responden 503, no quedan abiertos. Antes `/api/analysis/start`
estaba **público**: cualquiera podía disparar una ingesta completa contra la DB.

El gating del frontend (`lib/admin.ts`, `NavItem.admin`) es **cosmético a
propósito** — cualquiera puede escribirse una clave en su localStorage. Lo que
protege de verdad es el 401 de la API.

## 7. Roadmap (repriorizado según §0)

### P0 — el motor del negocio
1. **`price_history`** — es el bus de eventos, no una feature de usuario.
   Diseño ya decidido:
   - Delta detectado **dentro de `upsert_prices`** con
     `ON CONFLICT … DO UPDATE … WHERE price IS DISTINCT FROM … RETURNING`:
     sin lecturas extra y con menos write IO que hoy.
   - Tabla **particionada por rango de fecha desde el día uno** (convertirla
     después exige reescribirla entera).
   - `min_ever` / `min_ever_on` / `is_at_min` como **columnas de `prices`**, no
     tabla aparte (`prices` ya es 1 fila por producto×mercado).
   - Alcance inicial `kind='Juego'` × `CORE_MARKETS` (~80 MB/año); se amplía por
     config, nunca por esquema.
   - `checked_at` NO va por fila: "cuándo se barrió X" es dato de la corrida y
     vive en `ingest_runs` (O(mercados), no O(productos×mercados)).
2. **SEO / fichas indexables** — es el canal de adquisición.
   - `products.slug` + `/juego/{slug}` renderizado server-side (Jinja), NO la SPA.
   - ⚠️ El catch-all `@app.get("/{full_path:path}")` de `main.py` se come todo:
     las rutas nuevas deben registrarse ANTES.
   - **Una URL canónica por producto** con la tabla regional adentro. NO una URL
     por mercado (serían 2M de páginas casi idénticas = contenido duplicado).
   - SSR on-demand + cache, no pre-generar 43k archivos.
3. **Que el cron corra de verdad** (§4) y medir cuánto tarda `refresh`.

### P1 — convertir dato en venta
4. **Impuestos argentinos** sobre el precio de MS (ventaja local + margen propio).
5. **Alertas / wishlist** — es la razón para registrarse y para volver.
6. **Automatizaciones** que escuchen `price_history`: Gameflip, Discord, redes.
7. **Categorías editoriales** (estilo xstoregames). 8 de 9 son queries sobre
   datos que YA existen: "Salen del horno" = `release_date > now()-30d`;
   "Ahorrate unos pesos" = `discount_pct >= 50`; "Los más jugados" ≈
   `rating_count desc`; "Mirá lo que se viene" = `release_date > now()`.
   **"Last Added" = `products.first_seen`** (ya existe, se llena solo).

### P2 — producto
8. **UI:** selector de moneda + idioma arriba · rehacer incluir/excluir países ·
   recuperar vista tabla ↔ tarjetas · separar Advanced Settings usuario/admin.
9. **Poblar `product_relations`** desde el dump (juego ↔ DLC/bundle).
10. **Panel:** salud de datos (divergencias browse vs displaycatalog, productos
    sin precio), log de corridas con errores, config editable.
11. Metascore/IGDB · Analytics real · Register/Sign In (después de que exista un
    motivo para registrarse: ver #5).

## 8. Estado actual (qué YA anda)

- ✅ Catálogo público con 2 regiones + ahorro%, ordenable, filtros, presets,
  paginación, búsqueda server-side, selector de moneda.
- ✅ 47 mercados con precios; `deals` con 37.687 juegos.
- ✅ **Emerald Browse**: AR 18.251 productos con Game Pass (entrada y salida),
  xCloud, handheld y ranking. US barrido (16.569).
- ✅ **Panel de administración** (`/api/admin/*` + `AdminPanel.tsx`): estado del
  sistema con alertas calculadas, antigüedad y duración por fase, y ejecución de
  las 7 ingestas desde la web.
- ✅ Ingesta protegida con token; panel e integraciones ocultos al público.
- ✅ Scrollbars estilizadas + `scrollbar-gutter: stable`.
- ⚠️ **`pricing` no corre desde el 14-jul** (el cron nunca ejecutó: ver §4).
  Los precios están congelados hasta que se corra.

## 9. Para el chat nuevo

Leé **§0 (visión)** y **§6 (gotchas)** antes de tocar nada. Después
[RUNBOOK.md](RUNBOOK.md) para errores típicos.

Chequeá que Supabase no esté "Unhealthy" (IO). Trabajá sobre `main`. Después de
tocar el frontend, seguí §4.

**Estado del trabajo:** lo último cerrado fue la Fase 1 (Emerald) + panel admin +
seguridad + arreglo del cron. **Lo próximo es `price_history` (P0 #1)**, que
está diseñado en detalle arriba y no depende de nada pendiente.

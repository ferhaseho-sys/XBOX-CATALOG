# RUNBOOK — Xbox Price Atlas (guía de operación)

Guía para seguir operando el proyecto sin ayuda. Todo lo que necesitás para
cargar datos, desplegar y resolver los errores típicos.

## 0. Dónde está cada cosa

- **Repo GitHub:** https://github.com/ferhaseho-sys/XBOX-CATALOG
- **App (Railway):** https://web-production-2b5be.up.railway.app
- **Base de datos:** Supabase (proyecto `qvwtvjbxzdmfrmmdueoo`)
- **Código local:** `C:\Users\User\Desktop\Python\Python\xbox-price-atlas`

Arquitectura: sitemaps de Xbox → `products` (catálogo) · API displaycatalog →
`prices` (precio por juego×mercado) · `fx_rates` → `price_usd`. La API FastAPI
(`api/main.py`) sirve la web y lee de Supabase.

---

## 1. Requisitos del entorno local (una sola vez)

```cmd
cd "C:\Users\User\Desktop\Python\Python\xbox-price-atlas"
python -m pip install -r requirements.txt
python -m pip install pip-system-certs
```

- `pip-system-certs` es **obligatorio en esta PC**: hay un antivirus/proxy que
  intercepta TLS y sin esto Python da error de certificado SSL.
- El archivo `.env` debe tener el `DATABASE_URL` del **pooler** de Supabase
  (host `aws-1-...pooler.supabase.com`, puerto **6543**), NO la conexión directa
  (`db.*.supabase.co:5432`, que es IPv6 y no resuelve).

---

## 2. Cargar datos (ingesta)

Correr **desde el cmd, en la carpeta del proyecto**. Todo es idempotente y
resumible (podés cortar con Ctrl+C y volver a lanzar; retoma donde quedó).

```cmd
REM 1) Catálogo: baja sitemaps y llena `products` (~42.500 juegos). ~30-40 min.
python -u -m atlas.run_ingest discovery

REM 2) Precios: 48 mercados (uno por moneda). Llena `prices`.
python -m atlas.run_ingest pricing

REM    (o mercados puntuales para probar rápido)
python -m atlas.run_ingest pricing US GB AR TR NG

REM 3) Tasas de cambio: llena `fx_rates` y calcula `price_usd`.
python -m atlas.fx

REM Refresco diario (precios de mercados core + fx). Lo usa el cron de Railway.
python -m atlas.run_ingest metadata   REM refresca títulos/imágenes/rating
```

Qué llena cada fase en la web:
- `discovery` → contador **JUEGOS** y la pestaña **Buscar**.
- `pricing` + `fx` → **Más baratos / Ofertas / Spread** y la ficha de cada juego.

---

## 3. Ver el estado de la base

```cmd
python -c "from atlas import db; c=db.connect(); cur=c.cursor(); cur.execute('select count(*) from products'); print('juegos:', cur.fetchone()[0]); cur.execute('select count(*) from prices'); print('precios:', cur.fetchone()[0]); c.close()"
```

O en Supabase → Table Editor → tablas `products` / `prices`.

---

## 4. Subir cambios (git) y desplegar

Railway redespliega **solo** cada vez que hacés push a `main`.

```cmd
cd "C:\Users\User\Desktop\Python\Python\xbox-price-atlas"
git add -A
git commit -m "descripción del cambio"
git push
```

- Si `git push` pide credenciales y no las toma: usá el token en la URL una vez
  (crear token en https://github.com/settings/tokens, scope `repo`):
  ```cmd
  git push https://ferhaseho-sys:TU_TOKEN@github.com/ferhaseho-sys/XBOX-CATALOG.git main
  ```
- **Nunca** dejar los `< >` alrededor del token (en cmd son redirección de archivo).

---

## 5. Variables de entorno en Railway

Servicio **web** (y el de cron, si lo creás): Railway → servicio → Variables.
```
DATABASE_URL = <pooler de Supabase :6543>
REQ_RATE=6
BATCH_SIZE=150
MARKET_WORKERS=4
```
El servicio web arranca con `railway.json` (uvicorn + healthcheck `/health`).
Para el cron de refresco: nuevo servicio, mismo repo, Start Command
`python -m atlas.refresh`, Cron Schedule `0 6 * * *`.

---

## 6. Errores típicos y su solución (ya los pasamos)

| Síntoma | Causa | Solución |
|---|---|---|
| `libpq.so.5: cannot open shared object` (Railway) | Python 3.13 sin wheel psycopg2 | Ya fijado Python 3.12 en `.python-version` |
| `pg_config executable not found` (local pip) | psycopg2 compilando desde fuente | `requirements.txt` usa `psycopg2-binary==2.9.12` (tiene wheel py3.14) |
| `CERTIFICATE_VERIFY_FAILED` / `local issuer` | proxy/AV intercepta TLS | `pip install pip-system-certs` |
| `could not translate host name db.*.supabase.co` | usaste la conexión directa (IPv6) | usar el **pooler** `:6543` en `DATABASE_URL` |
| `git push`: `no upstream branch` | primer push sin tracking | `git push --set-upstream origin main` |
| Página muestra 0 / "sin conexión a DB" | falta `DATABASE_URL` en Railway o DB vacía | revisar Variables / correr ingesta |

---

## 7. Qué queda pendiente (roadmap)

- **Expansión a 243 en la ficha:** mapa `país→moneda` para mostrar todos los
  países (los EUR/USD apuntando al precio guardado) con 3 columnas: Local /
  Local→USD / Ref USD-EUR, ordenado por USD.
- **Historial de precios:** tabla `price_history` (snapshot por refresco) para el
  feed "cambios recientes" y el gráfico histórico. Ojo: multiplica almacenamiento.
- **Filtros:** presets de 1 clic (AAA/Free/Game Pass/ofertas), incluir/excluir
  países, selector de moneda de referencia.
- **Vista tabla** además de tarjetas.
- Escalar a 243 mercados completos = Supabase Pro (8 GB) o quedarse en los 48.

---

## 8. Principios de diseño (no olvidar)

- Datos oficiales de la API de Microsoft, **sin scraping** de terceros.
- Calidad por defecto: hundir shovelware (sin rating + tipo Consumable + desc genérica).
- Dato ausente = ausencia visual limpia, **nunca** un placeholder clickable ("N/A").
- **No** construir funciones de evasión regional (VPN/trucos): viola los ToS de
  Xbox y arriesga baneos. Atlas es transparencia de precios, no elusión.

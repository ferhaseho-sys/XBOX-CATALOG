# Migrar de Supabase a Railway Postgres

Supabase free NANO se satura y cae con la carga real (2 veces en jul-2026, la
última ni deja aplicar una migración). Railway Postgres: **sin límite de IO, en
la misma red privada que la app, sin el pooler** que daba conexiones de 105 s.

## Estrategia: arranque limpio (NO hay que rescatar datos de Supabase)

Todo se regenera, y los precios estaban desactualizados igual (congelados desde
el 14-jul). Así no dependemos de que Supabase reviva para poder dumpear.

Lo único irrecuperable serían los NDJSON crudos de Browse — y **ya están en tu
disco local** (`browse_*.ndjson`), así que `market_catalog` se reconstruye sin
red.

## Pasos

### 1. Crear la base en Railway
Railway → tu proyecto (el que tiene `web` y `cron`) → **New → Database →
Add PostgreSQL**. Esperá a que quede **Running**. El servicio se llama `Postgres`
por defecto (anotá el nombre exacto, se usa en el paso 2).

### 2. Apuntar las apps a la base nueva
Railway Postgres expone dos URLs:
- `DATABASE_URL` — **privada** (`…railway.internal`), rápida, misma red.
- `DATABASE_PUBLIC_URL` — pública, para conectarte desde tu PC.

En el servicio **web** → Variables → editá `DATABASE_URL` y poné como valor la
**variable de referencia**:
```
${{ Postgres.DATABASE_URL }}
```
(reemplazá `Postgres` por el nombre real del servicio de base). Hacé lo mismo en
el servicio **cron**. Esto los deja hablando por la red privada, sin pooler.

### 3. Aplicar el esquema (desde tu PC, una vez)
En el dashboard de Railway → servicio Postgres → Variables → copiá el valor de
`DATABASE_PUBLIC_URL`. Pegalo en tu `.env` local como `DATABASE_URL`. Después:
```bash
python apply_schema.py
```
Debe decir `✅ schema aplicado — 9/9 tablas principales presentes`. Sobre una
base vacía es instantáneo (nada que bloquear).

### 4. Poblar, en orden, desde el Panel de administración
Con el token de admin puesto (ver RUNBOOK/ROADMAP), apretá en este orden:
1. **Descubrimiento por sitemaps** → llena `products`
2. **Precios por mercado** → llena `prices` (era la actualización que hacía falta)
3. **Emerald Browse** → llena `market_catalog`
4. **Tasas de cambio**
5. **Recalcular resumen de ofertas** → llena `deals`

Corren en Railway (red rápida), no en tu PC. `pricing` ya es 4,45× más liviano y
ahora sobre una base sin límite de IO no debería saturarse.

### 5. Verificar el delta
Con `DATABASE_URL` = la URL pública en tu `.env`:
```bash
python verify_delta.py
```
Tiene que dar `cambios=0` al re-guardar sin cambios.

### 6. Confirmar y limpiar
Cuando el sitio (`web-production-…railway.app`) muestre datos, listo. Recién ahí
podés dar de baja el proyecto de Supabase (o dejarlo, es gratis).

## Notas
- **Local usa la URL PÚBLICA; las apps en Railway usan la privada por
  referencia.** No mezclar.
- **No borres Supabase hasta confirmar que Railway anda.**
- El `.env` local cambia solo para vos; en Railway las variables ya quedaron
  bien en el paso 2.
- Presupuesto: Railway cobra por uso. Con Postgres + web + cron, contá
  **$10-15/mes**. Ya tenías el crédito consumiéndose igual con el bug del cron.

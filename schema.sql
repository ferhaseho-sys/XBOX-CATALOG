-- Xbox Price Atlas — esquema Postgres (Supabase)
-- Ejecutar en el SQL Editor de Supabase o via psql con DATABASE_URL.

-- ============ Catálogo (metadata estable, 1 fila por ProductID) ============
create table if not exists products (
    product_id           text primary key,
    title                text,
    short_title          text,
    short_desc           text,
    description          text,
    product_type         text,          -- Game / Durable / Consumable / CSV / PASS
    product_kind         text,
    product_family       text,
    developer            text,
    publisher            text,
    category             text,           -- Properties.Category cruda de Microsoft
    kind                 text,           -- categoría legible: Juego/DLC/Moneda/Suscripción/Gift card
    is_demo              boolean,        -- true si es demo/trial (no un juego gratis real)
    on_pc                boolean,        -- AllowedPlatforms ∋ Windows.Desktop (corre en PC)
    on_xbox              boolean,        -- AllowedPlatforms ∋ Windows.Xbox (corre en consola)
    is_free              boolean,        -- F2P real (Juego con precio $0 en algún mercado). Lo recalcula atlas/deals.py
    categories           text[],
    release_date         date,
    min_user_age         int,
    is_ms_product        boolean,
    has_addons           boolean,
    console_gen          text[],
    gold_required        boolean,
    image_hero           text,
    image_boxart         text,
    image_poster         text,
    trailer              text,
    avg_rating           real,
    rating_count         int,
    ratings              jsonb,          -- {"ESRB":"ESRB:T","PEGI":"PEGI:16",...}
    xbox_title_id        text,
    available_markets    text[],         -- ~243 mercados de distribución
    n_available_markets  int,
    last_modified        timestamptz,
    first_seen           timestamptz default now(),
    updated_at           timestamptz default now()
);
create index if not exists idx_products_type      on products (product_type);
create index if not exists idx_products_coverage  on products (n_available_markets);
create index if not exists idx_products_publisher on products (publisher);

-- ============ Precios (1 fila por ProductID × mercado, solo comprables) ============
create table if not exists prices (
    product_id     text not null references products (product_id) on delete cascade,
    market         text not null,
    currency       text,
    list_price     numeric(12,2),
    msrp           numeric(12,2),
    discount_pct   int,
    on_sale        boolean,
    sale_ends      timestamptz,
    is_free        boolean,
    n_paid_offers  int,
    recurrence     text,            -- "1 Month" para suscripciones (PASS); null si no
    price_usd      numeric(12,2),   -- list_price convertido con fx_rates
    updated_at     timestamptz default now(),
    primary key (product_id, market)
);
-- Estadísticas históricas. Van COMO COLUMNAS de `prices` y no en una tabla
-- aparte: `prices` ya es 1 fila por (product_id, market), así que una tabla
-- `price_stats` sería duplicar ~1M de filas y agregar un join para nada.
-- Las mantiene `db.upsert_prices` en el mismo lote que detecta el cambio.
alter table prices add column if not exists min_ever      numeric(12,2);
alter table prices add column if not exists min_ever_on   date;
alter table prices add column if not exists is_at_min     boolean default false;
create index if not exists idx_prices_market   on prices (market);
create index if not exists idx_prices_at_min   on prices (market) where is_at_min;
create index if not exists idx_prices_usd       on prices (price_usd);
create index if not exists idx_prices_discount  on prices (discount_pct);

-- ============ Variantes / SKUs (denominaciones, duraciones, promos) ============
-- Todas las variantes comprables de un producto por mercado (gift cards, subs,
-- monedas). El precio "titular" vive en `prices`; esto es el menú completo.
-- Nota: sin FK a products (a diferencia de prices/deals) — refleja la tabla viva.
create table if not exists variants (
    product_id    text not null,
    market        text not null,
    sku_id        text not null,
    title         text,
    duration      text,            -- "1 Month", "12 Month" (subs); null si no aplica
    is_hidden     boolean,         -- IsSubscriptionHidden (promos/trials ocultos)
    is_recurring  boolean,         -- suscripción recurrente
    purchasable   boolean,
    currency      text,
    list_price    numeric(12,2),
    price_usd     numeric(12,2),   -- list_price convertido con fx_rates
    updated_at    timestamptz default now(),
    primary key (product_id, market, sku_id)
);
create index if not exists idx_variants_product on variants (product_id);

-- ============ Histórico de precios (solo CAMBIOS, no snapshots) ============
-- Es el bus de eventos del negocio: alertas, publicaciones en Gameflip, avisos
-- en Discord y redes son todos consumidores de "cambió el precio de X en Y".
--
-- Solo se inserta cuando el precio DIFIERE del anterior. Un snapshot diario
-- completo serían ~1M de filas por día (imposible en el free tier); con deltas
-- reales (1-3% de cambio diario) son ~20k.
--
-- PARTICIONADA POR FECHA DESDE EL DÍA UNO: convertir una tabla grande a
-- particionada después obliga a reescribirla entera. Declararla así hoy no
-- cuesta nada y evita esa migración.
-- Sin FK a products: las FK en tablas particionadas de alto volumen encarecen
-- cada escritura (mismo criterio que `variants`).
create table if not exists price_history (
    product_id    text not null,
    market        text not null,
    seen_on       date not null,
    list_price    numeric(12,2),
    msrp          numeric(12,2),
    discount_pct  int,
    currency      text,
    primary key (product_id, market, seen_on)   -- la PK DEBE incluir la clave de partición
) partition by range (seen_on);

-- Particiones: las crea `atlas/history.py` a demanda (uná por mes). La default
-- atrapa cualquier fecha sin partición para que un insert nunca falle.
create table if not exists price_history_default partition of price_history default;

-- "qué cambió hoy en AR" — el feed de novedades y el disparador de las alertas
create index if not exists idx_phist_market_dia on price_history (market, seen_on desc);

-- ============ Disponibilidad por mercado (fuente: Emerald Browse) ============
-- 1 fila por producto × mercado. NO reemplaza a `prices`: aporta las dimensiones
-- que displaycatalog no da (Game Pass, popularidad, xCloud, handheld).
-- `source` existe para que la tabla no quede atada a Browse: mañana otra fuente
-- puede aportar disponibilidad de DLC/consumibles con el mismo esquema.
-- Sin FK a products: Browse puede descubrir IDs que discovery todavía no cargó
-- (justamente una de las cosas que queremos medir).
create table if not exists market_catalog (
    product_id       text not null,
    market           text not null,
    source           text not null default 'browse',
    locale           text,
    rank             int,             -- posición en el orden devuelto por la fuente
    available_on     text[],          -- PC / XboxOne / XboxSeriesX / XCloud / Handheld
    in_gamepass      boolean,
    pass_ids         text[],          -- productIds de los passes que lo incluyen
    -- OJO: passMetadataByPassProductId es el HISTORIAL de membresía, no el estado
    -- actual. Estas dos columnas guardan solo fechas FUTURAS y no centinela:
    pass_exit_date   timestamptz,     -- sale del pass (solo si HOY está en él)
    pass_entry_date  timestamptz,     -- llega al pass (day-one anunciados)
    on_xcloud        boolean,
    on_handheld      boolean,
    handheld_tier    int,             -- hhVerified.deviceEvaluation
    badges           int[],
    avg_rating       real,
    rating_count     int,
    -- Precio según la fuente. NO es el precio del read path (ese vive en `prices`):
    -- se guarda para CONTRASTAR contra displaycatalog y detectar divergencias.
    list_price       numeric(12,2),
    msrp             numeric(12,2),
    discount_pct     int,
    currency         text,
    seen_at          timestamptz default now(),
    primary key (product_id, market, source)
);
create index if not exists idx_mktcat_market   on market_catalog (market);
create index if not exists idx_mktcat_gamepass on market_catalog (market, in_gamepass)
    where in_gamepass;
create index if not exists idx_mktcat_rank     on market_catalog (market, rank);
create index if not exists idx_mktcat_gp_coming on market_catalog (market, pass_entry_date)
    where pass_entry_date is not null;

-- ============ Relaciones entre productos (juego <-> DLC / bundle / edición) ============
-- La pieza que falta para el catálogo completo: hoy el 51% de los productos
-- (Durable/DLC) no tiene vínculo con su juego padre. Fuente principal:
-- MarketProperties[0].RelatedProducts de displaycatalog (ya presente en el dump).
-- Sin FK: el hijo puede aparecer antes que el padre según el orden de ingesta.
create table if not exists product_relations (
    parent_id   text not null,
    child_id    text not null,
    relation    text not null,        -- addon / bundle_item / edition / related
    source      text,                 -- de dónde salió la relación
    updated_at  timestamptz default now(),
    primary key (parent_id, child_id, relation)
);
create index if not exists idx_prel_child on product_relations (child_id);

-- ============ Tasas de cambio (para normalizar a USD) ============
create table if not exists fx_rates (
    currency    text primary key,
    usd_rate    numeric(18,8) not null,  -- 1 unidad de `currency` = usd_rate USD
    source      text,
    updated_at  timestamptz default now()
);

-- ============ Control de ingesta (resumible) ============
create table if not exists ingest_runs (
    id           bigserial primary key,
    phase        text not null,          -- discovery / metadata / pricing
    market       text,
    status       text default 'running', -- running / done / error
    n_products   int default 0,
    started_at   timestamptz default now(),
    finished_at  timestamptz,
    detail       text
);
create index if not exists idx_ingest_phase_market on ingest_runs (phase, market);

-- ============ Resumen de ofertas precalculado (1 fila por producto) ============
-- Región más barata + ahorro% vs US, para ordenar/filtrar el catálogo con un
-- index-scan liviano (clave en free-tier). La mantiene `atlas/deals.py` (que
-- corre este mismo DDL con `create if not exists` y la rellena tras cada refresh);
-- se documenta acá para tener el esquema completo en un solo lugar.
create table if not exists deals (
    product_id         text primary key references products(product_id) on delete cascade,
    cheapest_market    text,
    cheapest_currency  text,
    cheapest_list      numeric(12,2),
    cheapest_usd       numeric(12,2),
    us_usd             numeric(12,2),
    savings_pct        int,
    on_sale            boolean,
    sale_ends          timestamptz,
    n_markets          int,
    updated_at         timestamptz default now()
);
create index if not exists idx_deals_savings  on deals (savings_pct desc);
create index if not exists idx_deals_cheapest on deals (cheapest_usd);

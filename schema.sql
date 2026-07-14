-- Xbox Price Atlas — esquema Postgres (Supabase)
-- Ejecutar en el SQL Editor de Supabase o via psql con DATABASE_URL.

-- ============ Catálogo (metadata estable, 1 fila por ProductID) ============
create table if not exists products (
    product_id           text primary key,
    title                text,
    short_title          text,
    short_desc           text,
    description          text,
    product_type         text,          -- Game / Durable / Consumable / CSV
    product_kind         text,
    product_family       text,
    developer            text,
    publisher            text,
    category             text,
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
create index if not exists idx_prices_market   on prices (market);
create index if not exists idx_prices_usd       on prices (price_usd);
create index if not exists idx_prices_discount  on prices (discount_pct);

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

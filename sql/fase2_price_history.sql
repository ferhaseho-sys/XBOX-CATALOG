-- Fase 2 — Histórico de precios. Migración para pegar en el SQL Editor de
-- Supabase (Dashboard → SQL Editor), NO por el pooler.
--
-- POR QUÉ EN EL SQL EDITOR Y NO POR SCRIPT:
--   * Las ALTER TABLE piden un lock breve sobre `prices`. Con la base saturada
--     ese lock se encola detrás de queries lentas y da statement timeout (que es
--     justo lo que pasó). El SQL Editor corre contra la base directa, sin el
--     pooler y sin la cola del worker.
--   * Todo es idempotente (`if not exists`): se puede correr las veces que haga
--     falta sin romper nada.
--
-- CORRER SOLO CON LA BASE EN VERDE (Database Healthy).

-- columnas de mínimo histórico sobre `prices` (metadata-only en PG11+: instantáneo)
alter table prices add column if not exists min_ever      numeric(12,2);
alter table prices add column if not exists min_ever_on   date;
alter table prices add column if not exists is_at_min     boolean default false;
create index if not exists idx_prices_at_min on prices (market) where is_at_min;

-- histórico: solo CAMBIOS de precio, particionado por fecha desde el día uno
create table if not exists price_history (
    product_id    text not null,
    market        text not null,
    seen_on       date not null,
    list_price    numeric(12,2),
    msrp          numeric(12,2),
    discount_pct  int,
    currency      text,
    primary key (product_id, market, seen_on)
) partition by range (seen_on);

create table if not exists price_history_default partition of price_history default;
create index if not exists idx_phist_market_dia on price_history (market, seen_on desc);

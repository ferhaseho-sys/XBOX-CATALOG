"""Panel de administración: estado del sistema y ejecución de trabajos.

Todo lo de acá es INTERNO. Va detrás de `require_admin` (header X-Admin-Token);
el público solo ve el catálogo.

Dos responsabilidades:
  1. /status  — qué tan fresca está cada cosa y qué está roto, sin tener que
                entrar a la DB a mano.
  2. /jobs    — disparar las ingestas desde la web en vez de por consola.
"""
from __future__ import annotations

import threading
import time
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/api/admin", tags=["admin"])

# ---------------------------------------------------------------- trabajos ---
# Un solo trabajo a la vez: son todos pesados y comparten la misma DB.
_job = {"running": False, "name": None, "phase": "idle", "detail": "",
        "started_at": None, "finished_at": None, "error": None}
_job_lock = threading.Lock()


def _set(**kw) -> None:
    _job.update(kw)


def _run_pricing(markets: list[str] | None = None) -> None:
    from atlas import config, db, run_ingest
    from atlas.http_client import CatalogClient
    conn = db.connect()
    try:
        run_ingest.phase_pricing(conn, CatalogClient(),
                                 markets or config.PRICING_MARKETS)
    finally:
        conn.close()


def _run_discovery() -> None:
    from atlas import db, run_ingest
    from atlas.http_client import CatalogClient
    conn = db.connect()
    try:
        run_ingest.phase_discovery(conn, CatalogClient())
    finally:
        conn.close()


def _run_browse(locales: list[str] | None = None) -> None:
    from atlas import browse, config, db
    from atlas.http_client import EmeraldClient
    conn = db.connect()
    try:
        client = EmeraldClient()
        for loc in (locales or config.BROWSE_LOCALES):
            browse.browse_locale(conn, client, loc)
    finally:
        conn.close()


def _run_hydrate(locales: list[str] | None = None) -> None:
    from atlas import browse, config, db
    from atlas.http_client import EmeraldClient
    conn = db.connect()
    try:
        client = EmeraldClient()
        for loc in (locales or config.BROWSE_LOCALES):
            browse.hydrate_missing(conn, client, loc)
    finally:
        conn.close()


def _run_fx() -> None:
    from atlas import fx
    fx.main()


def _run_deals() -> None:
    from atlas import deals
    deals.main()


def _run_refresh() -> None:
    """Lo mismo que corre el cron: precios + FX + deals."""
    from atlas import refresh
    refresh.main()


# nombre -> (función, etiqueta, cuánto tarda más o menos)
JOBS: dict[str, tuple[Callable, str, str]] = {
    "refresh":   (_run_refresh,   "Refresco completo (precios + FX + ofertas)", "largo"),
    "pricing":   (_run_pricing,   "Precios por mercado",                        "largo"),
    "discovery": (_run_discovery, "Descubrimiento por sitemaps",                "largo"),
    "browse":    (_run_browse,    "Emerald Browse (Game Pass, ranking)",        "~17 min por locale"),
    "hydrate":   (_run_hydrate,   "Rescatar juegos que Browse no lista",        "~7 min por locale"),
    "fx":        (_run_fx,        "Tasas de cambio",                            "segundos"),
    "deals":     (_run_deals,     "Recalcular resumen de ofertas",              "~1 min"),
}


def _runner(name: str, fn: Callable, args: dict) -> None:
    try:
        fn(**args)
        _set(phase="done", detail="Terminado.")
    except Exception as e:                       # noqa: BLE001 - se reporta al panel
        _set(phase="error", error=str(e)[:400], detail="Falló.")
    finally:
        _set(running=False, finished_at=time.time())


@router.get("/jobs")
def jobs_state():
    """Catálogo de trabajos + estado del que está corriendo."""
    return {
        "available": [{"name": k, "label": v[1], "duration": v[2]} for k, v in JOBS.items()],
        "current": _job,
    }


@router.post("/jobs/{name}")
def jobs_start(name: str, locales: str = "", markets: str = ""):
    if name not in JOBS:
        raise HTTPException(404, f"Trabajo desconocido: {name}")
    with _job_lock:
        if _job["running"]:
            raise HTTPException(409, f"Ya hay un trabajo corriendo: {_job['name']}")
        _set(running=True, name=name, phase="running", detail=JOBS[name][1],
             started_at=time.time(), finished_at=None, error=None)

    args: dict = {}
    if locales and name in ("browse", "hydrate"):
        args["locales"] = [x.strip() for x in locales.split(",") if x.strip()]
    if markets and name == "pricing":
        args["markets"] = [x.strip().upper() for x in markets.split(",") if x.strip()]

    threading.Thread(target=_runner, args=(name, JOBS[name][0], args),
                     daemon=True).start()
    return {"status": "started", "name": name}


# ----------------------------------------------------------------- estado ---
# Antigüedad a partir de la cual una fase se considera atrasada. `pricing` es el
# más sensible: las ofertas rotan a diario y un dato viejo es un dato mentiroso.
STALE_HOURS = {"pricing": 48, "browse": 24 * 10, "discovery": 24 * 14,
               "browse-hydrate": 24 * 10}

# En tablas grandes count(*) obliga a recorrerlas enteras y en el free-tier eso
# se paga en IO. reltuples es la estimación que mantiene el propio Postgres.
COUNTS_SQL = """
select relname, greatest(reltuples::bigint, 0)
from pg_class
where relname in ('products','prices','market_catalog','variants','deals')
  and relkind = 'r'
"""

# Mercados con precio. `count(distinct market) from prices` recorre ~1M de filas
# y colgaba el panel (>20 s) en un endpoint que se consulta seguido: Postgres no
# hace "loose index scan" solo. Esto lo emula: salta de un market al siguiente
# por idx_prices_market, así son ~47 lookups en vez de un scan completo.
MARKETS_SQL = """
with recursive saltos as (
    (select market from prices order by market limit 1)
    union all
    select (select p.market from prices p
            where p.market > s.market order by p.market limit 1)
    from saltos s
    where s.market is not null
)
select count(*) from saltos where market is not null
"""

LAST_RUNS_SQL = """
select distinct on (phase)
       phase, market, status, n_products, started_at, finished_at,
       extract(epoch from (now() - finished_at))/3600 as horas,
       extract(epoch from (finished_at - started_at)) as duracion
from ingest_runs
order by phase, finished_at desc
"""


@router.get("/status")
def status():
    from atlas import db
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(COUNTS_SQL)
            counts = {r[0]: int(r[1]) for r in cur.fetchall()}
            cur.execute(MARKETS_SQL)
            n_markets = cur.fetchone()[0]
            cur.execute(LAST_RUNS_SQL)
            runs = [{
                "phase": r[0], "market": r[1], "status": r[2], "n_products": r[3],
                "finished_at": r[5].isoformat() if r[5] else None,
                "hours_ago": round(float(r[6]), 1) if r[6] is not None else None,
                "duration_s": int(r[7]) if r[7] is not None else None,
            } for r in cur.fetchall()]
    finally:
        conn.close()

    alerts = []
    by_phase = {r["phase"]: r for r in runs}
    for phase, limit in STALE_HOURS.items():
        r = by_phase.get(phase)
        if not r:
            alerts.append({"level": "warn",
                           "msg": f"La fase «{phase}» no corrió nunca."})
        elif r["hours_ago"] is not None and r["hours_ago"] > limit:
            dias = r["hours_ago"] / 24
            alerts.append({"level": "error" if phase == "pricing" else "warn",
                           "msg": f"«{phase}» no corre hace {dias:.1f} días "
                                  f"(límite: {limit / 24:.0f})."})
    if not counts.get("market_catalog"):
        alerts.append({"level": "warn",
                       "msg": "market_catalog vacía: sin datos de Game Pass ni ranking."})
    if all(r["duration_s"] in (0, None) for r in runs):
        alerts.append({"level": "info",
                       "msg": "Aún no hay corridas con duración medida; "
                              "las viejas registran 0."})

    return {"counts": counts, "markets_with_prices": n_markets,
            "runs": runs, "alerts": alerts, "job": _job}

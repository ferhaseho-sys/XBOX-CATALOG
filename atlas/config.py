"""Configuracion via variables de entorno (.env en local, Railway vars en prod)."""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Conexion Postgres de Supabase. En Supabase: Project Settings > Database >
# Connection string (usar el "Connection pooler" / puerto 6543 para workers).
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# --- Rendimiento de ingesta ---
# REQ_RATE es el TECHO global de req/seg (anti-429), no un freno; la concurrencia
# es el motor. WORKERS = conexiones HTTP concurrentes (cola plana de lotes).
# Pensado para correr en RAILWAY (sin el proxy TLS local que topa a ~340 KB/s).
REQ_RATE = float(os.environ.get("REQ_RATE", "20"))
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "400"))       # la API acepta ~500
WORKERS = int(os.environ.get("WORKERS", os.environ.get("MARKET_WORKERS", "24")))
HTTP_TIMEOUT = int(os.environ.get("HTTP_TIMEOUT", "60"))    # lotes de 400 pueden tardar
HTTP_POOL = int(os.environ.get("HTTP_POOL", "32"))          # debe ser >= WORKERS
# Plantilla de campos para PRECIOS. Medido sobre 10 productos reales:
#   details -> 56,1 KB por producto      Browse -> 12,6 KB  (4,45x menos)
# 'Browse' igual trae DisplaySkuAvailabilities, Actions y ListPrice/MSRP/moneda,
# que es todo lo que mira parse_price. La metadata sigue usando 'details' porque
# necesita `Properties` (que Browse no manda).
PRICING_FIELDS = os.environ.get("PRICING_FIELDS", "Browse")
# compat: algunos modulos aun leen MARKET_WORKERS
MARKET_WORKERS = WORKERS

# Sitemaps
SITEMAP_INDEX = "https://www.xbox.com/sitemap.xml"

# Mercados sembradores para discovery (los que TIENEN sitemap y mas aportan al
# universo de IDs). El resto de los 243 se cubre igual en la fase de pricing.
SEED_LOCALES = [
    "en-US", "en-GB", "ja-JP", "en-ZA", "en-IN", "tr-TR", "pt-BR",
    "es-AR", "ru-RU", "de-DE", "ko-KR", "zh-TW", "pl-PL", "es-MX",
]

# Mercados a PRECIFICAR: uno representativo por MONEDA distinta (~50). Guardar
# mas es guardar duplicados (toda la Eurozona = mismo precio EUR; decenas de
# paises chicos = mismo USD). Los ~190 restantes se expanden en la web via
# mapa pais->moneda, sin ocupar espacio en la DB.
# DE = representante EUR ; US = representante USD.
PRICING_MARKETS = [
    "US", "DE", "GB",                                  # USD, EUR, GBP
    "AR", "BR", "MX", "CL", "CO", "PE", "UY",          # LatAm
    "TR", "RU", "UA", "PL", "CZ", "HU", "RO", "BG",    # Europa del este
    "SE", "NO", "DK", "CH", "IS",                      # Europa (moneda propia)
    "IN", "ID", "TH", "VN", "MY", "PH", "SG",          # Asia SE/Sur
    "JP", "KR", "TW", "HK", "CN",                      # Asia este
    "AU", "NZ", "CA",                                  # Oceania/Norteamerica
    "ZA", "NG", "EG", "KE",                            # Africa
    "SA", "AE", "QA", "KW", "IL", "KZ",                # Medio Oriente/Asia central
]

# Token para los endpoints de administracion (disparar ingesta, ver su estado).
# Si queda VACIO, esos endpoints se DESHABILITAN (fail-closed): preferimos que el
# panel no funcione a que quede abierto y cualquiera pueda disparar una ingesta
# completa contra la DB.
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")

# --- Emerald (BFF de xbox.com) ---
# Complementa a displaycatalog: aporta Game Pass, popularidad, xCloud y handheld,
# que displaycatalog NO devuelve. Solo requiere el header MS-CV (sin auth).
# OJO: indexa por LOCALE, no por mercado, asi que solo cubre los mercados que
# tienen storefront en xbox.com (no los 243). El resto sigue via displaycatalog.
EMERALD_BASE = os.environ.get("EMERALD_BASE", "https://emerald.xboxservices.com/xboxcomfd")
# ResultsPerPage esta capado en 50 del lado del server (pedir mas no cambia nada).
BROWSE_MAX_PAGES = int(os.environ.get("BROWSE_MAX_PAGES", "500"))   # corte de seguridad
# Locales a barrer. Se empieza chico para validar; ampliar es agregar aca.
BROWSE_LOCALES = [l.strip() for l in os.environ.get(
    "BROWSE_LOCALES", "es-AR,en-US").split(",") if l.strip()]

# Suscripciones conocidas que NO estan en los sitemaps de juegos (Xbox no las
# sitemapea). Se siembran a mano; la lista se puede ampliar a medida que aparezcan.
# (El discovery completo de subs seria recorrer los add-ons de cada juego.)
KNOWN_SUBSCRIPTIONS = [
    "CFQ7TTC0L23L",   # Fortnite Crew
]

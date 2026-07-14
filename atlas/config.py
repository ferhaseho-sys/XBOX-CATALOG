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

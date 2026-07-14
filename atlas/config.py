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

# Ritmo de peticiones a la API (req/seg) y concurrencia de mercados.
REQ_RATE = float(os.environ.get("REQ_RATE", "6"))
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "150"))
MARKET_WORKERS = int(os.environ.get("MARKET_WORKERS", "4"))

# Sitemaps
SITEMAP_INDEX = "https://www.xbox.com/sitemap.xml"

# Mercados sembradores para discovery (los que TIENEN sitemap y mas aportan al
# universo de IDs). El resto de los 243 se cubre igual en la fase de pricing.
SEED_LOCALES = [
    "en-US", "en-GB", "ja-JP", "en-ZA", "en-IN", "tr-TR", "pt-BR",
    "es-AR", "ru-RU", "de-DE", "ko-KR", "zh-TW", "pl-PL", "es-MX",
]

"""Cliente HTTP resiliente para displaycatalog: reintentos, backoff y rate-limit.

La API es publica y sin auth, pero responde con caidas SSL intermitentes y 429
ocasionales. Este cliente centraliza esa robustez.

Notas de rendimiento:
- Se comparte UNA sola Session entre threads (urllib3 es thread-safe y reutiliza
  conexiones TLS). pool_maxsize debe ser >= concurrencia.
- El parseo usa orjson (C, ~5-10x mas rapido que json); con ~23 GB de JSON el
  parseo es el techo tras resolver el ancho de banda.
- RateLimiter GLOBAL como techo anti-429; no duerme dentro del lock.
"""
from __future__ import annotations
import time
import threading
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from . import config

try:
    import orjson
    def _loads(b: bytes):
        return orjson.loads(b)
except Exception:  # fallback si orjson no esta instalado
    import json
    def _loads(b: bytes):
        return json.loads(b)

BASE = "https://displaycatalog.mp.microsoft.com/v7.0/products"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")


class RateLimiter:
    """Techo global de `rate` req/seg. Calcula el slot bajo lock y duerme FUERA
    del lock, para que N threads puedan esperar sus slots en paralelo."""
    def __init__(self, rate: float):
        self.min_interval = 1.0 / rate if rate > 0 else 0.0
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self):
        if self.min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            slot = self._next if self._next > now else now
            self._next = slot + self.min_interval
        delay = slot - time.monotonic()
        if delay > 0:
            time.sleep(delay)


class CatalogClient:
    def __init__(self, rate: float | None = None, timeout: int | None = None,
                 max_retries: int = 4, pool: int | None = None):
        self.timeout = timeout or config.HTTP_TIMEOUT
        self.max_retries = max_retries
        self.limiter = RateLimiter(rate if rate is not None else config.REQ_RATE)
        pool = pool or config.HTTP_POOL
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": UA,
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",   # explicito: el server comprime ~2.6x
        })
        retry = Retry(total=2, backoff_factor=0.6,
                      status_forcelist=[500, 502, 503, 504],
                      allowed_methods=["GET"])
        adapter = HTTPAdapter(max_retries=retry, pool_connections=pool, pool_maxsize=pool)
        self.session.mount("https://", adapter)

    def _get(self, url: str, params: dict) -> dict | None:
        for attempt in range(1, self.max_retries + 1):
            self.limiter.wait()
            try:
                r = self.session.get(url, params=params, timeout=self.timeout)
                if r.status_code == 429:
                    # respetar Retry-After si viene; si no, backoff progresivo
                    ra = r.headers.get("Retry-After")
                    wait = float(ra) if (ra and ra.isdigit()) else 1.5 * attempt
                    time.sleep(min(wait, 20))
                    continue
                r.raise_for_status()
                return _loads(r.content)
            except (requests.exceptions.SSLError,
                    requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout):
                time.sleep(0.8 * attempt)
            except requests.HTTPError:
                if attempt == self.max_retries:
                    return None
                time.sleep(0.8 * attempt)
            except ValueError:  # JSON invalido
                return None
        return None

    def batch(self, product_ids: list[str], market: str, locale: str = "en-US") -> list[dict]:
        """Devuelve la lista Products para hasta ~500 IDs."""
        params = {
            "bigIds": ",".join(product_ids),
            "market": market,
            "languages": locale,
            "fieldsTemplate": "details",
        }
        data = self._get(BASE, params)
        if not data:
            return []
        return data.get("Products") or []

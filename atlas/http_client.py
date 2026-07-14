"""Cliente HTTP resiliente para displaycatalog: reintentos, backoff y rate-limit.

La API es publica y sin auth, pero responde con caidas SSL intermitentes y 429
ocasionales. Este cliente centraliza esa robustez.
"""
from __future__ import annotations
import time
import threading
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = "https://displaycatalog.mp.microsoft.com/v7.0/products"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")


class RateLimiter:
    """Limita a `rate` peticiones por segundo (token bucket simple, thread-safe)."""
    def __init__(self, rate: float):
        self.min_interval = 1.0 / rate if rate > 0 else 0.0
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self):
        with self._lock:
            now = time.monotonic()
            if now < self._next:
                time.sleep(self._next - now)
                now = time.monotonic()
            self._next = now + self.min_interval


class CatalogClient:
    def __init__(self, rate: float = 5.0, timeout: int = 20, max_retries: int = 4):
        self.timeout = timeout
        self.max_retries = max_retries
        self.limiter = RateLimiter(rate)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": UA, "Accept": "application/json"})
        retry = Retry(total=3, backoff_factor=0.6,
                      status_forcelist=[429, 500, 502, 503, 504],
                      allowed_methods=["GET"])
        adapter = HTTPAdapter(max_retries=retry, pool_connections=32, pool_maxsize=32)
        self.session.mount("https://", adapter)

    def _get(self, url: str, params: dict) -> dict | None:
        for attempt in range(1, self.max_retries + 1):
            self.limiter.wait()
            try:
                r = self.session.get(url, params=params, timeout=self.timeout)
                if r.status_code == 429:
                    time.sleep(1.5 * attempt)
                    continue
                r.raise_for_status()
                return r.json()
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
        """Devuelve la lista Products para hasta ~500 IDs. Usar lotes de 100-200."""
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

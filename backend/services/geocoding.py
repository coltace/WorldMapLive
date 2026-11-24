import copy
import os
import threading
import time
from collections import OrderedDict

import requests

BASE_URL = os.getenv("NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org").rstrip("/")
USER_AGENT = "WorldMapLive/1.0 (contact: acevolt@atomic.io)"
CACHE_TTL_SECONDS = 6 * 60 * 60
CACHE_MAX_ENTRIES = 512
MIN_REQUEST_INTERVAL_SECONDS = 1.1


class GeocodingService:
    """Nominatim adapter with a shared per-process throttle and short-lived cache."""

    def __init__(self, base_url=None, min_request_interval=MIN_REQUEST_INTERVAL_SECONDS):
        self.base_url = (base_url or BASE_URL).rstrip("/")
        self.min_request_interval = max(0.0, float(min_request_interval))
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self._lock = threading.Lock()
        self._last_request_started = 0.0
        self._cache = OrderedDict()

    def _configured_base_url(self):
        try:
            from flask import current_app

            return current_app.config.get("NOMINATIM_BASE_URL", self.base_url).rstrip("/")
        except RuntimeError:
            return self.base_url

    def _configured_interval(self):
        try:
            from flask import current_app

            interval = current_app.config.get("NOMINATIM_MIN_REQUEST_INTERVAL", self.min_request_interval)
            return max(0.0, float(interval))
        except (RuntimeError, TypeError, ValueError):
            return self.min_request_interval

    def _request_json(self, endpoint, params):
        base_url = self._configured_base_url()
        cache_key = (
            base_url,
            endpoint,
            tuple(sorted((str(key), str(value)) for key, value in params.items())),
        )
        with self._lock:
            now = time.monotonic()
            cached = self._cache.get(cache_key)
            if cached and cached[0] > now:
                self._cache.move_to_end(cache_key)
                return copy.deepcopy(cached[1])
            if cached:
                self._cache.pop(cache_key, None)

            wait_seconds = self._configured_interval() - (now - self._last_request_started)
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            self._last_request_started = time.monotonic()
            response = self.session.get(
                f"{base_url}/{endpoint}",
                params=params,
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            self._cache[cache_key] = (time.monotonic() + CACHE_TTL_SECONDS, data)
            self._cache.move_to_end(cache_key)
            while len(self._cache) > CACHE_MAX_ENTRIES:
                self._cache.popitem(last=False)
            return copy.deepcopy(data)

    @staticmethod
    def _address_result(result):
        try:
            lat = float(result["lat"])
            lng = float(result["lon"])
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                return None
            address = result.get("address")
            display_name = result.get("display_name")
            if not isinstance(display_name, str) or not display_name.strip():
                return None
            namedetails = result.get("namedetails")
            if not isinstance(namedetails, dict):
                namedetails = {}
            name = result.get("name") or namedetails.get("name")
            if not isinstance(name, str):
                name = None
            return {
                "lat": lat,
                "lng": lng,
                "name": name,
                "formatted_address": display_name.strip(),
                "address": address if isinstance(address, dict) else {},
                "category": result.get("category"),
                "type": result.get("type"),
                "osm_type": result.get("osm_type"),
                "osm_id": result.get("osm_id"),
            }
        except (KeyError, TypeError, ValueError):
            return None

    def search_addresses(self, address, limit=6):
        if not isinstance(address, str) or not address.strip():
            return []
        limit = max(1, min(int(limit), 8))
        try:
            results = self._request_json(
                "search",
                {
                    "q": address.strip(),
                    "format": "jsonv2",
                    "limit": limit,
                    "addressdetails": 1,
                    "namedetails": 1,
                },
            )
            if not isinstance(results, list):
                return None
            return [candidate for item in results if (candidate := self._address_result(item))]
        except (requests.RequestException, ValueError, TypeError, KeyError):
            return None

    def get_coordinates(self, address):
        results = self.search_addresses(address, limit=1)
        if not results:
            return None
        result = results[0]
        return {
            "lat": result["lat"],
            "lng": result["lng"],
            "formatted_address": result["formatted_address"],
        }

    def get_address_details(self, lat, lng):
        try:
            result = self._request_json(
                "reverse",
                {
                    "lat": lat,
                    "lon": lng,
                    "format": "jsonv2",
                    "zoom": 18,
                    "addressdetails": 1,
                    "namedetails": 1,
                },
            )
            return self._address_result(result) if isinstance(result, dict) else None
        except (requests.RequestException, ValueError, TypeError):
            return None

    def get_address(self, lat, lng):
        result = self.get_address_details(lat, lng)
        return result["formatted_address"] if result else None


geocoding_service = GeocodingService()

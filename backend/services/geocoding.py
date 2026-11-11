import requests

BASE_URL = "https://nominatim.openstreetmap.org"
USER_AGENT = (
    "WorldMapLive/1.0 "
    "(contact: acevolt@atomic.io)"
)

class GeocodingService:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT
        })

    def get_coordinates(self, address):
        if not isinstance(address, str) or not address.strip():
            return None

        try:
            response = self.session.get(
                f"{BASE_URL}/search",
                params={
                    "q": address.strip(),
                    "format": "jsonv2",
                    "limit": 1,
                    "addressdetails": 1,
                },
                timeout=15,
            )
            response.raise_for_status()
            results = response.json()

            if not results:
                return None

            result = results[0]

            return {
                "lat": float(result["lat"]),
                "lng": float(result["lon"]),
                "formatted_address": result["display_name"],
            }

        except (requests.RequestException, ValueError, KeyError):
            return None

    def get_address(self, lat, lng):
        try:
            response = self.session.get(
                f"{BASE_URL}/reverse",
                params={
                    "lat": lat,
                    "lon": lng,
                    "format": "jsonv2",
                    "zoom": 18,
                },
                timeout=15,
            )
            response.raise_for_status()
            result = response.json()

            return result.get("display_name")

        except (requests.RequestException, ValueError):
            return None


geocoding_service = GeocodingService()

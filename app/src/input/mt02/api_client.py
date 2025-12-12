import requests
import time

from app.core.logger import get_logger
from app.config.settings import settings

logger = get_logger(__name__)

class MT02ApiClient:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("API key must be provided")
        
        self.api_key = api_key
    
    def _get_headers(self):
        return {
            "api_token": self.api_key,
            "timestamp": str(int(time.time())),
            "Content-Type": "application/json"
        }
    
    def fetch_devices(self):
        try:

            return []  # Placeholder for actual API call
        
        except requests.RequestException as e:
            logger.info(f"Error fetching devices: {e}")
        
        except Exception as e:
            logger.info(f"Unexpected error: {e}")

    def fetch_device_location(self, device_id: str):
        try:
            url = f"{settings.MT02_API_BASE_URL}/tag"
            params = {"ids": device_id}
            headers = self._get_headers()

            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()

            return response.json()
        
        except requests.RequestException as e:
            logger.info(f"Error fetching location for device {device_id}: {e}")
        
        except Exception as e:
            logger.info(f"Unexpected error: {e}")

    def fetch_all(self):
        try:
            devices = self.fetch_devices()
            all_locations = {}

            if not devices:
                logger.info("No devices found.")
                return all_locations

            for device_id in devices:
                location = self.fetch_device_location(device_id)
                if location:
                    all_locations[device_id] = location

            return all_locations
        
        except Exception as e:
            logger.info(f"Error fetching all device locations: {e}")
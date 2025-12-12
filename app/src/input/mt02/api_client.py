import requests
import time

from app.core.logger import get_logger
from app.config.settings import settings

logger = get_logger(__name__)

# -- MT02ApiClient class definition -- 
# This class handles communication with the MT02 manufacturer API.
# Making a client class allows for better organization and reuse of API interaction logic.
class MT02ApiClient:
    # Constructor to initialize the API client with the necessary API key.
    def __init__(self, api_key: str):
        if not api_key: # Ensure an API key is provided
            raise ValueError("API key must be provided")
        
        self.api_key = api_key
    
    # Helper method to construct headers for API requests.
    def _get_headers(self):
        return {
            "api_token": self.api_key,
            "timestamp": str(int(time.time())),
            "Content-Type": "application/json"
        }
    
    # Method to fetch the list of devices from the MT02 API.
    def fetch_devices(self):
        try:

            return []  # Placeholder for actual API call
        
        except requests.RequestException as e:
            logger.info(f"Error fetching devices: {e}")
        
        except Exception as e:
            logger.info(f"Unexpected error: {e}")

    # Method to fetch location data for a specific device by its ID.
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

    # Method to fetch location data for all devices.
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
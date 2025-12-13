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
            
            # Preparing requests.get arguments
            url = f"{settings.MT02_API_BASE_URL}/tag/all"
            params = {
                "isActived": True,
            }
            headers = self._get_headers()

            # Preparing list to store all tags
            all_devices = []
            
            # Starting the current page
            current_page = 1
            while True:
                # Passing the current page as a parameter
                params["page"] = current_page

                # Requesting response
                response = requests.get(url, params, headers=headers)
                response.raise_for_status() # To catch HTTP errors

                # Getting the json data as a dict
                page_data = response.json()
                
                # Checking if there are devices on this page
                if not page_data.get("data"):
                    break
                
                # Storing devices
                all_devices += page_data["data"]

                # Turning page
                current_page += 1

            # Returning all devices encontered
            return all_devices
        
        except requests.RequestException as e:
            logger.info(f"Error fetching devices: {e}")

            return [] # To always receive a list
        
        except Exception as e:
            logger.info(f"Unexpected error: {e}")

            return [] # To always receive a list

    # Method to fetch location data for a specific device by its ID.
    def fetch_device_location(self, device_id: str):
        try:
            # Preparing requests.get arguments
            url = f"{settings.MT02_API_BASE_URL}/tag"
            params = {
                "ids": device_id
            }
            headers = self._get_headers()

            # Requesting the response
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status() # To catch HTTP errors

            return response.json() # Returning the json location data as a dict
        
        except requests.RequestException as e:
            logger.info(f"Error fetching location for device {device_id}: {e}")
        
        except Exception as e:
            logger.info(f"Unexpected error: {e}")

    # Method to fetch location data for all devices.
    def fetch_all(self):
        try:
            # First we fetch all devices for the given token
            devices = self.fetch_devices()

            # Checking if there are any device
            if not devices:
                logger.info("No devices found.")
                return all_locations
            
            # If there are, declaring a variable store all locations from the devices previously fetched
            all_locations = {}
            
            # For each device, we fetch the device location and stores it in "all_locations"
            for device_id in devices:
                location = self.fetch_device_location(device_id) # Fetch the location data
                if location and location.get("data"):
                    all_locations[str(device_id)] = location["data"] # Converting dev id to str

            # Returning it
            return all_locations
        
        except Exception as e:
            logger.info(f"Error fetching all device locations: {e}")
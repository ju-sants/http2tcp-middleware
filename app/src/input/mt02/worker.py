import threading

from . import processor
from .api_client import MT02ApiClient
from app.config.settings import settings
from app.services.redis_service import get_redis
from app.core.logger import get_logger

logger = get_logger(__name__)
redis_client = get_redis()

api_client = MT02ApiClient(api_key=settings.MT02_API_KEY)

def worker():
    """
    Routine that performs the action of retrieve location data from the manufacturer API.
    """

    # Main loop of the worker, that runs indefinitely.
    while True:
        try:
            # Fetch all location data from the API.
            locations = api_client.fetch_all()
            if not locations:
                logger.info("No location data retrieved this time.")
                continue

            logger.info(f"Fetched locations for {len(locations)} devices.")

            # For each location, we check if the data was already processed in a past iteration.
            for device_id, location in locations.items():
                device_key = f"device:mt02:{device_id}"
                last_processed_timestamp = redis_client.hget(device_key, "last_timestamp")

                # If the location data is new (not processed before), we store it in Redis.
                is_new = not last_processed_timestamp or int(location['timestamp']) > int(last_processed_timestamp)
                if not is_new:
                    logger.info(f"No new location for device {device_id}.")
                    continue
                
                # Store the new location timestamp in Redis to mark it as processed.
                redis_client.hset(device_key, "last_timestamp", location["timestamp"])
                logger.info(f"New location for device {device_id}: {location}")

                # Pass the new location to the processor for further handling.
                threading.Thread(target=processor.process_location, args=(device_id, location)).start()

        except Exception as e:
            logger.info(f"Error in worker loop: {e}")
        
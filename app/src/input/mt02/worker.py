from .api_client import MT02ApiClient
from app.config.settings import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

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

        except Exception as e:
            logger.info(f"Error in worker loop: {e}")
        
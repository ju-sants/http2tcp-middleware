from datetime import datetime
from dateutil.relativedelta import relativedelta

from app.core.logger import get_logger

logger = get_logger(__name__)

def map_location_data(device_id: str, location: dict) -> dict:
    """
    Map the raw location data from MT02 API to the internal format.

    :param device_id: Device Identifier
    :type device_id: str
    :param location: Raw location data from MT02 API
    :type location: dict
    :return: Mapped location data in internal format
    :rtype: dict
    """

    logger.info(f"Mapping location data for device {device_id}: {location}")

    # The timestamp of the MT02 tag is in UTC-3 timezone
    # But the majority of geolocation server accept only UTC time zones
    # So we adding 3 more hours to the date time

    # First converting it
    date_time = datetime.fromtimestamp(location.get("timestamp", 0))

    # Then adding the hours
    date_time += relativedelta(hours=3)

    mapped_data = {
        "timestamp": date_time,
        "latitude": location.get("lat"),
        "longitude": location.get("lng"),
    }
    
    return mapped_data
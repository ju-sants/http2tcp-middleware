from datetime import datetime

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

    mapped_data = {
        "timestamp": datetime.fromtimestamp(location.get("timestamp", 0)),
        "latitude": location.get("lat"),
        "longitude": location.get("lng"),
    }
    
    return mapped_data
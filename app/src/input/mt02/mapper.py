from datetime import datetime
from dateutil.relativedelta import relativedelta

from app.core.logger import get_logger
from app.services.redis_service import get_redis
from .. import utils as input_source_utils

logger = get_logger(__name__)
redis_client = get_redis()

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

    lat, lon = location.get("lat"), location.get("lng")
    if not lat or not lon:
        logger.error(f"It was not possible to continue the mapping of the data, coordinates corrupted.")
        return {}
    
    device_key = device_key = f"device:mt02:{device_id}"

    odometer = redis_client.hget(device_key, "last_odometer")
    if not odometer:
        odometer = 0

    last_lat, last_lon = redis_client.hmget(device_key, "last_lat", "last_lon")
    if last_lat and last_lon:
        args = list(map(float, [lat, lon, last_lat, last_lon]))

        meters_calculated = input_source_utils.haversine(*args)
        odometer += meters_calculated

        redis_client.hset(device_key, "last_odometer", odometer)

    else:
        logger.warning(f"There are not coordinates stored in the devices state storage. Continue with 0 odometer")
        
    mapped_data = {
        "timestamp": date_time,
        "latitude": lat,
        "longitude": lon,
        "satellites": 6, # Mock satellites so the server can accept our packets
        "gps_odometer": odometer,
    }
    
    return mapped_data
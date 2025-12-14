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

    # First converting the timestamp
    date_time = datetime.fromtimestamp(location.get("timestamp", 0))

    # Then checking the lat and lon information
    lat, lon = location.get("lat"), location.get("lng")
    if not lat or not lon:
        logger.error(f"It was not possible to continue the mapping of the data, coordinates corrupted.")
        return {}
    
    # If the lat and lon are reliable, lets construct the redis device key
    device_key = device_key = f"device:mt02:{device_id}"

    # Retrieve the last_odometer from redis
    odometer = redis_client.hget(device_key, "last_odometer")
    
    # If there are no odometer set it to 0
    if not odometer:
        odometer = 0

    # Retrieve the last lat and last lon from redis
    last_lat, last_lon = redis_client.hmget(device_key, "last_lat", "last_lon")
    
    # If there are last lat and lon, lets confirm that they are float types
    # And pass they to the haversine fórmula function
    if last_lat and last_lon:
        args = list(map(float, [lat, lon, last_lat, last_lon])) # mapping float to every member of the iterable

        # Calculate haversine
        meters_calculated = input_source_utils.haversine(*args)
        
        # Adds it to odometer
        odometer += meters_calculated

        # Save it to redis, so the next time it will be set
        redis_client.hset(device_key, "last_odometer", odometer)

    else:
        # If there are not last lat and lon, lets return the 0 odometer
        logger.warning(f"There are not coordinates stored in the devices state storage. Continue with 0 odometer")

    # ---
    
    # Now, lets gave the "baterry" information of the mt02 location data some meaning

    # Getting the voltage level from the location data
    battery_level = location.get("battery", 0)

    battery_based_voltage = None # Its a voltage that instead of the voltage of the battery, represents the level of it
    if battery_level and battery_level != -1: # If theres a battery level

        # Calculate the percentage of it with a math fórmula
        battery_based_voltage = (battery_level * 100) / 3

        # This way, we can use the voltage field on the binary packet to represent the battery of the device

        # Saving it on the device state storage
        redis_client.hset(device_key, "voltage", battery_based_voltage)
    
    # ---
    
    # Mapping the data
    #  to a structured python dict
    mapped_data = {
        "timestamp": date_time,
        "latitude": lat,
        "longitude": lon,
        "satellites": 6, # Mock satellites so the server can accept our packets
        "gps_odometer": odometer,
        "voltage": battery_based_voltage or 1.11,
    }
    
    # Returning it
    return mapped_data
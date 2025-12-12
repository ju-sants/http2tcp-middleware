from . import mapper
from app.core.logger import get_logger
from app.src.session.output_session import output_processor

logger = get_logger(__name__)

def process_location(device_id: str, location: dict):
    """
    Process the new location data for a device.
    This function forwards the data to a mapper and then to output.
    
    :param device_id: Device Identifier
    :type device_id: str
    :param location: Device location data
    :type location: dict
    """

    logger.info(f"Processing location for device {device_id}: {location}")

    # Map the location data to the internal format
    mapped_data = mapper.map_location_data(device_id, location)

    # Forward the mapped data to the output processor
    output_processor.forward(device_id, mapped_data)
from app.core.logger import get_logger

logger = get_logger(__name__)

def map_command(dev_id: str, command: bytes):
    """
    Map GT06 specific command bytes to a universal command format.
    
    :param dev_id: Description
    :type dev_id: str
    :param command: Description
    :type command: bytes
    """
    logger.info(f"Mapping GT06 command to universal format. command_bytes={command.hex()}")

    command_length = command[4] - 4
    command_content = command[9:9 + command_length]
    command_key = command_content.decode("ascii", errors="ignore")

    logger.info(f"Extracted command key: {command_key}")

    command_mapping = {
        "RELAY,1#": "OUTPUT ON",
        "DYD,000000#": "OUTPUT ON",
        "RELAY,0#": "OUTPUT OFF",
        "HFYD,000000#": "OUTPUT OFF",
        "GPRS,GET,LOCATION#": "PING",
    }

    if command_key.startswith("MILEAGE"):
        kilometers = command_key.split("ON,")[-1].replace("#", "")
        if not kilometers.isdigit():
            logger.info(f"Invalid mileage value: {kilometers}")
            return
        
        meters = int(kilometers) * 1000
        return f"HODOMETRO:{meters}"

    return command_mapping.get(command_key)
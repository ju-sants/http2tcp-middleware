from pydantic import BaseModel

from . import gt06, suntech4g

class OutputMappers(BaseModel):
    
    OUTPUT_PACKET_BUILDERS: dict = {
        "gt06": {
            "location": gt06.build_location_packet,
            "heartbeat": gt06.build_heartbeat_packet,
            "info": gt06.build_voltage_info_packet,
            "login": gt06.build_login_packet,
        },
        # "suntech4g": {
        #     "location": suntech4g.build_location_packet,
        #     "heartbeat": suntech4g.build_heartbeat_packet,
        #     "login": suntech4g.build_login_packet,
        # }
    }

    OUTPUT_COMMAND_MAPPERS: dict = {
        "gt06": gt06.map_command,
        # "suntech4g": suntech4g.map_command,
    }

output_mappers = OutputMappers()
import struct
from datetime import datetime

from app.core.logger import get_logger
from ..utils import crc_itu
from ..utils import get_output_dev_id
from app.config.settings import settings

logger = get_logger(__name__)

def build_location_packet(dev_id: str, packet_data: dict, serial_number: int, *args) -> bytes:
    """
    Builds a GT06 location packet from the "packet_data" data source.
    Suports different types of protocols (protocol_number): 0x22, 0x32, 0xA0 
    """

    # Note on struct: struct is a python library used to pack python native types (ex: int, string, float, etc...)
    # Into a binary data, or to unpack binary data into python native types.
    # The methods struct.pack and struct.unpack needs the developer to specify the format in the first argument
    # ">" Means "Big Endian" it's the "orientation" of the number, so how we read "1000" from left to right
    # the binary data must be read this way (in other hand "<" means "Little Endian" wich is the opposite)
    # "B" means "Byte" or "One Byte" it tells struct to pack python data into a single byte or to unpack a single byte to a python data
    # "H" means "Word" or "Two bytes" and follows the same logic, so how are "I" and "Q".

    protocol_number = settings.GT06_LOCATION_PACKET_PROTOCOL_NUMBER # We will use the protocol_number specified in settings

    # First we get the timestamp from the packet data
    # and dissecate it part-by-part, pass it to struct and pack into "time_bytes"
    timestamp: datetime = packet_data.get("timestamp", datetime.now())
    time_bytes = struct.pack(
        ">BBBBBB", # We pass this format, that means one byte for each part of the date, in ">" Big Endian
        timestamp.year % 100, # Module of the year, gets only the final part. Ex: 2025 -> 25
        timestamp.month,
        timestamp.day,
        timestamp.hour,
        timestamp.minute,
        timestamp.second,
    )

    # Now we will mount the gps length and quantity of satellites byte
    # this byte combine two informations, the gps information length that is fixed to 12 (0xC in Hex)
    # And the quantity of satellites
    packet_satellites = packet_data.get("satellites", 0)
    satellites = min(15, packet_satellites) # The quantity of satellites field in the GT06 protocol have a fixed length of a nibble (4 bits, max decimal value of 15)
    gps_info = 0xC0 | satellites # Now we apply a mask (OR) to merge the two informations into a single byte
    gps_info_byte = struct.pack(">B", gps_info)

    # Mounting the latitude and longitue bytes
    latitude_val = packet_data.get("latitude", 0.0)
    longitude_val = packet_data.get("longitude", 0.0)
    
    # converting the floating point values of lat and long into integers
    lat_raw = int(abs(latitude_val) * 1800000)
    lon_raw = int(abs(longitude_val) * 1800000)

    # Packing it into "lat_lon_bytes"
    lat_lon_bytes = struct.pack(">II", lat_raw, lon_raw)

    # Mouting the speed kmh byte
    speed_kmh = int(packet_data.get("speed_kmh", 0))
    speed_kmh_bytes = struct.pack(">B", speed_kmh)

    # Mouting the course and status byte
    # Course and status byte carryes various informations
    # The principals informations are: GPS Fixed, Hemisfer of latitude and lingitude
    # And the direction of the movement 

    # Here we apply a mask that isolates the 11 last significant bytes (the ones to the rigth)
    # To have the certainty that this field only ocupates 11 bits length
    direction = int(packet_data.get("direction", 0)) & 0x03FF

    # Then we prepare the other information tu put in the five bits left
    gps_fixed = 1 if packet_data.get("gps_fixed", False) else 0
    
    is_latitude_north = 1 if latitude_val >= 0 else 0 # Deciding the hemisfer of latitude
    is_longitude_west = 1 if longitude_val < 0 else 0 # Deciding the hemisfer of longitude

    # Here we use a mask (OR) to combine the direction byte with the others informations packing it to a 2 bytes length field
    course_status = (gps_fixed << 12) | (is_longitude_west << 11) | (is_latitude_north << 10) | direction
    course_status_bytes = struct.pack(">H", course_status) # Packing it
    
    # ==============================================================================================================================
    # Finally putting it all together, forming the body of the packet
    content_body = time_bytes + gps_info_byte + lat_lon_bytes + speed_kmh_bytes + course_status_bytes
    
    acc_status = 1 if packet_data.get("acc_status", 1) else 0
    gps_odometer = int(packet_data.get("gps_odometer", 0))
    voltage = float(packet_data.get("voltage", 0.0))
    voltage_raw = int(voltage * 100)

    # Getting the saved LBS information
    mcc = 0
    mnc = 0
    lac = 0
    cell_id = 0

    if protocol_number == 0x12:
        content_body += struct.pack(">H", mcc)
        content_body += struct.pack(">B", mnc)
        content_body += struct.pack(">H", lac)
        content_body += cell_id.to_bytes(3, "big")

    elif protocol_number == 0x22:
        content_body += struct.pack(">H", mcc)
        content_body += struct.pack(">B", mnc)
        content_body += struct.pack(">H", lac)
        content_body += cell_id.to_bytes(3, "big")

        content_body += struct.pack(">B", acc_status)
        content_body += b'\x00' # Data Upload
        content_body += b'\x00' # Sempre em tempo real, para que a plataforma principal possa ouvir os pacotes de voltagem
        content_body += struct.pack(">I", gps_odometer) # Mileage

    elif protocol_number == 0x32:
        content_body += struct.pack(">H", mcc)
        content_body += struct.pack(">B", mnc)
        content_body += struct.pack(">H", lac)
        content_body += struct.pack(">I", cell_id)

        content_body += struct.pack(">B", acc_status)
        content_body += b'\x00'
        content_body += b'\x00' # Sempre em tempo real, para que a plataforma principal possa ouvir os pacotes de voltagem
        content_body += struct.pack(">I", gps_odometer)
        content_body += struct.pack(">H", voltage_raw)
        content_body += b"\x00" * 6

    elif protocol_number == 0xA0:
        content_body += struct.pack(">H", mcc)
        content_body += struct.pack(">H", mnc)

        content_body += struct.pack(">I", lac)
        content_body += struct.pack(">Q", cell_id)


        content_body += struct.pack(">B", acc_status)
        content_body += b'\x00'
        content_body += b'\x00' # Sempre em tempo real, para que a plataforma principal possa ouvir os pacotes de voltagem
        content_body += struct.pack(">I", gps_odometer)
        content_body += struct.pack(">H", voltage_raw)

    # 1 (protocol_number) + len(content_body) + 2 (serial_number) + 2 (CRC)
    length_value = 1 + len(content_body) + 2 + 2
    length_byte = struct.pack(">B", length_value)

    data_for_crc = length_byte + struct.pack(">B", protocol_number) + content_body + struct.pack(">H", serial_number)
    
    crc = crc_itu(data_for_crc)
    crc_bytes = struct.pack(">H", crc)

    final_packet = (
        b"\x78\x78" +
        data_for_crc +
        crc_bytes +
        b"\x0d\x0a"
    )

    logger.debug(f"Construído pacote de localização GT06 (Protocol {hex(protocol_number)}): {final_packet.hex()}")
    return final_packet

def imei_to_bcd(imei: str) -> bytes:
    if len(imei) > 15 or len(imei) < 15 or not imei.isdigit():
        raise ValueError("IMEI must be a 15-digit string.")
    
    imei_padded = "0" + imei
    bcd_bytes = bytearray()
    for i in range(0, len(imei_padded), 2):
        byte_val = (int(imei_padded[i]) << 4) | int(imei_padded[i+1])
        bcd_bytes.append(byte_val)
    return bytes(bcd_bytes)

def build_login_packet(imei: str, serial_number: int) -> bytes:
    """
    Constrói um pacote de login GT06.
    """
    protocol_number = 0x01

    output_imei = get_output_dev_id(imei, "gt06")

    imei_bcd = imei_to_bcd(output_imei)

    packet_content_for_crc = (
        struct.pack(">B", protocol_number) +
        imei_bcd +
        struct.pack(">H", serial_number)
    )

    # 1 (protocol) + 8 (IMEI) + 2 (serial) + 2 (CRC placeholder)
    packet_length_value = len(packet_content_for_crc) + 2

    data_for_crc = struct.pack(">B", packet_length_value) + packet_content_for_crc

    crc = crc_itu(data_for_crc)

    full_packet = (
        b"\x78\x78" +
        struct.pack(">B", packet_length_value) +
        packet_content_for_crc +
        struct.pack(">H", crc) +
        b"\x0d\x0a"
    )

    logger.debug(f"Construído pacote de login GT06: {full_packet.hex()}")
    return full_packet


def build_heartbeat_packet(dev_id: str, *args) -> bytes:
    """
    Controi um pacote de Heartbeat GT06.
    """

    protocol_number = struct.pack(">B", 0x13)

    acc_status = 1
    last_output_status = 0
    serial = 0

    terminal_info_content = (int(last_output_status) << 7) | (1 << 6) | (1 << 2) | (int(acc_status) << 1) | 1
    terminal_info_content_bytes = struct.pack(">B", terminal_info_content)

    voltage_level = struct.pack(">B", 6)
    gsm_signal_strenght = struct.pack(">B", 0x04)
    alarm = struct.pack(">B", 0x00)
    language = struct.pack(">B", 0x02)
    serial = struct.pack(">H", int(serial))

    data_for_crc = (
        protocol_number +
        terminal_info_content_bytes +
        voltage_level +
        gsm_signal_strenght +
        alarm +
        language +
        serial
    )

    packet_lenght = len(data_for_crc)

    data_for_crc = (struct.pack(">B", packet_lenght) + data_for_crc)

    crc = crc_itu(data_for_crc)

    full_packet = (
        b"\x78\x78" + 
        data_for_crc +
        struct.pack(">H", crc) +
        b"\x0D\x0A"
    )

    return full_packet


def build_voltage_info_packet(packet_data: dict, serial_number: int) -> bytes:
    """
    Constrói um pacote de informação (Protocolo 0x94),
    enviando exclusivamente a informação de voltagem externa (Sub-protocolo 0x00).
    """
    protocol_number = 0x94
    sub_protocol_number = 0x00

    voltage = float(packet_data.get("voltage", 0.0))
    voltage_raw = int(voltage * 100)
    information_content = struct.pack(">H", voltage_raw)

    body_packet = (
        struct.pack(">B", protocol_number) +
        struct.pack(">B", sub_protocol_number) +
        information_content +
        struct.pack(">H", serial_number)
    )

    packet_length_value = len(body_packet) + 2
    packet_length_bytes = struct.pack(">H", packet_length_value)

    data_for_crc = packet_length_bytes + body_packet
    
    crc = crc_itu(data_for_crc)
    crc_bytes = struct.pack(">H", crc)

    final_packet = (
        b"\x79\x79" + 
        data_for_crc +
        crc_bytes +   
        b"\x0d\x0a"   
    )

    logger.info(f"Construído pacote de Informação (Protocol {hex(protocol_number)}): {final_packet.hex()}")
    return final_packet
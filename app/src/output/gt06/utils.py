from crc import Calculator, Configuration

def crc_itu(data_bytes: bytes) -> int:
    """
    Calculates the CRC ITU of a binary packet.
    
    :param data_bytes: Binary packet to calculate.
    :type data_bytes: bytes
    :return: The CRC ITU result from the calculation
    :rtype: int
    """

    config = Configuration(
        width=16,
        polynomial=0x1021,
        init_value=0xFFFF,
        final_xor_value=0xFFFF,
        reverse_input=True,
        reverse_output=True,
    )

    calculator = Calculator(config)
    crc_value = calculator.checksum(data_bytes)
    return crc_value

def dev_id_to_bcd(dev_id: str) -> bytes:
    """
    Encode device id's to BCD encoding (Binary Coded Decimal)
    
    :param dev_id: Device Identifier
    :type dev_id: str
    :return: Return device's id encoded to BCD.
    :rtype: bytes
    """

    # Validating the dev_id
    if len(dev_id) > 15 or len(dev_id) < 15 or not dev_id.isdigit():
        raise ValueError("dev_id must be a 15-digit string.")
    
    # Padding the dev_id with a 0 to the left to complete a 16 digits string.
    dev_id_padded = "0" + dev_id

    # Using bytearray to use standard array python methods
    # Like append and others, here we dinamically append bytes to it  
    bcd_bytes = bytearray()
    for i in range(0, len(dev_id_padded), 2): # iterating through the dev_id two digits per iteration
        # packing the two digits of this iteration into one byte
        byte_val = (int(dev_id_padded[i]) << 4) | int(dev_id_padded[i+1])
        # appending to the bytes array
        bcd_bytes.append(byte_val)

    # merging the bytes in the array to a single packet
    return bytes(bcd_bytes)

def normalize_dev_id(dev_id: str) -> str:
    """
    Normalize devices ids by filtering only the digits of the string and filling it with
    0s to the left.
    
    :param dev_id: Device Identifier
    :type dev_id: str
    :return: Normalized Device Identifier
    :rtype: str
    """

    dev_id = dev_id.zfill(20)
    
    return ''.join(filter(str.isdigit, dev_id))

def get_output_dev_id(dev_id: str, output_protocol: str) -> str:
    """
    Get the device ID normalized according to the rules of the output_protocol
    
    :param dev_id: Device Identifier
    :type dev_id: str
    :param output_protocol: Output Protocol
    :type output_protocol: str
    :return: Normalized Device Identifier
    :rtype: str
    """
    dev_id = normalize_dev_id(dev_id)
    output_dev_id = None

    if output_protocol.lower() == "suntech4g":
        output_dev_id = dev_id[-10:]
    if output_protocol.lower() == "gt06":
        output_dev_id = dev_id[-15:]

    return output_dev_id

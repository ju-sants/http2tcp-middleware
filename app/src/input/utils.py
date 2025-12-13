from math import radians, sin, cos, atan2, sqrt

def haversine(lat1: float, lon1: float, lat2: float, lon2: float):
    """
    Calculates the haversine formula in two coordinates (pairs of lat and lon)
    And return the meters calculed distance
    
    :param lat1: First lat
    :type lat1: float
    :param lon1: First lon
    :type lon1: float
    :param lat2: Second lat
    :type lat2: float
    :param lon2: Second lon
    :type lon2: float
    """

    # Obtaining the radians of each coordinate
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Rest of the formula (Not really know exacly how its internal working)    
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a)) 
    r = 6371
    return int((c * r) * 1000) # Convertendo para metros e int
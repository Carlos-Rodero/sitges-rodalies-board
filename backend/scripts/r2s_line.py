R2S_STATIONS = [
    {"code": "SVC", "stop_id": "71600", "name": "Sant Vicenç de Calders"},
    {"code": "CAL", "stop_id": "71601", "name": "Calafell"},
    {"code": "SEG", "stop_id": "71602", "name": "Segur de Calafell"},
    {"code": "CUN", "stop_id": "71603", "name": "Cunit"},
    {"code": "CUB", "stop_id": "71604", "name": "Cubelles"},
    {"code": "VNG", "stop_id": "71700", "name": "Vilanova i la Geltrú"},
    {"code": "SIT", "stop_id": "71701", "name": "Sitges"},
    {"code": "GAR", "stop_id": "71703", "name": "Garraf"},
    {"code": "PCF", "stop_id": "71704", "name": "Platja de Castelldefels"},
    {"code": "CDF", "stop_id": "71705", "name": "Castelldefels"},
    {"code": "GAV", "stop_id": "71706", "name": "Gavà"},
    {"code": "VLD", "stop_id": "71709", "name": "Viladecans"},
    {"code": "ELP", "stop_id": "71707", "name": "El Prat de Llobregat"},
    {"code": "BEL", "stop_id": "71708", "name": "Bellvitge-Gornal"},
    {"code": "SAN", "stop_id": "71801", "name": "Barcelona Sants"},
    {"code": "PGR", "stop_id": "71802", "name": "Barcelona Passeig de Gràcia"},
    {"code": "EDF", "stop_id": "79400", "name": "Barcelona Estació de França"},
]

STOP_ID_TO_STATION = {
    station["stop_id"]: station
    for station in R2S_STATIONS
}

STOP_ID_TO_INDEX = {
    station["stop_id"]: index
    for index, station in enumerate(R2S_STATIONS)
}


def station_index(stop_id):
    return STOP_ID_TO_INDEX.get(str(stop_id))


def station_code(stop_id):
    station = STOP_ID_TO_STATION.get(str(stop_id))
    return station["code"] if station else str(stop_id)


def station_name(stop_id):
    station = STOP_ID_TO_STATION.get(str(stop_id))
    return station["name"] if station else str(stop_id)


def infer_direction(current_stop_id, next_stop_id):
    current_index = station_index(current_stop_id)
    next_index = station_index(next_stop_id)

    if current_index is None or next_index is None:
        return "unknown"

    if next_index > current_index:
        return "to_barcelona"

    if next_index < current_index:
        return "to_south"

    return "unknown"


def train_icon(direction):
    if direction == "to_barcelona":
        return "[>]"
    if direction == "to_south":
        return "[<]"
    return "[?]"


def estimate_line_index(vehicle_stop_id, next_stop_id, status):
    """
    Returns a float index along R2S_STATIONS.

    Important:
    - vehicle_stop_id is interpreted as the station associated with the
      vehicle status.
    - STOPPED_AT: the train is exactly at vehicle_stop_id.
    - INCOMING_AT: the train is close to vehicle_stop_id, before reaching it.
    - IN_TRANSIT_TO: the train is between the previous station and vehicle_stop_id.

    Example:
    If vehicle_stop_id=SIT and next_stop_id=VNG, the train direction is south.
    If it is INCOMING_AT SIT, it should be just to the right of SIT, because
    it is arriving from the Barcelona/Garraf side.
    """
    vehicle_index = station_index(vehicle_stop_id)
    next_index = station_index(next_stop_id)

    if vehicle_index is None:
        return None

    direction = infer_direction(vehicle_stop_id, next_stop_id)

    if status == "STOPPED_AT":
        return float(vehicle_index)

    last_index = len(R2S_STATIONS) - 1

    if direction == "to_barcelona":
        # Train moves left -> right.
        # If it is approaching vehicle_stop_id, it is slightly before it.
        if status == "INCOMING_AT":
            return max(0.0, vehicle_index - 0.15)
        if status == "IN_TRANSIT_TO":
            return max(0.0, vehicle_index - 0.50)

    if direction == "to_south":
        # Train moves right -> left.
        # If it is approaching vehicle_stop_id, it is slightly after it.
        if status == "INCOMING_AT":
            return min(float(last_index), vehicle_index + 0.15)
        if status == "IN_TRANSIT_TO":
            return min(float(last_index), vehicle_index + 0.50)

    return float(vehicle_index)

# Approximate scheduled travel time offset relative to Sitges.
# Negative values are south/west of Sitges.
# Positive values are north/east towards Barcelona.
# These are approximate and will later be replaced/refined with GTFS static.
SITGES_TIME_OFFSET_MIN = {
    "SVC": -36,
    "CAL": -29,
    "SEG": -25,
    "CUN": -21,
    "CUB": -15,
    "VNG": -7,
    "SIT": 0,
    "GAR": 5,
    "PCF": 9,
    "CDF": 13,
    "GAV": 18,
    "VLD": 22,
    "ELP": 27,
    "BEL": 32,
    "SAN": 38,
    "PGR": 43,
    "EDF": 48,
}


def station_time_offset_from_sitges(code):
    return SITGES_TIME_OFFSET_MIN.get(code)
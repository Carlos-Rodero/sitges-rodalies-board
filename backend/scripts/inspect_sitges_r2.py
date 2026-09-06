import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TRIP_UPDATES_URL = "https://gtfsrt.renfe.com/trip_updates.json"
VEHICLE_POSITIONS_URL = "https://gtfsrt.renfe.com/vehicle_positions.json"

LOCAL_TZ = ZoneInfo("Europe/Madrid")
SITGES_STOP_ID = "71701"

TARGET_ROUTE_SUFFIXES = ("R2S", "R2N")


STOP_NAMES = {
    "71701": "Sitges",
    "71703": "Garraf / zona Sitges",
    "71707": "zona Castelldefels",
    "71708": "zona Castelldefels",
    "71801": "Barcelona Sants",
    "71802": "Barcelona Pg. Gràcia",
    "71603": "Vilanova / zona sur",
}


def fetch_json(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def get_any(d, *keys, default=None):
    for key in keys:
        if isinstance(d, dict) and key in d:
            return d[key]
    return default


def parse_epoch(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def epoch_to_local(epoch):
    if epoch is None:
        return "unknown"
    return datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone(LOCAL_TZ).strftime("%H:%M:%S")


def get_stop_time_epoch(stop_time_update):
    arrival = get_any(stop_time_update, "arrival", default={})
    departure = get_any(stop_time_update, "departure", default={})

    dep_time = parse_epoch(get_any(departure, "time", default=None))
    arr_time = parse_epoch(get_any(arrival, "time", default=None))

    return dep_time if dep_time is not None else arr_time


def get_delay_seconds(stop_time_update):
    arrival = get_any(stop_time_update, "arrival", default={})
    departure = get_any(stop_time_update, "departure", default={})

    dep_delay = get_any(departure, "delay", default=None)
    arr_delay = get_any(arrival, "delay", default=None)

    delay = dep_delay if dep_delay is not None else arr_delay

    if delay is None:
        return None

    try:
        return int(delay)
    except (TypeError, ValueError):
        return None


def build_vehicle_index(vehicle_data):
    vehicle_by_trip_id = {}

    for entity in get_any(vehicle_data, "entity", default=[]):
        vehicle = get_any(entity, "vehicle", default={})
        trip = get_any(vehicle, "trip", default={})
        trip_id = str(get_any(trip, "tripId", default=""))

        if not trip_id:
            continue

        stop_id = str(get_any(vehicle, "stopId", default=""))
        status = str(get_any(vehicle, "currentStatus", default=""))
        timestamp = parse_epoch(get_any(vehicle, "timestamp", default=None))
        position = get_any(vehicle, "position", default={})
        vehicle_info = get_any(vehicle, "vehicle", default={})

        vehicle_by_trip_id[trip_id] = {
            "stop_id": stop_id,
            "stop_name": STOP_NAMES.get(stop_id, stop_id),
            "status": status,
            "timestamp": timestamp,
            "time": epoch_to_local(timestamp),
            "lat": get_any(position, "latitude", default=None),
            "lon": get_any(position, "longitude", default=None),
            "label": get_any(vehicle_info, "label", default=""),
        }

    return vehicle_by_trip_id


def is_target_trip(trip_id):
    return trip_id.endswith(TARGET_ROUTE_SUFFIXES)


def main():
    trip_data = fetch_json(TRIP_UPDATES_URL)
    vehicle_data = fetch_json(VEHICLE_POSITIONS_URL)
    vehicle_by_trip_id = build_vehicle_index(vehicle_data)

    sitges_trains = []
    nearby_updates = []

    for entity in get_any(trip_data, "entity", default=[]):
        trip_update = get_any(entity, "tripUpdate", default={})
        trip = get_any(trip_update, "trip", default={})
        trip_id = str(get_any(trip, "tripId", default=""))

        if not is_target_trip(trip_id):
            continue

        stop_time_updates = get_any(trip_update, "stopTimeUpdate", default=[])

        for stu in stop_time_updates:
            stop_id = str(get_any(stu, "stopId", default=""))
            event_epoch = get_stop_time_epoch(stu)
            delay_seconds = get_delay_seconds(stu)
            delay_min = None if delay_seconds is None else round(delay_seconds / 60)

            vehicle = vehicle_by_trip_id.get(trip_id, {})

            item = {
                "trip_id": trip_id,
                "stop_id": stop_id,
                "stop_name": STOP_NAMES.get(stop_id, stop_id),
                "time": epoch_to_local(event_epoch),
                "epoch": event_epoch,
                "delay_min": delay_min,
                "vehicle_stop_id": vehicle.get("stop_id", ""),
                "vehicle_stop_name": vehicle.get("stop_name", ""),
                "vehicle_status": vehicle.get("status", ""),
                "vehicle_time": vehicle.get("time", ""),
                "vehicle_label": vehicle.get("label", ""),
                "lat": vehicle.get("lat", ""),
                "lon": vehicle.get("lon", ""),
            }

            if stop_id == SITGES_STOP_ID:
                sitges_trains.append(item)

            if stop_id.startswith("71") or str(vehicle.get("stop_id", "")).startswith("71"):
                nearby_updates.append(item)

    sitges_trains.sort(key=lambda x: x["epoch"] or 9999999999)
    nearby_updates.sort(key=lambda x: x["epoch"] or 9999999999)

    print("")
    print("=== R2 trains with predicted stop at Sitges ===")

    if not sitges_trains:
        print("No R2 trains currently have Sitges as stopTimeUpdate.")
    else:
        for item in sitges_trains:
            print(
                f"{item['time']} | delay={item['delay_min']} min | "
                f"trip={item['trip_id']} | "
                f"vehicle={item['vehicle_stop_name']} ({item['vehicle_stop_id']}) | "
                f"status={item['vehicle_status']} | "
                f"label={item['vehicle_label']}"
            )

    print("")
    print("=== Nearby R2 updates around Sitges corridor ===")

    if not nearby_updates:
        print("No nearby R2 updates found.")
    else:
        for item in nearby_updates[:50]:
            print(
                f"stop={item['stop_name']} ({item['stop_id']}) at {item['time']} | "
                f"delay={item['delay_min']} min | "
                f"vehicle={item['vehicle_stop_name']} ({item['vehicle_stop_id']}) | "
                f"status={item['vehicle_status']} | "
                f"trip={item['trip_id']}"
            )


if __name__ == "__main__":
    main()
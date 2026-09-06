import json
import requests
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TRIP_UPDATES_URL = "https://gtfsrt.renfe.com/trip_updates.json"
VEHICLE_POSITIONS_URL = "https://gtfsrt.renfe.com/vehicle_positions.json"

SITGES_STOP_ID = "71701"
SITGES_STOP_PREFIX = "717"
LOCAL_TZ = ZoneInfo("Europe/Madrid")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "logs"

MAX_RESULTS = 40


def get_any(d, *keys, default=None):
    for key in keys:
        if isinstance(d, dict) and key in d:
            return d[key]
    return default


def fetch_json(url, output_name):
    print(f"Downloading {url}")
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    print(f"Status: {response.status_code} | Size: {len(response.content) / 1024:.1f} KB")

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    output_path = LOG_DIR / output_name
    output_path.write_bytes(response.content)
    print(f"Saved raw response to {output_path}")

    return response.json()


def parse_epoch(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def epoch_to_local_str(epoch):
    if epoch is None:
        return "unknown"
    return datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")


def get_stop_time_epoch(stop_time_update):
    arrival = get_any(stop_time_update, "arrival", "Arrival", default={})
    departure = get_any(stop_time_update, "departure", "Departure", default={})
    departure_time = parse_epoch(get_any(departure, "time", default=None))
    arrival_time = parse_epoch(get_any(arrival, "time", default=None))
    return departure_time if departure_time is not None else arrival_time


def get_stop_time_delay(stop_time_update):
    arrival = get_any(stop_time_update, "arrival", "Arrival", default={})
    departure = get_any(stop_time_update, "departure", "Departure", default={})
    departure_delay = get_any(departure, "delay", default=None)
    arrival_delay = get_any(arrival, "delay", default=None)
    return departure_delay if departure_delay is not None else arrival_delay


def build_vehicle_index(vehicle_data):
    vehicle_by_trip_id = {}
    vehicle_stop_ids = Counter()
    vehicle_statuses = Counter()
    vehicle_route_ids = Counter()

    entities = get_any(vehicle_data, "entity", "Entity", default=[])

    for entity in entities:
        vehicle = get_any(entity, "vehicle", "Vehicle", default={})
        trip = get_any(vehicle, "trip", "Trip", default={})
        trip_id = str(get_any(trip, "tripId", "trip_id", default=""))
        route_id = str(get_any(trip, "routeId", "route_id", default=""))
        direction_id = str(get_any(trip, "directionId", "direction_id", default=""))

        stop_id = str(get_any(vehicle, "stopId", "stop_id", default=""))
        status = str(get_any(vehicle, "currentStatus", "current_status", default=""))
        timestamp = parse_epoch(get_any(vehicle, "timestamp", default=None))
        position = get_any(vehicle, "position", "Position", default={})

        if stop_id:
            vehicle_stop_ids[stop_id] += 1
        if status:
            vehicle_statuses[status] += 1
        if route_id:
            vehicle_route_ids[route_id] += 1

        if trip_id:
            vehicle_by_trip_id[trip_id] = {
                "trip_id": trip_id,
                "route_id": route_id,
                "direction_id": direction_id,
                "vehicle_stop_id": stop_id,
                "current_status": status,
                "timestamp": timestamp,
                "position": position,
            }

    return vehicle_by_trip_id, vehicle_stop_ids, vehicle_statuses, vehicle_route_ids


def summarize_trip_updates(trip_data, vehicle_by_trip_id):
    entities = get_any(trip_data, "entity", "Entity", default=[])

    route_ids = Counter()
    direction_ids = Counter()
    all_stop_ids = Counter()
    stop_prefixes = Counter()
    trip_id_samples = []
    sitges_matches = []
    nearby_stop_matches = []

    for entity in entities:
        trip_update = get_any(entity, "tripUpdate", "trip_update", default={})
        trip = get_any(trip_update, "trip", "Trip", default={})

        trip_id = str(get_any(trip, "tripId", "trip_id", default=""))
        route_id = str(get_any(trip, "routeId", "route_id", default=""))
        direction_id = str(get_any(trip, "directionId", "direction_id", default=""))
        start_date = str(get_any(trip, "startDate", "start_date", default=""))

        if route_id:
            route_ids[route_id] += 1
        if direction_id:
            direction_ids[direction_id] += 1
        if trip_id and len(trip_id_samples) < 20:
            trip_id_samples.append(trip_id)

        stop_time_updates = get_any(trip_update, "stopTimeUpdate", "stop_time_update", default=[])

        for stop_time_update in stop_time_updates:
            stop_id = str(get_any(stop_time_update, "stopId", "stop_id", default=""))
            if not stop_id:
                continue

            all_stop_ids[stop_id] += 1
            stop_prefixes[stop_id[:3]] += 1

            event_epoch = get_stop_time_epoch(stop_time_update)
            delay = get_stop_time_delay(stop_time_update)

            item = {
                "trip_id": trip_id,
                "route_id": route_id,
                "direction_id": direction_id,
                "start_date": start_date,
                "stop_id": stop_id,
                "time": epoch_to_local_str(event_epoch),
                "delay": delay,
                "vehicle": vehicle_by_trip_id.get(trip_id, {}),
            }

            if stop_id == SITGES_STOP_ID or SITGES_STOP_ID in stop_id:
                sitges_matches.append(item)

            if stop_id.startswith(SITGES_STOP_PREFIX):
                nearby_stop_matches.append(item)

    sitges_matches.sort(key=lambda x: x["time"])
    nearby_stop_matches.sort(key=lambda x: x["time"])

    print("")
    print("=== Trip updates summary ===")
    print(f"Trip update entities: {len(entities)}")
    print(f"Unique stop_ids in trip_updates: {len(all_stop_ids)}")
    print("Top route_ids:")
    for route_id, count in route_ids.most_common(30):
        print(f"  {route_id}: {count}")

    print("")
    print("Direction ids:")
    for direction_id, count in direction_ids.most_common():
        print(f"  {direction_id}: {count}")

    print("")
    print("Top stop_id prefixes:")
    for prefix, count in stop_prefixes.most_common(30):
        print(f"  {prefix}: {count}")

    print("")
    print("Top stop_ids:")
    for stop_id, count in all_stop_ids.most_common(60):
        print(f"  {stop_id}: {count}")

    print("")
    print(f"Stop IDs containing exact Sitges id '{SITGES_STOP_ID}': {len(sitges_matches)}")
    for item in sitges_matches[:MAX_RESULTS]:
        vehicle = item["vehicle"]
        print(
            f"  {item['time']} | stop={item['stop_id']} | trip={item['trip_id']} | "
            f"route={item['route_id']} | dir={item['direction_id']} | delay={item['delay']} | "
            f"vehicle_stop={vehicle.get('vehicle_stop_id', '')} | status={vehicle.get('current_status', '')}"
        )

    print("")
    print(f"Nearby stop_ids starting with '{SITGES_STOP_PREFIX}': {len(nearby_stop_matches)}")
    for item in nearby_stop_matches[:MAX_RESULTS]:
        vehicle = item["vehicle"]
        print(
            f"  {item['time']} | stop={item['stop_id']} | trip={item['trip_id']} | "
            f"route={item['route_id']} | dir={item['direction_id']} | delay={item['delay']} | "
            f"vehicle_stop={vehicle.get('vehicle_stop_id', '')} | status={vehicle.get('current_status', '')}"
        )

    print("")
    print("Trip ID samples:")
    for trip_id in trip_id_samples:
        print(f"  {trip_id}")


def summarize_vehicle_positions(vehicle_data, vehicle_stop_ids, vehicle_statuses, vehicle_route_ids):
    entities = get_any(vehicle_data, "entity", "Entity", default=[])

    print("")
    print("=== Vehicle positions summary ===")
    print(f"Vehicle entities: {len(entities)}")

    print("")
    print("Top vehicle route_ids:")
    for route_id, count in vehicle_route_ids.most_common(30):
        print(f"  {route_id}: {count}")

    print("")
    print("Vehicle statuses:")
    for status, count in vehicle_statuses.most_common():
        print(f"  {status}: {count}")

    print("")
    print("Top vehicle stop_ids:")
    for stop_id, count in vehicle_stop_ids.most_common(60):
        print(f"  {stop_id}: {count}")

    nearby_vehicle_stops = [(stop_id, count) for stop_id, count in vehicle_stop_ids.items() if stop_id.startswith(SITGES_STOP_PREFIX)]
    nearby_vehicle_stops.sort(key=lambda x: x[0])

    print("")
    print(f"Vehicle stop_ids starting with '{SITGES_STOP_PREFIX}': {len(nearby_vehicle_stops)}")
    for stop_id, count in nearby_vehicle_stops:
        print(f"  {stop_id}: {count}")


def print_raw_samples(trip_data, vehicle_data):
    trip_entities = get_any(trip_data, "entity", "Entity", default=[])
    vehicle_entities = get_any(vehicle_data, "entity", "Entity", default=[])

    print("")
    print("=== Raw trip_update sample ===")
    if trip_entities:
        print(json.dumps(trip_entities[0], indent=2, ensure_ascii=False)[:3000])
    else:
        print("No trip_update entities.")

    print("")
    print("=== Raw vehicle_position sample ===")
    if vehicle_entities:
        print(json.dumps(vehicle_entities[0], indent=2, ensure_ascii=False)[:3000])
    else:
        print("No vehicle_position entities.")


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    trip_data = fetch_json(TRIP_UPDATES_URL, f"trip_updates_{timestamp}.json")
    vehicle_data = fetch_json(VEHICLE_POSITIONS_URL, f"vehicle_positions_{timestamp}.json")

    trip_header = get_any(trip_data, "header", "Header", default={})
    vehicle_header = get_any(vehicle_data, "header", "Header", default={})

    print("")
    print("=== Feed headers ===")
    print(f"Trip updates header timestamp: {epoch_to_local_str(parse_epoch(get_any(trip_header, 'timestamp', default=None)))}")
    print(f"Vehicle positions header timestamp: {epoch_to_local_str(parse_epoch(get_any(vehicle_header, 'timestamp', default=None)))}")

    vehicle_by_trip_id, vehicle_stop_ids, vehicle_statuses, vehicle_route_ids = build_vehicle_index(vehicle_data)
    print(f"Vehicle positions indexed by trip_id: {len(vehicle_by_trip_id)}")

    summarize_trip_updates(trip_data, vehicle_by_trip_id)
    summarize_vehicle_positions(vehicle_data, vehicle_stop_ids, vehicle_statuses, vehicle_route_ids)
    print_raw_samples(trip_data, vehicle_data)


if __name__ == "__main__":
    main()
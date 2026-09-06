import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TRIP_UPDATES_URL = "https://gtfsrt.renfe.com/trip_updates.json"
VEHICLE_POSITIONS_URL = "https://gtfsrt.renfe.com/vehicle_positions.json"

LOCAL_TZ = ZoneInfo("Europe/Madrid")

SITGES_STOP_ID = "71701"

# Tabla mínima inicial. Iremos completando/corrigiendo nombres y códigos.
# position: 0.0 = Sant Vicenç / Vilanova lado izquierdo, 1.0 = Barcelona lado derecho.
STOPS = {
    # Lado Sant Vicenç / sur
    "71500": {"name": "Sant Vicenç", "position": 0.00},
    "71600": {"name": "Calafell", "position": 0.10},
    "71601": {"name": "Segur de Calafell", "position": 0.16},
    "71602": {"name": "Cunit", "position": 0.22},
    "71604": {"name": "Cubelles", "position": 0.29},
    "71700": {"name": "Vilanova", "position": 0.36},

    # Centro
    "71701": {"name": "Sitges", "position": 0.50},

    # Lado Barcelona
    "71703": {"name": "Garraf", "position": 0.58},
    "71707": {"name": "El Prat Llobregat", "position": 0.78},
    "71708": {"name": "Bellvitge-Gornal", "position": 0.84},
    "71801": {"name": "Barcelona Sants", "position": 0.90},
    "71802": {"name": "Barcelona Pg. Gràcia", "position": 0.94},
    "79400": {"name": "Barcelona Estació França", "position": 1.00},
}

# Códigos relevantes del corredor que queremos observar.
CORRIDOR_STOP_IDS = set(STOPS.keys())

TARGET_SUFFIXES = ("R2S", "R2N")


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


def epoch_to_local_time(epoch):
    if epoch is None:
        return "unknown"
    return datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone(LOCAL_TZ).strftime("%H:%M")


def get_delay_min(stop_time_update):
    arrival = get_any(stop_time_update, "arrival", default={})
    departure = get_any(stop_time_update, "departure", default={})

    delay = get_any(departure, "delay", default=None)
    if delay is None:
        delay = get_any(arrival, "delay", default=None)

    if delay is None:
        return None

    return round(int(delay) / 60)


def get_event_epoch(stop_time_update):
    arrival = get_any(stop_time_update, "arrival", default={})
    departure = get_any(stop_time_update, "departure", default={})

    dep_time = parse_epoch(get_any(departure, "time", default=None))
    arr_time = parse_epoch(get_any(arrival, "time", default=None))

    return dep_time if dep_time is not None else arr_time


def infer_direction(current_stop_id, next_stop_id):
    current_pos = stop_position(current_stop_id)
    next_pos = stop_position(next_stop_id)

    if current_pos is None or next_pos is None:
        return "unknown"

    if next_pos > current_pos:
        return "right"

    if next_pos < current_pos:
        return "left"

    return "unknown"


def stop_name(stop_id):
    return STOPS.get(stop_id, {}).get("name", stop_id)


def stop_position(stop_id):
    return STOPS.get(stop_id, {}).get("position")


def build_trip_update_index(trip_data):
    updates_by_trip_id = {}

    for entity in get_any(trip_data, "entity", default=[]):
        trip_update = get_any(entity, "tripUpdate", default={})
        trip = get_any(trip_update, "trip", default={})
        trip_id = str(get_any(trip, "tripId", default=""))

        if not trip_id.endswith(TARGET_SUFFIXES):
            continue

        stop_updates = []
        for stu in get_any(trip_update, "stopTimeUpdate", default=[]):
            stop_id = str(get_any(stu, "stopId", default=""))
            event_epoch = get_event_epoch(stu)

            stop_updates.append({
                "stop_id": stop_id,
                "stop_name": stop_name(stop_id),
                "time": epoch_to_local_time(event_epoch),
                "epoch": event_epoch,
                "delay_min": get_delay_min(stu),
            })

        updates_by_trip_id[trip_id] = stop_updates

    return updates_by_trip_id


def extract_active_r2_trains(vehicle_data, trip_updates):
    trains = []

    for entity in get_any(vehicle_data, "entity", default=[]):
        vehicle = get_any(entity, "vehicle", default={})
        trip = get_any(vehicle, "trip", default={})
        trip_id = str(get_any(trip, "tripId", default=""))

        if not trip_id.endswith(TARGET_SUFFIXES):
            continue

        vehicle_stop_id = str(get_any(vehicle, "stopId", default=""))
        vehicle_status = str(get_any(vehicle, "currentStatus", default=""))
        vehicle_ts = parse_epoch(get_any(vehicle, "timestamp", default=None))
        vehicle_info = get_any(vehicle, "vehicle", default={})
        label = str(get_any(vehicle_info, "label", default=""))

        # Nos quedamos solo con trenes del corredor cercano si conocemos su stop actual
        # o si sus stopTimeUpdates mencionan alguna estación del corredor.
        stop_updates = trip_updates.get(trip_id, [])
        mentions_corridor = any(u["stop_id"] in CORRIDOR_STOP_IDS for u in stop_updates)

        # Temporalmente no filtramos por corredor.
        # Queremos ver todos los R2S/R2N activos para descubrir stop_id reales.
        # if vehicle_stop_id not in CORRIDOR_STOP_IDS and not mentions_corridor:
        #     continue

        position = stop_position(vehicle_stop_id)

        next_update = stop_updates[0] if stop_updates else None
        sitges_update = next((u for u in stop_updates if u["stop_id"] == SITGES_STOP_ID), None)
        next_stop_id = next_update["stop_id"] if next_update else ""
        direction = infer_direction(vehicle_stop_id, next_stop_id)

        trains.append({
            "trip_id": trip_id,
            "direction": direction,
            "vehicle_stop_id": vehicle_stop_id,
            "vehicle_stop_name": stop_name(vehicle_stop_id),
            "vehicle_status": vehicle_status,
            "vehicle_time": epoch_to_local_time(vehicle_ts),
            "position": position,
            "label": label,
            "next_stop_id": next_stop_id,
            "next_stop_name": stop_name(next_stop_id),
            "next_time": next_update["time"] if next_update else "",
            "delay_min": next_update["delay_min"] if next_update else None,
            "sitges_time": sitges_update["time"] if sitges_update else None,
            "has_sitges_prediction": sitges_update is not None,
        })

    trains.sort(key=lambda x: (x["position"] is None, x["position"] if x["position"] is not None else 999))

    return trains


def render_console_board(trains):
    print("")
    print("SITGES — R2 live prototype")
    print(datetime.now().strftime("Updated %H:%M:%S"))
    print("")
    print("Line: STV/Vilanova ---- Sitges ---- BCN")
    print("")

    if not trains:
        print("No active R2S/R2N trains found in vehicle_positions right now.")
        print("This does not necessarily mean there are no scheduled trains.")
        print("It means the current vehicle feed does not expose matching active R2S/R2N vehicles.")
        return

    for train in trains:
        arrow = "[>]" if train["direction"] == "right" else "[<]" if train["direction"] == "left" else "[?]"
        pos = train["position"]
        pos_txt = f"{pos:.2f}" if pos is not None else "?"
        sitges_txt = train["sitges_time"] if train["sitges_time"] else "no Sitges prediction"

        print(
            f"{arrow} {train['trip_id']} | "
            f"vehicle={train['vehicle_stop_name']} ({train['vehicle_stop_id']}) "
            f"{train['vehicle_status']} | "
            f"line_pos={pos_txt} | "
            f"next={train['next_stop_name']} {train['next_time']} "
            f"delay={train['delay_min']} min | "
            f"Sitges={sitges_txt}"
        )

def print_r2_trip_updates(trip_data):
    print("")
    print("=== R2 trip_updates, even without vehicle position ===")

    found = 0

    for entity in get_any(trip_data, "entity", default=[]):
        trip_update = get_any(entity, "tripUpdate", default={})
        trip = get_any(trip_update, "trip", default={})
        trip_id = str(get_any(trip, "tripId", default=""))

        if "R2" not in trip_id:
            continue

        found += 1
        print("")
        print(f"trip_id={trip_id}")

        for stu in get_any(trip_update, "stopTimeUpdate", default=[]):
            stop_id = str(get_any(stu, "stopId", default=""))
            event_epoch = get_event_epoch(stu)
            delay_min = get_delay_min(stu)

            print(
                f"  stop={stop_name(stop_id)} ({stop_id}) | "
                f"time={epoch_to_local_time(event_epoch)} | "
                f"delay={delay_min} min"
            )

    if found == 0:
        print("No R2 trip_updates found right now.")

def main():
    trip_data = fetch_json(TRIP_UPDATES_URL)
    vehicle_data = fetch_json(VEHICLE_POSITIONS_URL)

    trip_entities = get_any(trip_data, "entity", default=[])
    vehicle_entities = get_any(vehicle_data, "entity", default=[])

    print("")
    print("=== Feed diagnostics ===")
    print(f"trip_update entities: {len(trip_entities)}")
    print(f"vehicle_position entities: {len(vehicle_entities)}")

    trip_ids_from_updates = []
    trip_ids_from_vehicles = []

    for entity in trip_entities:
        trip_update = get_any(entity, "tripUpdate", default={})
        trip = get_any(trip_update, "trip", default={})
        trip_id = str(get_any(trip, "tripId", default=""))
        if trip_id:
            trip_ids_from_updates.append(trip_id)

    for entity in vehicle_entities:
        vehicle = get_any(entity, "vehicle", default={})
        trip = get_any(vehicle, "trip", default={})
        trip_id = str(get_any(trip, "tripId", default=""))
        if trip_id:
            trip_ids_from_vehicles.append(trip_id)

    r2_updates = [t for t in trip_ids_from_updates if "R2" in t]
    r2_vehicles = [t for t in trip_ids_from_vehicles if "R2" in t]

    target_updates = [t for t in trip_ids_from_updates if t.endswith(TARGET_SUFFIXES)]
    target_vehicles = [t for t in trip_ids_from_vehicles if t.endswith(TARGET_SUFFIXES)]

    print(f"trip_updates with 'R2' in trip_id: {len(r2_updates)}")
    print(f"vehicle_positions with 'R2' in trip_id: {len(r2_vehicles)}")
    print(f"trip_updates ending with R2S/R2N: {len(target_updates)}")
    print(f"vehicle_positions ending with R2S/R2N: {len(target_vehicles)}")

    print("")
    print("Sample R2 trip_updates:")
    for trip_id in r2_updates[:20]:
        print(f"  {trip_id}")

    print("")
    print("Sample R2 vehicle_positions:")
    for trip_id in r2_vehicles[:20]:
        print(f"  {trip_id}")

    print_r2_trip_updates(trip_data)
    trip_updates = build_trip_update_index(trip_data)
    trains = extract_active_r2_trains(vehicle_data, trip_updates)
    render_console_board(trains)


if __name__ == "__main__":
    main()
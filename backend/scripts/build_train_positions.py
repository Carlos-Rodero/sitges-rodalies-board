import json
import requests
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from r2s_line import (
    STOP_ID_TO_STATION,
    estimate_line_index,
    infer_direction,
    station_code,
    station_name,
    train_icon,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "logs"

TRIP_UPDATES_URL = "https://gtfsrt.renfe.com/trip_updates.json"
VEHICLE_POSITIONS_URL = "https://gtfsrt.renfe.com/vehicle_positions.json"

TARGET_SUFFIXES = ("R2S", "R2N")
LOCAL_TZ = ZoneInfo("Europe/Madrid")


def now_local():
    return datetime.now(LOCAL_TZ).strftime("%H:%M:%S")


def download_json(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def get_trip_id_from_vehicle(entity):
    vehicle = entity.get("vehicle", {})
    trip = vehicle.get("trip", {})
    return trip.get("tripId", "")


def get_trip_id_from_update(entity):
    trip_update = entity.get("tripUpdate", {})
    trip = trip_update.get("trip", {})
    return trip.get("tripId", "")


def build_trip_update_index(trip_data):
    updates = {}

    for entity in trip_data.get("entity", []):
        trip_update = entity.get("tripUpdate", {})
        trip_id = get_trip_id_from_update(entity)

        if not trip_id:
            continue

        stop_updates = trip_update.get("stopTimeUpdate", [])

        first_stop_id = None
        first_time = None
        delay = None

        if stop_updates:
            first = stop_updates[0]
            first_stop_id = str(first.get("stopId", ""))

            event = first.get("arrival") or first.get("departure") or {}
            first_time = event.get("time")
            delay = event.get("delay")

        updates[trip_id] = {
            "next_stop_id": first_stop_id,
            "next_time": first_time,
            "delay_seconds": delay,
        }

    return updates


def epoch_to_local_hhmm(epoch_text):
    if not epoch_text:
        return ""

    try:
        epoch = int(epoch_text)
    except ValueError:
        return ""

    return datetime.fromtimestamp(epoch, LOCAL_TZ).strftime("%H:%M")


def build_train_positions(trip_data, vehicle_data):
    trip_updates = build_trip_update_index(trip_data)

    trains = []

    for entity in vehicle_data.get("entity", []):
        trip_id = get_trip_id_from_vehicle(entity)

        if not trip_id.endswith(TARGET_SUFFIXES):
            continue

        vehicle = entity.get("vehicle", {})
        position = vehicle.get("position", {})

        current_stop_id = str(vehicle.get("stopId", ""))
        status = vehicle.get("currentStatus", "")
        timestamp = vehicle.get("timestamp", "")

        update = trip_updates.get(trip_id, {})
        next_stop_id = update.get("next_stop_id")

        # Keep only trains whose vehicle stop is on the R2S corridor we draw.
        # If only next_stop_id is on the corridor but vehicle_stop_id is outside,
        # the position is too uncertain for this first map.
        if current_stop_id not in STOP_ID_TO_STATION:
            continue

        direction = infer_direction(current_stop_id, next_stop_id)
        line_index = estimate_line_index(current_stop_id, next_stop_id, status)

        train = {
            "trip_id": trip_id,
            "icon": train_icon(direction),
            "direction": direction,
            "line_index": line_index,
            "status": status,
            "current_stop_id": current_stop_id,
            "current_stop_code": station_code(current_stop_id),
            "current_stop_name": station_name(current_stop_id),
            "next_stop_id": next_stop_id,
            "next_stop_code": station_code(next_stop_id),
            "next_stop_name": station_name(next_stop_id),
            "next_time": epoch_to_local_hhmm(update.get("next_time")),
            "delay_min": (
                int(update["delay_seconds"] / 60)
                if update.get("delay_seconds") is not None
                else None
            ),
            "lat": position.get("latitude"),
            "lon": position.get("longitude"),
            "vehicle_timestamp": epoch_to_local_hhmm(timestamp),
        }

        trains.append(train)

    sitges_index = 6
    trains.sort(
        key=lambda item: (
            999 if item["line_index"] is None else abs(item["line_index"] - sitges_index),
            item["trip_id"],
        )
    )

    return trains


def print_train_positions(trains):
    print("")
    print(f"R2 train positions | updated {now_local()}")
    print("")

    if not trains:
        print("No R2 trains found on the drawn R2S corridor.")
        return

    for train in trains:
        idx = train["line_index"]
        idx_text = "?" if idx is None else f"{idx:.2f}"

        print(
            f"{train['icon']} {train['trip_id']} | "
            f"{train['status']} | "
            f"vehicle_stop={train['current_stop_code']} | "
            f"next_update={train['next_stop_code']} | "
            f"pos={idx_text} | "
            f"next={train['next_time']} | "
            f"delay={train['delay_min']} min"
        )


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    trip_data = download_json(TRIP_UPDATES_URL)
    vehicle_data = download_json(VEHICLE_POSITIONS_URL)

    trains = build_train_positions(trip_data, vehicle_data)

    output_path = LOG_DIR / "train_positions_latest.json"
    output_path.write_text(
        json.dumps(trains, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print_train_positions(trains)

    print("")
    print(f"Saved train positions to: {output_path}")


if __name__ == "__main__":
    main()
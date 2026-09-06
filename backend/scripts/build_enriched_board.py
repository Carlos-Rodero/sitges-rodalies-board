import copy
import json
from pathlib import Path

from match_board_train_candidates import (
    departure_to_minutes,
    estimate_sitges_eta_minutes,
    time_diff_minutes,
    minutes_to_hhmm,
    is_candidate_physically_plausible,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "logs"

BOARD_JSON = LOG_DIR / "board_latest.json"
TRAIN_POSITIONS_JSON = LOG_DIR / "train_positions_latest.json"
OUTPUT_JSON = LOG_DIR / "board_enriched_latest.json"

HIGH_CONFIDENCE_DIFF_MIN = 4
MEDIUM_CONFIDENCE_DIFF_MIN = 8


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def describe_train_location(train):
    code = train.get("current_stop_code")
    next_code = train.get("next_stop_code")
    status = train.get("status")
    direction = train.get("direction")

    if not code:
        return "posición desconocida"

    # Special user-facing wording for terminal/origin stations.
    # A train towards Barcelona at SVC is effectively waiting/starting
    # at the south terminal of the corridor, even if Renfe says INCOMING_AT.
    if direction == "to_barcelona" and code == "SVC":
        return "en origen SVC"

    # A train towards the south at EDF is effectively at the Barcelona-side
    # origin of the corridor.
    if direction == "to_south" and code == "EDF":
        return "en origen EDF"

    if status == "STOPPED_AT":
        return f"en {code}"

    if status == "INCOMING_AT":
        return f"llegando a {code}"

    if status == "IN_TRANSIT_TO":
        if next_code:
            return f"entre {code} y {next_code}"
        return f"saliendo de {code}"

    return f"cerca de {code}"


def find_best_match(departure, direction, trains, board_updated, used_trip_ids):
    dep_minutes = departure_to_minutes(departure, board_updated)

    if dep_minutes is None:
        return None

    candidates = []

    for train in trains:
        trip_id = train.get("trip_id")

        if trip_id in used_trip_ids:
            continue

        if not is_candidate_physically_plausible(train, direction):
            continue

        eta = estimate_sitges_eta_minutes(train)
        diff = time_diff_minutes(dep_minutes, eta)

        if diff is None:
            continue

        score = 100 - diff

        line_index = train.get("line_index")
        if line_index is not None:
            score -= abs(float(line_index) - 6.0) * 0.2

        candidates.append((score, diff, eta, train))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    _score, diff, eta, train = candidates[0]

    if diff > MEDIUM_CONFIDENCE_DIFF_MIN:
        return None

    if diff <= HIGH_CONFIDENCE_DIFF_MIN:
        confidence = "high"
        position_status = "visible"
    else:
        confidence = "medium"
        position_status = "estimated"

    return {
        "position_status": position_status,
        "match_confidence": confidence,
        "matched_trip_id": train.get("trip_id"),
        "train_icon": train.get("icon"),
        "train_location": describe_train_location(train),
        "train_current_stop": train.get("current_stop_code"),
        "train_next_stop": train.get("next_stop_code"),
        "train_status": train.get("status"),
        "train_line_index": train.get("line_index"),
        "train_eta_sitges": minutes_to_hhmm(eta),
        "match_time_diff_min": diff,
        "train_delay_min": train.get("delay_min"),
    }


def enrich_departures(departures, direction, trains, board_updated):
    enriched = []
    used_trip_ids = set()

    for departure in departures:
        item = copy.deepcopy(departure)
        match = find_best_match(
            item,
            direction,
            trains,
            board_updated,
            used_trip_ids,
        )

        if match:
            item.update(match)
            used_trip_ids.add(match["matched_trip_id"])
        else:
            item.update({
                "position_status": "not_visible_yet",
                "match_confidence": "none",
                "matched_trip_id": None,
                "train_location": "sin posición",
                "train_eta_sitges": None,
                "match_time_diff_min": None,
                "train_delay_min": None,
            })

        enriched.append(item)

    return enriched


def main():
    board = load_json(BOARD_JSON)
    trains = load_json(TRAIN_POSITIONS_JSON)

    enriched = copy.deepcopy(board)
    board_updated = board.get("updated", "")

    enriched["to_barcelona"] = enrich_departures(
        board.get("to_barcelona", []),
        "to_barcelona",
        trains,
        board_updated,
    )

    enriched["to_south"] = enrich_departures(
        board.get("to_south", []),
        "to_south",
        trains,
        board_updated,
    )

    OUTPUT_JSON.write_text(
        json.dumps(enriched, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Saved enriched board to: {OUTPUT_JSON}")
    print("")

    print("→ Barcelona")
    for item in enriched["to_barcelona"][:3]:
        print(
            f"{item['time']:>5} | {item['destination']:<14} | "
            f"{item['position_status']:<15} | "
            f"{item['train_location']} | "
            f"conf={item['match_confidence']}"
        )

    print("")
    print("← Vilanova / Sant Vicenç")
    for item in enriched["to_south"][:3]:
        print(
            f"{item['time']:>5} | {item['destination']:<14} | "
            f"{item['position_status']:<15} | "
            f"{item['train_location']} | "
            f"conf={item['match_confidence']}"
        )


if __name__ == "__main__":
    main()
import json
from pathlib import Path

from r2s_line import station_time_offset_from_sitges

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "logs"

BOARD_JSON = LOG_DIR / "board_latest.json"
TRAIN_POSITIONS_JSON = LOG_DIR / "train_positions_latest.json"

MAX_CANDIDATES = 4
MATCH_THRESHOLD_MIN = 8


def parse_hhmm_to_minutes(text):
    text = str(text or "").strip().lower()

    if "min" in text:
        return None

    try:
        hour, minute = map(int, text.split(":"))
    except ValueError:
        return None

    return hour * 60 + minute

def departure_to_minutes(departure, board_updated):
    """
    Converts an Adif departure into absolute minutes of day.

    Supports:
    - "14:03"
    - "3 min", using departure["minutes_until"] + board updated time
    """
    time_text = str(departure.get("time", "")).strip().lower()

    if "min" in time_text:
        board_minutes = parse_hhmm_to_minutes(board_updated)
        minutes_until = departure.get("minutes_until")

        if board_minutes is None or minutes_until is None:
            return None

        return (board_minutes + int(minutes_until)) % (24 * 60)

    return parse_hhmm_to_minutes(time_text)

def minutes_to_hhmm(minutes):
    minutes = minutes % (24 * 60)
    hour = minutes // 60
    minute = minutes % 60
    return f"{hour:02d}:{minute:02d}"


def time_diff_minutes(a, b):
    if a is None or b is None:
        return None

    diff = abs(a - b)
    return min(diff, 24 * 60 - diff)


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def estimate_sitges_eta_minutes(train):
    """
    Estimate when this train will pass Sitges.

    Uses Renfe next_time at next_stop_code and approximate station offsets
    relative to Sitges.

    Example:
    southbound train with next_stop=GAV at 13:35.
    GAV is about +18 min from Sitges.
    Therefore estimated Sitges pass is about 13:35 + 18 = 13:53
    when moving towards the south.

    Barcelona-bound train with next_stop=SIT at 13:39.
    Estimated Sitges pass is exactly 13:39.
    """
    direction = train.get("direction")
    next_time_min = parse_hhmm_to_minutes(train.get("next_time"))
    next_code = train.get("next_stop_code")
    current_code = train.get("current_stop_code")
    status = train.get("status")

    if next_time_min is None:
        return None

    # Best case: Renfe explicitly reports Sitges as next update.
    if next_code == "SIT":
        return next_time_min

    # If train is currently stopped at Sitges, use next_time minus travel time
    # from Sitges to next stop.
    if current_code == "SIT" and status == "STOPPED_AT":
        next_offset = station_time_offset_from_sitges(next_code)
        if next_offset is not None:
            return next_time_min - abs(next_offset)
        return next_time_min

    # General case.
    next_offset = station_time_offset_from_sitges(next_code)
    if next_offset is None:
        return None

    if direction == "to_barcelona":
        # Train moves from negative offsets to positive offsets.
        # If next stop is after Sitges, then it has already passed or is
        # about to pass Sitges before reaching that next stop.
        return next_time_min - next_offset

    if direction == "to_south":
        # Train moves from positive offsets to negative offsets.
        # If next stop is after Sitges on the Barcelona side, it will reach
        # Sitges after that next stop.
        return next_time_min + next_offset

    return None


def is_candidate_physically_plausible(train, departure_direction):
    """
    Avoid matching trains that already passed Sitges in the wrong direction.
    """
    direction = train.get("direction")
    line_index = train.get("line_index")

    if direction != departure_direction:
        return False

    if line_index is None:
        return False

    line_index = float(line_index)
    sitges_index = 6.0

    if departure_direction == "to_barcelona":
        # Useful candidates are at/before Sitges, or very close after Sitges
        # if the train has just departed.
        return line_index <= sitges_index + 0.7

    if departure_direction == "to_south":
        # Useful candidates are at/after Sitges, or very close before Sitges
        # if the train has just departed.
        return line_index >= sitges_index - 0.7

    return False


def format_train_candidate(train, estimated_eta, diff):
    pos = train.get("line_index")
    pos_text = "?" if pos is None else f"{float(pos):.2f}"

    delay = train.get("delay_min")
    delay_text = "" if delay is None else f", delay {delay:+d} min"

    eta_text = "?" if estimated_eta is None else minutes_to_hhmm(estimated_eta)
    diff_text = "?" if diff is None else f"{diff} min"

    return (
        f"{train.get('icon')} {train.get('trip_id')} | "
        f"{train.get('current_stop_code')} → {train.get('next_stop_code')} | "
        f"{train.get('status')} | pos={pos_text} | "
        f"next={train.get('next_time')} | "
        f"ETA Sitges={eta_text} | diff={diff_text}{delay_text}"
    )


def print_matches_for_group(title, departures, direction, trains, board_updated):
    print("")
    print(title)
    print("-" * len(title))

    used_trip_ids = set()

    for departure in departures:
        dep_time = departure.get("time")
        dep_minutes = departure_to_minutes(departure, board_updated)

        scored = []

        for train in trains:
            if train.get("trip_id") in used_trip_ids:
                continue

            if not is_candidate_physically_plausible(train, direction):
                continue

            estimated_eta = estimate_sitges_eta_minutes(train)
            diff = time_diff_minutes(dep_minutes, estimated_eta)

            if diff is None:
                continue

            score = 100 - diff

            # Prefer trains closer to Sitges if time difference is similar.
            line_index = train.get("line_index")
            if line_index is not None:
                score -= abs(float(line_index) - 6.0) * 0.2

            scored.append((score, diff, estimated_eta, train))

        scored.sort(key=lambda item: item[0], reverse=True)

        print("")
        print(
            f"{dep_time} | {departure.get('destination')} | "
            f"{departure.get('line')} | vía {departure.get('platform')}"
        )

        if not scored:
            print("  no candidate")
            continue

        best_score, best_diff, best_eta, best_train = scored[0]

        if best_diff <= MATCH_THRESHOLD_MIN:
            print(f"  BEST MATCH: {format_train_candidate(best_train, best_eta, best_diff)}")
            used_trip_ids.add(best_train.get("trip_id"))
        else:
            print("  no confident match")
            print(f"  closest: {format_train_candidate(best_train, best_eta, best_diff)}")

        for _score, diff, eta, train in scored[1:MAX_CANDIDATES]:
            print(f"  candidate: {format_train_candidate(train, eta, diff)}")


def main():
    board = load_json(BOARD_JSON)
    trains = load_json(TRAIN_POSITIONS_JSON)

    print(f"Board updated: {board.get('updated')}")
    print(f"Train positions: {len(trains)}")

    board_updated = board.get("updated")

    print_matches_for_group(
        "→ Barcelona candidates",
        board.get("to_barcelona", [])[:5],
        "to_barcelona",
        trains,
        board_updated,
    )

    print_matches_for_group(
        "← Vilanova / Sant Vicenç candidates",
        board.get("to_south", [])[:5],
        "to_south",
        trains,
        board_updated,
    )


if __name__ == "__main__":
    main()
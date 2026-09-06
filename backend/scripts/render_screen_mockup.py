import json
import textwrap
from pathlib import Path
from r2s_line import R2S_STATIONS

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "logs"

ENRICHED_BOARD_JSON = LOG_DIR / "board_enriched_latest.json"
BOARD_JSON = LOG_DIR / "board_latest.json"

SCREEN_WIDTH = 104
MAX_TRAINS_PER_DIRECTION = 3
MAX_ALERT_LINES = 2

TRAIN_POSITIONS_JSON = LOG_DIR / "train_positions_latest.json"


def short_text(text, max_len):
    text = str(text or "")
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def load_board():
    if ENRICHED_BOARD_JSON.exists():
        path = ENRICHED_BOARD_JSON
    elif BOARD_JSON.exists():
        path = BOARD_JSON
    else:
        raise FileNotFoundError(
            f"No board JSON found. Run build_board_live.py first."
        )

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_train_positions():
    if not TRAIN_POSITIONS_JSON.exists():
        return []

    with TRAIN_POSITIONS_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)

def get_sitges_station_index():
    return next(
        i for i, station in enumerate(R2S_STATIONS)
        if station["code"] == "SIT"
    )


def get_icon_start(line_index, icon, line_length):
    if line_index is None:
        return None

    try:
        line_index = float(line_index)
    except (TypeError, ValueError):
        return None

    # Each station step occupies 6 characters:
    # " ○ " + "───" = 6
    start = round(line_index * 6)

    # Keep icon inside the line
    start = max(0, min(start, line_length - len(icon)))
    return start


def can_place_icon(line_chars, start, icon):
    """
    Avoid overlapping icons. We also leave 1 character of margin.
    """
    if start is None:
        return False

    check_start = max(0, start - 1)
    check_end = min(len(line_chars), start + len(icon) + 1)

    for pos in range(check_start, check_end):
        if line_chars[pos] != " ":
            return False

    return True


def place_icon(line_chars, start, icon):
    for j, char in enumerate(icon):
        pos = start + j
        if 0 <= pos < len(line_chars):
            line_chars[pos] = char


def build_icon_lanes(trains, direction, marker_line_length, max_lanes=3):
    """
    Build several text rows for train icons so nearby trains do not overwrite
    each other.
    """
    selected = [
        train for train in trains
        if train.get("direction") == direction
    ]

    selected.sort(
        key=lambda train: (
            999 if train.get("line_index") is None else float(train.get("line_index")),
            train.get("trip_id", ""),
        )
    )

    lanes = [
        [" "] * marker_line_length
        for _ in range(max_lanes)
    ]

    hidden_count = 0

    for train in selected:
        icon = train.get("icon", "[?]")
        start = get_icon_start(train.get("line_index"), icon, marker_line_length)

        placed = False
        for lane in lanes:
            if can_place_icon(lane, start, icon):
                place_icon(lane, start, icon)
                placed = True
                break

        if not placed:
            hidden_count += 1

    lane_strings = [
        "".join(lane).rstrip()
        for lane in lanes
        if "".join(lane).strip()
    ]

    return lane_strings, hidden_count


def build_unknown_icon_lanes(trains, marker_line_length, max_lanes=1):
    selected = [
        train for train in trains
        if train.get("direction") not in ["to_barcelona", "to_south"]
    ]

    selected.sort(
        key=lambda train: (
            999 if train.get("line_index") is None else float(train.get("line_index")),
            train.get("trip_id", ""),
        )
    )

    lanes = [
        [" "] * marker_line_length
        for _ in range(max_lanes)
    ]

    hidden_count = 0

    for train in selected:
        icon = train.get("icon", "[?]")
        start = get_icon_start(train.get("line_index"), icon, marker_line_length)

        placed = False
        for lane in lanes:
            if can_place_icon(lane, start, icon):
                place_icon(lane, start, icon)
                placed = True
                break

        if not placed:
            hidden_count += 1

    lane_strings = [
        "".join(lane).rstrip()
        for lane in lanes
        if "".join(lane).strip()
    ]

    return lane_strings, hidden_count


def build_imminent_departure_icons(board):
    """
    Fallback: if Renfe train positions are unavailable, show only imminent
    departures from Sitges based on Adif.
    """
    sit_index = get_sitges_station_index()

    trains = []

    for item in board.get("to_barcelona", []):
        minutes_until = item.get("minutes_until")
        if minutes_until is not None and minutes_until <= 15:
            trains.append({
                "icon": "[>]",
                "direction": "to_barcelona",
                "line_index": float(sit_index),
                "trip_id": "adif_to_barcelona",
            })
            break

    for item in board.get("to_south", []):
        minutes_until = item.get("minutes_until")
        if minutes_until is not None and minutes_until <= 15:
            trains.append({
                "icon": "[<]",
                "direction": "to_south",
                "line_index": float(sit_index),
                "trip_id": "adif_to_south",
            })
            break

    return trains


def format_line_map(board, train_positions):
    marker_parts = []
    label_parts = []

    for station in R2S_STATIONS:
        code = station["code"]
        marker = "◎" if code == "SIT" else "○"
        marker_parts.append(f"{marker:^3}")
        label_parts.append(f"{code:^3}")

    marker_line = "───".join(marker_parts)
    label_line = "   ".join(label_parts)

    if train_positions:
        trains = train_positions
        subtitle = "R2S Sant Vicenç → Sitges → Barcelona | posiciones Renfe"
    else:
        trains = build_imminent_departure_icons(board)
        subtitle = "R2S Sant Vicenç → Sitges → Barcelona | salidas Adif"

    line_length = len(marker_line)

    bcn_lanes, bcn_hidden = build_icon_lanes(
        trains,
        direction="to_barcelona",
        marker_line_length=line_length,
        max_lanes=3,
    )

    south_lanes, south_hidden = build_icon_lanes(
        trains,
        direction="to_south",
        marker_line_length=line_length,
        max_lanes=3,
    )

    unknown_lanes, unknown_hidden = build_unknown_icon_lanes(
        trains,
        marker_line_length=line_length,
        max_lanes=1,
    )

    lines = [subtitle]

    for lane in bcn_lanes:
        lines.append(lane)

    for lane in unknown_lanes:
        lines.append(f"{lane}   ?")

    lines.append(marker_line)
    lines.append(label_line)

    for lane in south_lanes:
        lines.append(lane)

    hidden_total = bcn_hidden + south_hidden + unknown_hidden
    if hidden_total:
        lines.append(f"{hidden_total} trenes no mostrados por solape")

    lines.append("[>] tren hacia Barcelona   [<] tren hacia Vilanova/Sant Vicenç")

    return lines

def format_position_status(item):
    position_status = item.get("position_status", "")
    train_location = item.get("train_location", "")
    confidence = item.get("match_confidence", "")

    if not position_status:
        return ""

    if position_status == "not_visible_yet":
        return "sin posición"

    if not train_location:
        return ""

    if confidence == "medium":
        return f"estim. {train_location}"

    return train_location

def format_observation_short(item):
    observation = str(item.get("observation", "")).lower()

    if not observation:
        return ""

    if "platja de castelldefels" in observation:
        return "sin PCF"

    return "aviso"

def format_train_row(item):
    time = short_text(item.get("time", ""), 5)
    destination = short_text(item.get("destination", ""), 14)
    line = short_text(item.get("line", ""), 4)
    platform = short_text(item.get("platform", ""), 2)
    leave_home = short_text(item.get("leave_home", ""), 12)
    position = short_text(format_position_status(item), 18)
    observation = short_text(format_observation_short(item), 8)

    urgency = item.get("urgency", "")
    if urgency == "now":
        marker = "!"
    elif urgency == "soon":
        marker = "·"
    else:
        marker = " "

    row = (
        f"{marker} {time:<5} {destination:<14} {line:<4} "
        f"v{platform:<2} {leave_home:<12}"
    )

    if position:
        row += f" {position}"

    if observation:
        row += f" {observation}"

    return row


def format_section(title, items):
    lines = []
    lines.append(title)

    if not items:
        lines.append("  Sin próximas salidas")
        return lines

    for item in items[:MAX_TRAINS_PER_DIRECTION]:
        lines.append(format_train_row(item))

    return lines


def format_alerts(alerts):
    if not alerts:
        return []

    lines = []
    lines.append("Avisos:")

    wrapped = []
    for alert in alerts:
        clean = str(alert).strip()
        if not clean:
            continue
        wrapped.extend(textwrap.wrap(clean, width=SCREEN_WIDTH - 2))

    for line in wrapped[:MAX_ALERT_LINES]:
        lines.append(f"- {line}")

    return lines


def render_screen(board, train_positions):
    updated = board.get("updated", "")
    date = board.get("date", "")

    lines = []

    header = "SITGES R2"
    if updated:
        header = f"{header:<{SCREEN_WIDTH - len(updated)}}{updated}"

    lines.append(header[:SCREEN_WIDTH])

    if date:
        lines.append(short_text(date, SCREEN_WIDTH))

    lines.append("")

    lines.extend(format_line_map(board, train_positions))

    lines.append("")
    lines.extend(format_section("→ Barcelona", board.get("to_barcelona", [])))

    lines.append("")
    lines.extend(format_section("← Vilanova / Sant Vicenç", board.get("to_south", [])))

    # alert_lines = format_alerts(board.get("alerts", []))
    # if alert_lines:
    #     lines.append("")
    #     lines.extend(alert_lines)

    return "\n".join(lines)


def main():
    board = load_board()
    train_positions = load_train_positions()
    screen_text = render_screen(board, train_positions)

    print("")
    print("=" * SCREEN_WIDTH)
    print(screen_text)
    print("=" * SCREEN_WIDTH)

    output_path = LOG_DIR / "screen_mockup.txt"
    output_path.write_text(screen_text, encoding="utf-8")

    print("")
    print(f"Saved screen mockup to: {output_path}")


if __name__ == "__main__":
    main()
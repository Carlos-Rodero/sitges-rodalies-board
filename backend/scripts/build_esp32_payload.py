import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "logs"
PUBLIC_DIR = PROJECT_ROOT / "docs"

ENRICHED_BOARD_JSON = LOG_DIR / "board_enriched_latest.json"
TRAIN_POSITIONS_JSON = LOG_DIR / "train_positions_latest.json"

OUTPUT_JSON = LOG_DIR / "esp32_payload_latest.json"
PUBLIC_OUTPUT_JSON = PUBLIC_DIR / "esp32_payload_latest.json"

MAX_ROWS_PER_DIRECTION = 3
MAX_TRAINS = 12


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def short_text(text, max_len):
    text = str(text or "")
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def compact_location(item):
    status = item.get("position_status", "")
    location = item.get("train_location", "")

    if status == "not_visible_yet":
        return "sin pos"

    if not location:
        return ""

    replacements = {
        "sin posición": "sin pos",
        "en origen ": "orig ",
        "llegando a ": "llega ",
        "entre ": "",
        " y ": "-",
    }

    text = location
    for old, new in replacements.items():
        text = text.replace(old, new)

    return short_text(text, 12)


def compact_time(text):
    text = str(text or "").strip()

    if not text:
        return ""

    if "min" in text:
        number = text.split()[0]
        return f"{number}m"

    return short_text(text, 5)


def compact_leave_home(text):
    text = str(text or "").strip()

    if not text:
        return ""

    if text == "salir ya":
        return "ya"

    if text.startswith("salir "):
        return text.replace("salir ", "")

    return short_text(text, 5)


def is_valid_departure(item):
    time = str(item.get("time", "")).strip()
    leave_home = str(item.get("leave_home", "")).strip()

    if not time and not leave_home:
        return False

    return True


def compact_departure(item):
    return [
        compact_time(item.get("time", "")),
        short_text(item.get("destination", ""), 13),
        f"v{item.get('platform', '')}",
        compact_leave_home(item.get("leave_home", "")),
        compact_location(item),
    ]


def compact_train(train):
    icon = train.get("icon", "[?]")

    if icon == "[>]":
        direction = ">"
    elif icon == "[<]":
        direction = "<"
    else:
        direction = "?"

    return [
        round(float(train.get("line_index", 0)), 2),
        direction,
    ]


def build_payload(board, trains):
    payload = {
        "station": board.get("station", "Sitges"),
        "updated": board.get("updated", ""),
        "date": board.get("date", ""),
        "line": "R2S",
        "stations": [
            "SVC", "CAL", "SEG", "CUN", "CUB", "VNG", "SIT",
            "GAR", "PCF", "CDF", "GAV", "VLD", "ELP", "BEL",
            "SAN", "PGR", "EDF"
        ],
        "sitges_index": 6,
        "to_bcn": [
            compact_departure(item)
            for item in board.get("to_barcelona", [])
            if is_valid_departure(item)
        ][:MAX_ROWS_PER_DIRECTION],
        "to_south": [
            compact_departure(item)
            for item in board.get("to_south", [])
            if is_valid_departure(item)
        ][:MAX_ROWS_PER_DIRECTION],
        "trains": [
            compact_train(train)
            for train in trains[:MAX_TRAINS]
            if train.get("line_index") is not None
            and train.get("icon") in ("[>]", "[<]")
        ],
    }

    return payload


def main():
    if not ENRICHED_BOARD_JSON.exists():
        raise FileNotFoundError(
            f"{ENRICHED_BOARD_JSON} not found. Run build_enriched_board.py first."
        )

    if not TRAIN_POSITIONS_JSON.exists():
        raise FileNotFoundError(
            f"{TRAIN_POSITIONS_JSON} not found. Run build_train_positions.py first."
        )

    board = load_json(ENRICHED_BOARD_JSON)
    trains = load_json(TRAIN_POSITIONS_JSON)

    payload = build_payload(board, trains)

    # Local development copy
    OUTPUT_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    # Public GitHub Pages copy
    PUBLIC_DIR.mkdir(exist_ok=True)

    PUBLIC_OUTPUT_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    compact_size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    print(f"Saved ESP32 payload to: {OUTPUT_JSON}")
    print(f"Saved public payload to: {PUBLIC_OUTPUT_JSON}")
    print(f"Payload size: {compact_size} bytes")
    print("")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
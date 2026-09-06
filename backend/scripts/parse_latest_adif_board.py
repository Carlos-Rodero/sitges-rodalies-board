import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "logs"

MAX_PER_DIRECTION = 5


def find_latest_adif_json():
    files = sorted(LOG_DIR.glob("adif_browser_endpoint_*.json"))
    if not files:
        raise FileNotFoundError("No adif_browser_endpoint_*.json files found in logs/")
    return files[-1]


def classify_direction(destination):
    destination_lower = destination.lower()

    south_keywords = [
        "vilanova",
        "sant vicenç",
        "st. vicenç",
        "calders",
        "cubelles",
        "cunit",
        "calafell",
    ]

    barcelona_keywords = [
        "barcelona",
        "estació de frança",
        "passeig de gràcia",
        "sants",
        "granollers",
        "maçanet",
        "aeroport",
    ]

    if any(keyword in destination_lower for keyword in south_keywords):
        return "to_south"

    if any(keyword in destination_lower for keyword in barcelona_keywords):
        return "to_barcelona"

    return "unknown"


def simplify_observation(observation):
    if not observation:
        return ""

    # Adif sometimes gives bilingual duplicated text separated by "/"
    parts = [part.strip() for part in observation.split("/") if part.strip()]
    if not parts:
        return ""

    return parts[0]


def build_board(adif_data):
    board = {
        "station": "Sitges",
        "source": "adif",
        "date": adif_data.get("date", ""),
        "updated": adif_data.get("time", datetime.now().strftime("%H:%M")),
        "line": {
            "left_label": "STV",
            "center_label": "Sitges",
            "right_label": "BCN",
            "trains": []
        },
        "to_barcelona": [],
        "to_south": [],
        "unknown": [],
        "alerts": []
    }

    horarios = adif_data.get("horarios", [])

    for row in horarios:
        destination = row.get("estacion", "")
        direction = classify_direction(destination)

        item = {
            "time": row.get("hora", ""),
            "destination": destination,
            "line": row.get("tren", ""),
            "platform": row.get("via", ""),
            "observation": simplify_observation(row.get("observation", "")),
            "immediate": row.get("immediate", False),
            "accessible": row.get("accesible", False),
        }

        if direction == "to_barcelona":
            if len(board["to_barcelona"]) < MAX_PER_DIRECTION:
                board["to_barcelona"].append(item)

        elif direction == "to_south":
            if len(board["to_south"]) < MAX_PER_DIRECTION:
                board["to_south"].append(item)

        else:
            board["unknown"].append(item)

    # Basic alert summary from observations
    observations = []
    for group_name in ["to_barcelona", "to_south", "unknown"]:
        for item in board[group_name]:
            if item["observation"]:
                observations.append(item["observation"])

    # Keep unique alerts, short list
    seen = set()
    for obs in observations:
        if obs not in seen:
            board["alerts"].append(obs)
            seen.add(obs)

    board["alerts"] = board["alerts"][:3]

    return board


def print_board(board):
    print("")
    print(f"SITGES — Adif board | updated {board['updated']}")
    print("")

    print("→ Barcelona")
    if not board["to_barcelona"]:
        print("  No departures found.")
    for item in board["to_barcelona"]:
        obs = f" | {item['observation']}" if item["observation"] else ""
        print(
            f"  {item['time']:>6} | {item['destination']} | "
            f"{item['line']} | via {item['platform']}{obs}"
        )

    print("")
    print("← Vilanova / Sant Vicenç")
    if not board["to_south"]:
        print("  No departures found.")
    for item in board["to_south"]:
        obs = f" | {item['observation']}" if item["observation"] else ""
        print(
            f"  {item['time']:>6} | {item['destination']} | "
            f"{item['line']} | via {item['platform']}{obs}"
        )

    if board["unknown"]:
        print("")
        print("Unknown direction")
        for item in board["unknown"][:10]:
            print(
                f"  {item['time']:>6} | {item['destination']} | "
                f"{item['line']} | via {item['platform']}"
            )

    if board["alerts"]:
        print("")
        print("Alerts / observations")
        for alert in board["alerts"]:
            print(f"  - {alert}")


def main():
    latest_json = find_latest_adif_json()
    print(f"Reading: {latest_json}")

    with latest_json.open("r", encoding="utf-8") as f:
        adif_data = json.load(f)

    board = build_board(adif_data)
    print_board(board)

    output_path = LOG_DIR / "board_latest.json"
    output_path.write_text(json.dumps(board, indent=2, ensure_ascii=False), encoding="utf-8")

    print("")
    print(f"Saved board JSON to: {output_path}")


if __name__ == "__main__":
    main()
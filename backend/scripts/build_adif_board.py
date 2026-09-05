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
        "estacion de francia",
        "passeig de gràcia",
        "passeig de gracia",
        "sants",
        "sant celoni",
        "granollers",
        "maçanet",
        "macanet",
        "aeroport",
    ]

    if any(keyword in destination_lower for keyword in south_keywords):
        return "to_south"

    if any(keyword in destination_lower for keyword in barcelona_keywords):
        return "to_barcelona"

    return "unknown"


def simplify_destination(destination):
    replacements = {
        "Barcelona Estació de França": "Barcelona EdF",
        "Vilanova i la Geltrú": "Vilanova",
        "Sant Vicenç de Calders": "Sant Vicenç",
        "Sant Celoni": "Sant Celoni",
    }
    return replacements.get(destination, destination)


def simplify_observation(observation):
    if not observation:
        return ""

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

    for row in adif_data.get("horarios", []):
        destination = row.get("estacion", "")
        direction = classify_direction(destination)

        item = {
            "time": row.get("hora", ""),
            "destination": simplify_destination(destination),
            "destination_full": destination,
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

    seen_alerts = set()
    for group in ["to_barcelona", "to_south", "unknown"]:
        for item in board[group]:
            obs = item.get("observation", "")
            if obs and obs not in seen_alerts:
                board["alerts"].append(obs)
                seen_alerts.add(obs)

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
            f"  {item['time']:>6} | {item['destination']:<14} | "
            f"{item['line']:<4} | vía {item['platform']}{obs}"
        )

    print("")
    print("← Vilanova / Sant Vicenç")
    if not board["to_south"]:
        print("  No departures found.")
    for item in board["to_south"]:
        obs = f" | {item['observation']}" if item["observation"] else ""
        print(
            f"  {item['time']:>6} | {item['destination']:<14} | "
            f"{item['line']:<4} | vía {item['platform']}{obs}"
        )

    if board["unknown"]:
        print("")
        print("Unknown direction")
        for item in board["unknown"]:
            print(
                f"  {item['time']:>6} | {item['destination']:<14} | "
                f"{item['line']:<4} | vía {item['platform']}"
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
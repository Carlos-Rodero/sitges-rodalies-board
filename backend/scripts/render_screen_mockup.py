import json
import textwrap
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "logs"

BOARD_JSON = LOG_DIR / "board_latest.json"

SCREEN_WIDTH = 104
MAX_TRAINS_PER_DIRECTION = 3
MAX_ALERT_LINES = 2

R2S_STATIONS = [
    ("SVC", "Sant Vicenç de Calders"),
    ("CAL", "Calafell"),
    ("SEG", "Segur de Calafell"),
    ("CUN", "Cunit"),
    ("CUB", "Cubelles"),
    ("VNG", "Vilanova i la Geltrú"),
    ("SIT", "Sitges"),
    ("GAR", "Garraf"),
    ("PCF", "Platja de Castelldefels"),
    ("CDF", "Castelldefels"),
    ("GAV", "Gavà"),
    ("VLD", "Viladecans"),
    ("ELP", "El Prat de Llobregat"),
    ("BEL", "Bellvitge / Gornal"),
    ("SAN", "Barcelona Sants"),
    ("PGR", "Passeig de Gràcia"),
    ("EDF", "Barcelona Estació de França"),
]


def short_text(text, max_len):
    text = str(text or "")
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def load_board():
    if not BOARD_JSON.exists():
        raise FileNotFoundError(
            f"{BOARD_JSON} not found. Run build_board_live.py first."
        )

    with BOARD_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_imminent_train_icons(board):
    """
    Returns train icons to display on the station line.

    For now, without reliable vehicle positions, we only place trains at SIT
    when they are imminent departures from Sitges.
    Later, this will be replaced/enriched with Renfe vehicle_positions.
    """
    icons = {}

    sit_index = next(
        i for i, (code, _name) in enumerate(R2S_STATIONS)
        if code == "SIT"
    )

    for item in board.get("to_barcelona", []):
        minutes_until = item.get("minutes_until")
        if minutes_until is not None and minutes_until <= 15:
            icons[sit_index] = "[>]"

    for item in board.get("to_south", []):
        minutes_until = item.get("minutes_until")
        if minutes_until is not None and minutes_until <= 15:
            icons[sit_index] = "[<]"

    return icons


def format_line_map(board):
    # Full R2 Sud station mockup.
    # ◎ marks Sitges, the station being queried.
    # [>] train towards Barcelona.
    # [<] train towards Vilanova / Sant Vicenç.
    marker_parts = []
    label_parts = []

    for code, _name in R2S_STATIONS:
        marker = "◎" if code == "SIT" else "○"
        marker_parts.append(f"{marker:^3}")
        label_parts.append(f"{code:^3}")

    marker_line = "───".join(marker_parts)
    label_line = "   ".join(label_parts)

    train_line_chars = [" "] * len(marker_line)
    icons = get_imminent_train_icons(board)

    for station_index, icon in icons.items():
        # Each station cell starts every 6 characters:
        # " ○ " + "───" = 6
        start = station_index * 6
        for j, char in enumerate(icon):
            if start + j < len(train_line_chars):
                train_line_chars[start + j] = char

    train_line = "".join(train_line_chars).rstrip()

    lines = [
        "R2S Sant Vicenç → Sitges → Barcelona",
    ]

    if train_line.strip():
        lines.append(train_line)

    lines.extend([
        marker_line,
        label_line,
        "[>] hacia Barcelona   [<] hacia Vilanova/Sant Vicenç",
    ])

    return lines


def format_train_row(item):
    time = short_text(item.get("time", ""), 5)
    destination = short_text(item.get("destination", ""), 14)
    line = short_text(item.get("line", ""), 4)
    platform = short_text(item.get("platform", ""), 2)
    leave_home = short_text(item.get("leave_home", ""), 12)

    urgency = item.get("urgency", "")
    if urgency == "now":
        marker = "!"
    elif urgency == "soon":
        marker = "·"
    else:
        marker = " "

    return f"{marker} {time:<5} {destination:<14} {line:<4} v{platform:<2} {leave_home}"


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


def render_screen(board):
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

    lines.extend(format_line_map(board))

    lines.append("")
    lines.extend(format_section("→ Barcelona", board.get("to_barcelona", [])))

    lines.append("")
    lines.extend(format_section("← Vilanova / Sant Vicenç", board.get("to_south", [])))

    alert_lines = format_alerts(board.get("alerts", []))
    if alert_lines:
        lines.append("")
        lines.extend(alert_lines)

    return "\n".join(lines)


def main():
    board = load_board()
    screen_text = render_screen(board)

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
import json
import os
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from build_adif_board import build_board, print_board

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "logs"

load_dotenv(PROJECT_ROOT / ".env")


def fetch_adif_board():
    adif_url = os.getenv("ADIF_URL")
    adif_cookie = os.getenv("ADIF_COOKIE")

    if not adif_url or not adif_cookie:
        raise RuntimeError("Missing ADIF_URL or ADIF_COOKIE in .env")

    headers = {
        "accept": "*/*",
        "accept-language": "ca-ES,ca;q=0.9,en;q=0.8,es;q=0.7,fr;q=0.6,it;q=0.5",
        "cookie": adif_cookie,
        "referer": "https://www.adif.es/w/71701-sitges",
        "sec-ch-ua": '"Chromium";v="152", "Not?A_Brand";v="24", "Google Chrome";v="152"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/152.0.0.0 Safari/537.36"
        ),
        "x-requested-with": "XMLHttpRequest",
    }

    response = requests.get(adif_url, headers=headers, timeout=30)

    print(f"Adif status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('content-type')}")
    print(f"Size: {len(response.content) / 1024:.1f} KB")

    if response.status_code != 200:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        error_path = LOG_DIR / f"adif_live_error_{timestamp}.html"
        error_path.write_text(response.text, encoding="utf-8", errors="replace")

        print("")
        print(f"Saved error response to: {error_path}")
        print("Adif did not return 200. The browser token/cookies may have expired.")
        print("Refresh the Adif page in Chrome and copy a new cURL if needed.")
        return None

    try:
        return response.json()
    except json.JSONDecodeError:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_path = LOG_DIR / f"adif_live_non_json_{timestamp}.txt"
        raw_path.write_text(response.text, encoding="utf-8", errors="replace")

        print("")
        print(f"Saved non-JSON response to: {raw_path}")
        print("Adif returned 200, but the response was not valid JSON.")
        return None


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    adif_data = fetch_adif_board()

    if adif_data is None:
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    raw_json_path = LOG_DIR / f"adif_live_{timestamp}.json"
    raw_json_path.write_text(
        json.dumps(adif_data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    board = build_board(adif_data)

    board_path = LOG_DIR / "board_latest.json"
    board_path.write_text(
        json.dumps(board, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print_board(board)

    print("")
    print(f"Saved raw Adif JSON to: {raw_json_path}")
    print(f"Saved board JSON to: {board_path}")


if __name__ == "__main__":
    main()
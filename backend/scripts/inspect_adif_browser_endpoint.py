import json
import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "logs"

load_dotenv(PROJECT_ROOT / ".env")


def main():
    adif_url = os.getenv("ADIF_URL")
    adif_cookie = os.getenv("ADIF_COOKIE")

    if not adif_url or not adif_cookie:
        print("Missing ADIF_URL or ADIF_COOKIE in .env")
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)

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

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = LOG_DIR / f"adif_browser_endpoint_{timestamp}.txt"
    raw_path.write_text(response.text, encoding="utf-8", errors="replace")

    print(f"Status: {response.status_code}")
    print(f"Final URL: {response.url}")
    print(f"Content-Type: {response.headers.get('content-type')}")
    print(f"Size: {len(response.content) / 1024:.1f} KB")
    print(f"Saved response to: {raw_path}")

    print("")
    print("=== Response preview ===")
    print(response.text[:3000])

    if response.status_code != 200:
        print("")
        print("Adif did not return 200. The browser token/cookies may have expired.")
        return

    content_type = response.headers.get("content-type", "").lower()

    if "json" in content_type:
        try:
            data = response.json()
            json_path = LOG_DIR / f"adif_browser_endpoint_{timestamp}.json"
            json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            print("")
            print(f"Saved JSON to: {json_path}")
            print("JSON type:", type(data).__name__)
            if isinstance(data, dict):
                print("JSON keys:", list(data.keys()))
            return
        except json.JSONDecodeError:
            print("Content-Type says JSON, but could not decode as JSON.")

    soup = BeautifulSoup(response.text, "lxml")
    text = soup.get_text("\n", strip=True)

    txt_path = LOG_DIR / f"adif_browser_endpoint_{timestamp}_text.txt"
    txt_path.write_text(text, encoding="utf-8", errors="replace")

    print("")
    print(f"Saved extracted text to: {txt_path}")

    print("")
    print("=== Interesting lines ===")
    for line in text.splitlines():
        if re.search(
            r"R2S|R2N|Barcelona|Vilanova|Vicenç|Sant|Sitges|Hora|Destino|Origen|Vía|Via|Línea|Linea|\d+\s*min|\d{2}:\d{2}",
            line,
            re.IGNORECASE,
        ):
            print(line)


if __name__ == "__main__":
    main()
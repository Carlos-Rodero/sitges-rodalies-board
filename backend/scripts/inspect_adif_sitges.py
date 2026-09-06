import re
from wsgiref import headers
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime

ADIF_SITGES_URL = "https://www.adif.es/w/71701-sitges"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "logs"


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,ca;q=0.8,en;q=0.7",
        "Connection": "keep-alive",
        "Referer": "https://www.adif.es/",
    }

    session = requests.Session()
    response = session.get(ADIF_SITGES_URL, headers=headers, timeout=30)

    print(f"Status: {response.status_code}")
    print(f"Final URL: {response.url}")
    print(f"Content-Type: {response.headers.get('content-type')}")
    print(f"Response preview: {response.text[:500]}")

    if response.status_code != 200:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        error_path = LOG_DIR / f"adif_sitges_error_{timestamp}.html"
        error_path.write_text(response.text, encoding="utf-8", errors="replace")

        print("")
        print("Adif returned a non-200 response.")
        print(f"Status: {response.status_code}")
        print(f"Saved error response to: {error_path}")
        print("")
        print("This probably means Adif blocks direct requests from Python.")
        print("Next step: inspect the browser Network/XHR calls instead.")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_path = LOG_DIR / f"adif_sitges_{timestamp}.html"
    txt_path = LOG_DIR / f"adif_sitges_{timestamp}.txt"

    html_path.write_text(response.text, encoding="utf-8", errors="replace")

    soup = BeautifulSoup(response.text, "lxml")
    text = soup.get_text("\n", strip=True)
    txt_path.write_text(text, encoding="utf-8", errors="replace")

    print(f"Status: {response.status_code}")
    print(f"HTML size: {len(response.text) / 1024:.1f} KB")
    print(f"Saved HTML to: {html_path}")
    print(f"Saved text to: {txt_path}")

    print("")
    print("=== Lines containing R2S / R2N / Barcelona / Vilanova / Sant Vicenç ===")
    interesting = []
    for line in text.splitlines():
        if re.search(r"R2S|R2N|Barcelona|Vilanova|Vicenç|Sitges|Salidas|Llegadas|Hora actual|Vía", line, re.IGNORECASE):
            interesting.append(line)

    for line in interesting[:200]:
        print(line)


if __name__ == "__main__":
    main()
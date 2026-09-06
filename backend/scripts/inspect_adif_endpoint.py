import json
import re
import requests
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

ADIF_ENDPOINT_URL = "https://www.adif.es/w/71701-sitges?p_p_id=servicios_estacion_ServiciosEstacionPortlet&p_p_lifecycle=2&p_p_state=normal&p_p_mode=view&p_p_resource_id=%2FconsultarHorario&p_p_cacheability=cacheLevelPage&assetEntryId=3106420&p_p_auth=db2ynLMe&_servicios_estacion_ServiciosEstacionPortlet_searchType=proximasSalidas&_servicios_estacion_ServiciosEstacionPortlet_trafficType=cercanias&_servicios_estacion_ServiciosEstacionPortlet_numPage=0&_servicios_estacion_ServiciosEstacionPortlet_commuterNetwork=RODALIES_CATALUNYA&_servicios_estacion_ServiciosEstacionPortlet_stationCode=71701"

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
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "es-ES,es;q=0.9,ca;q=0.8,en;q=0.7",
        "Referer": "https://www.adif.es/w/71701-sitges",
        "X-Requested-With": "XMLHttpRequest",
    }

    session = requests.Session()
    response = session.get(ADIF_ENDPOINT_URL, headers=headers, timeout=30)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = LOG_DIR / f"adif_endpoint_{timestamp}.txt"
    raw_path.write_text(response.text, encoding="utf-8", errors="replace")

    print(f"Status: {response.status_code}")
    print(f"Final URL: {response.url}")
    print(f"Content-Type: {response.headers.get('content-type')}")
    print(f"Size: {len(response.content) / 1024:.1f} KB")
    print(f"Saved response to: {raw_path}")
    print("")
    print("=== Response preview ===")
    print(response.text[:2000])

    if response.status_code != 200:
        print("")
        print("Adif did not return 200. The p_p_auth token may be expired or tied to browser cookies.")
        print("If this happens, we will need to reproduce the request using 'Copy as cURL'.")
        return

    content_type = response.headers.get("content-type", "")

    if "json" in content_type.lower():
        try:
            data = response.json()
            json_path = LOG_DIR / f"adif_endpoint_{timestamp}.json"
            json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            print("")
            print(f"Saved JSON to: {json_path}")
            print("")
            print("=== JSON keys ===")
            if isinstance(data, dict):
                print(list(data.keys()))
            elif isinstance(data, list):
                print(f"List with {len(data)} items")
        except json.JSONDecodeError:
            print("Content-Type looked like JSON, but response could not be parsed as JSON.")

    soup = BeautifulSoup(response.text, "lxml")
    text = soup.get_text("\n", strip=True)

    print("")
    print("=== Lines containing trains / destinations / platforms ===")
    for line in text.splitlines():
        if re.search(
            r"R2S|R2N|Barcelona|Vilanova|Vicenç|Sant|Sitges|Hora|Destino|Origen|Vía|via|Tren",
            line,
            re.IGNORECASE,
        ):
            print(line)


if __name__ == "__main__":
    main()
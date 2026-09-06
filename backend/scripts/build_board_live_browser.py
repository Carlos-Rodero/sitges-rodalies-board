import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from build_adif_board import build_board, print_board

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "logs"

BOARD_JSON = LOG_DIR / "board_latest.json"

STATION_CODE = "71701"
STATION_URL = "https://www.adif.es/w/71701-sitges"
ASSET_ENTRY_ID_FALLBACK = "3106420"

PORTLET_ID = "servicios_estacion_ServiciosEstacionPortlet"
PORTLET_PREFIX = "_servicios_estacion_ServiciosEstacionPortlet_"


def now_stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def extract_auth_token(html):
    patterns = [
        r"p_p_auth=([^&\"'<>]+)",
        r"Liferay\.authToken\s*=\s*['\"]([^'\"]+)['\"]",
        r"authToken\s*:\s*['\"]([^'\"]+)['\"]",
        r'"p_p_auth"\s*:\s*"([^"]+)"',
    ]

    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return match.group(1)

    return None


def extract_asset_entry_id(html):
    patterns = [
        r"assetEntryId=([0-9]+)",
        r"assetEntryId\s*[:=]\s*['\"]?([0-9]+)",
        r'"assetEntryId"\s*:\s*"([0-9]+)"',
    ]

    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return match.group(1)

    return ASSET_ENTRY_ID_FALLBACK


def make_departures_url(auth_token, asset_entry_id):
    query = {
        "p_p_id": PORTLET_ID,
        "p_p_lifecycle": "2",
        "p_p_state": "normal",
        "p_p_mode": "view",
        "p_p_resource_id": "/consultarHorario",
        "p_p_cacheability": "cacheLevelPage",
        "assetEntryId": asset_entry_id,
        "p_p_auth": auth_token,
        PORTLET_PREFIX + "searchType": "proximasSalidas",
        PORTLET_PREFIX + "trafficType": "cercanias",
        PORTLET_PREFIX + "numPage": "0",
        PORTLET_PREFIX + "commuterNetwork": "RODALIES_CATALUNYA",
        PORTLET_PREFIX + "stationCode": STATION_CODE,
    }

    return STATION_URL + "?" + urlencode(query)


async def fetch_adif_departures():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        context = await browser.new_context(
            locale="es-ES",
            timezone_id="Europe/Madrid",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        page = await context.new_page()

        print(f"Opening Adif station page: {STATION_URL}")

        await page.goto(
            STATION_URL,
            wait_until="domcontentloaded",
            timeout=45000,
        )

        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightTimeoutError:
            pass

        await page.wait_for_timeout(3000)

        html = await page.content()

        # First try to read the token from the live JavaScript context.
        auth_token = await page.evaluate(
            """
            () => {
                if (window.Liferay && window.Liferay.authToken) {
                    return window.Liferay.authToken;
                }

                if (window.Liferay && window.Liferay.ThemeDisplay && window.Liferay.ThemeDisplay.getPathContext) {
                    return window.Liferay.authToken || null;
                }

                return null;
            }
            """
        )

        # Fallback: try to extract it from the HTML text.
        if not auth_token:
            auth_token = extract_auth_token(html)

        asset_entry_id = extract_asset_entry_id(html)

        title = await page.title()
        current_url = page.url

        print(f"Page title: {title}")
        print(f"Current URL: {current_url}")
        print(f"HTML size: {len(html) / 1024:.1f} KB")

        if not auth_token:
            debug_html = LOG_DIR / f"adif_page_debug_{now_stamp()}.html"
            debug_png = LOG_DIR / f"adif_page_debug_{now_stamp()}.png"

            debug_html.write_text(html, encoding="utf-8")
            await page.screenshot(path=str(debug_png), full_page=True)

            await browser.close()

            raise RuntimeError(
                f"Could not extract p_p_auth token. "
                f"Saved debug files: {debug_html} and {debug_png}"
            )

        print(f"Extracted p_p_auth: {auth_token[:6]}...")
        print(f"AssetEntryId: {asset_entry_id}")

        departures_url = make_departures_url(auth_token, asset_entry_id)

        print(f"Departures URL: {departures_url}")

        result = await page.evaluate(
            """
            async (url) => {
                const response = await fetch(url, {
                    credentials: "include",
                    headers: {
                        "Accept": "application/json, text/plain, */*",
                        "X-Requested-With": "XMLHttpRequest"
                    }
                });

                const text = await response.text();

                return {
                    status: response.status,
                    contentType: response.headers.get("content-type"),
                    text: text
                };
            }
            """,
            departures_url,
        )

        await browser.close()

    print(f"Adif status: {result['status']}")
    print(f"Content-Type: {result['contentType']}")
    print(f"Size: {len(result['text']) / 1024:.1f} KB")

    try:
        data = json.loads(result["text"])
    except json.JSONDecodeError:
        preview = result["text"][:1000]
        raise RuntimeError(f"Adif did not return JSON. Preview:\n{preview}")

    return data, departures_url


async def main_async():
    LOG_DIR.mkdir(exist_ok=True)

    try:
        adif_data, departures_url = await fetch_adif_departures()
    except Exception as exc:
        print(f"Adif browser fetch failed: {exc}")
        return 1

    raw_path = LOG_DIR / f"adif_live_browser_{now_stamp()}.json"
    raw_path.write_text(
        json.dumps(adif_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Saved raw Adif JSON to: {raw_path}")

    if not isinstance(adif_data, dict):
        print("Adif did not return a JSON object. board_latest.json was NOT overwritten.")
        return 1

    if adif_data.get("error") is True:
        print("Adif returned error=true. board_latest.json was NOT overwritten.")
        return 1

    if not adif_data.get("horarios"):
        print("Adif returned no horarios. board_latest.json was NOT overwritten.")
        return 1

    board = build_board(adif_data)

    BOARD_JSON.write_text(
        json.dumps(board, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Saved board to: {BOARD_JSON}")
    print("")
    print_board(board)

    return 0


def main():
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
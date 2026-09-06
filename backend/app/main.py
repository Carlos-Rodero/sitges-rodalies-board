from fastapi import FastAPI
from .mock_data import get_mock_board
import json
from pathlib import Path
from fastapi import HTTPException

app = FastAPI(title="Sitges Rodalies Board API")

@app.get("/")
def root():
    return {"status": "ok", "project": "sitges-rodalies-board"}

@app.get("/api/board/sitges")
def sitges_board():
    return get_mock_board()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ESP32_PAYLOAD_JSON = PROJECT_ROOT / "logs" / "esp32_payload_latest.json"


@app.get("/api/board/sitges/esp32")
def get_sitges_esp32_payload():
    if not ESP32_PAYLOAD_JSON.exists():
        raise HTTPException(
            status_code=404,
            detail="ESP32 payload not found. Run backend/scripts/update_all.py first.",
        )

    with ESP32_PAYLOAD_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)
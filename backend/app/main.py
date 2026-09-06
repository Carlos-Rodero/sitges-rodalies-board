from fastapi import FastAPI
from app.mock_data import get_mock_board

app = FastAPI(title="Sitges Rodalies Board API")

@app.get("/")
def root():
    return {"status": "ok", "project": "sitges-rodalies-board"}

@app.get("/api/board/sitges")
def sitges_board():
    return get_mock_board()
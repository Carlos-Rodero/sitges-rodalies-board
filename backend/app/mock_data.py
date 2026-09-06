from datetime import datetime

def get_mock_board():
    return {
        "station": "Sitges",
        "updated": datetime.now().strftime("%H:%M"),
        "walk_minutes": 10,
        "line": {
            "left_label": "STV",
            "center_label": "Sitges",
            "right_label": "BCN",
            "trains": [
                {"direction": "right", "position": 0.36, "label": "08:37", "location": "Vilanova"},
                {"direction": "left", "position": 0.72, "label": "08:26", "location": "Castelldefels"}
            ]
        },
        "to_barcelona": [
            {"time": "08:37", "delay": 4, "destination": "Barcelona", "location": "Vilanova", "leave_home": "08:24", "confidence": "high"},
            {"time": "08:52", "delay": None, "destination": "Barcelona", "location": "sin posición", "leave_home": "08:39", "confidence": "low"}
        ],
        "to_south": [
            {"time": "08:26", "delay": 2, "destination": "Sant Vicenç", "location": "Castelldefels", "leave_home": "08:13", "confidence": "high"},
            {"time": "08:44", "delay": 0, "destination": "Vilanova", "location": "Sants", "leave_home": "08:31", "confidence": "medium"}
        ],
        "alerts": ["Sin incidencias relevantes en este momento"]
    }
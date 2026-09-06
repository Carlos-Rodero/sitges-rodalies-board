import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SCRIPTS = [
    "build_board_live.py",
    "build_train_positions.py",
    "build_enriched_board.py",
    "render_screen_mockup.py",
    "build_esp32_payload.py",
]


def run_script(script_name):
    script_path = PROJECT_ROOT / "backend" / "scripts" / script_name

    print("")
    print("=" * 80)
    print(f"Running {script_name}")
    print("=" * 80)

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=PROJECT_ROOT,
        text=True,
    )

    if result.returncode != 0:
        print("")
        print(f"Error while running {script_name}")
        sys.exit(result.returncode)


def main():
    for script in SCRIPTS:
        run_script(script)

    print("")
    print("=" * 80)
    print("All done.")
    print("=" * 80)
    print("")
    print("Generated files:")
    print("  logs/board_latest.json")
    print("  logs/train_positions_latest.json")
    print("  logs/board_enriched_latest.json")
    print("  logs/screen_mockup.txt")
    print("  logs/esp32_payload_latest.json")


if __name__ == "__main__":
    main()
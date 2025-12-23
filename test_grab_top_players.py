import json
import sys
from pathlib import Path

# Ensure project root is on PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.api.players import fetch_top_players


def main():
    players = fetch_top_players(limit=10)

    print("=== RAW PLAYERS JSON ===")
    print(json.dumps(players, indent=2))


if __name__ == "__main__":
    main()

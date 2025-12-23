"""
test_grab_player_info.py

Goal:
- Load .env
- Call Clash Royale API: GET /players/{playerTag}
- Print full raw JSON output
- Also print quick trophy fields
"""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv


def normalize_player_tag(tag: str) -> str:
    tag = tag.strip().upper()
    if not tag.startswith("#"):
        tag = "#" + tag
    return tag


def main() -> None:
    # --- Make sure project root is on sys.path (so `from src...` works) ---
    project_root = Path(__file__).resolve().parent
    sys.path.insert(0, str(project_root))

    # --- Load .env ---
    load_dotenv(project_root / ".env")

    player_tag = os.getenv("PLAYER_TAG", "").strip()
    if not player_tag:
        raise SystemExit("ERROR: PLAYER_TAG is missing in .env")

    # --- Import your API client ---
    from src.api.cr_client import cr_get  # type: ignore

    normalized = normalize_player_tag(player_tag)
    encoded_tag = normalized.replace("#", "%23", 1)

    # --- Call endpoint: /players/{tag} ---
    data = cr_get(f"/players/{encoded_tag}")

    print("\n=== PLAYER INFO (RAW JSON) ===")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    print("\n=== TROPHY QUICK PEEK ===")
    # Most important trophy fields you’ll care about
    print("name:         ", data.get("name"))
    print("tag:          ", data.get("tag"))
    print("trophies:     ", data.get("trophies"))        # current trophies
    print("bestTrophies: ", data.get("bestTrophies"))    # best trophies
    print("wins:         ", data.get("wins"))
    print("losses:       ", data.get("losses"))
    print("battleCount:  ", data.get("battleCount"))


if __name__ == "__main__":
    main()

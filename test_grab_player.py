"""
test_grab_player.py

Goal:
- Load .env
- Grab the player's battlelog from Clash Royale API
- Print the MOST RECENT battle (raw JSON) so you can see the structure

Expected .env:
PLAYER_TAG=#8C83JQLG
CR_API_KEY=...
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv
import os


def main() -> None:
    # ------------------------------------------------------------------
    # 1) Make imports work no matter where you run from
    #    Assumption: your code lives under ./src/...
    # ------------------------------------------------------------------
    project_root = Path(__file__).resolve().parent
    if (project_root / "src").exists():
        sys.path.insert(0, str(project_root))
    else:
        # If you put this file inside src/ or a subfolder, walk up until we find src/
        cur = project_root
        while cur != cur.parent:
            if (cur / "src").exists():
                sys.path.insert(0, str(cur))
                project_root = cur
                break
            cur = cur.parent

    # ------------------------------------------------------------------
    # 2) Load env
    # ------------------------------------------------------------------
    env_path = project_root / ".env"
    load_dotenv(env_path)

    player_tag = os.getenv("PLAYER_TAG", "").strip()
    if not player_tag:
        raise SystemExit("ERROR: PLAYER_TAG is missing in .env")

    # ------------------------------------------------------------------
    # 3) Import your existing function and fetch battlelog
    #    (Based on your uploaded battles.py)
    # ------------------------------------------------------------------
    # If your file is exactly: src/api/battles.py
    from src.api.battles import get_player_battlelog  # type: ignore

    battles = get_player_battlelog(player_tag)

    if not battles:
        print("No battles returned (empty list).")
        return

    most_recent = battles[0]

    print("\n=== MOST RECENT BATTLE (RAW JSON) ===")
    print(json.dumps(most_recent, indent=2, ensure_ascii=False))

    # Optional: quick human-readable peek
    print("\n=== QUICK PEEK ===")
    battle_time = most_recent.get("battleTime")
    game_mode = (most_recent.get("gameMode") or {}).get("name")
    battle_type = most_recent.get("type")
    team0 = (most_recent.get("team") or [{}])[0]
    opp0 = (most_recent.get("opponent") or [{}])[0]
    print(f"battleTime: {battle_time}")
    print(f"gameMode:   {game_mode}")
    print(f"type:       {battle_type}")
    print(f"team crowns: {team0.get('crowns')} | opponent crowns: {opp0.get('crowns')}")
    print(f"team tag:   {team0.get('tag')} | opponent tag: {opp0.get('tag')}")


if __name__ == "__main__":
    main()

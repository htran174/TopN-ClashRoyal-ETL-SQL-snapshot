# scripts/validate_snapshot.py
from __future__ import annotations

import os
import sys
import argparse
from dataclasses import dataclass
from typing import Iterable, Optional

from sqlalchemy import create_engine, text
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise SystemExit(
        "[VALIDATE] FAIL: DATABASE_URL is not set (and --database-url not provided)."
    )


@dataclass
class CheckResult:
    name: str
    ok: bool
    details: str = ""


def _fail(msg: str) -> None:
    print(f"[VALIDATE] FAIL: {msg}")
    raise SystemExit(1)


def _get_database_url(cli_value: Optional[str]) -> str:
    url = cli_value or os.getenv("DATABASE_URL")
    if not url:
        _fail("DATABASE_URL is not set (and --database-url not provided).")
    return url


def _run_scalar(conn, sql: str, params: Optional[dict] = None):
    return conn.execute(text(sql), params or {}).scalar()


def _run_rows(conn, sql: str, params: Optional[dict] = None):
    return conn.execute(text(sql), params or {}).fetchall()


def check_deck_cards_integrity(conn) -> CheckResult:
    # Every deck_hash should have exactly 8 rows in deck_cards
    rows = _run_rows(
        conn,
        """
        SELECT deck_hash, COUNT(*) AS n
        FROM deck_cards
        GROUP BY deck_hash
        HAVING COUNT(*) <> 8
        LIMIT 20;
        """
    )
    if rows:
        sample = "\n".join([f"  {r[0]} -> {r[1]}" for r in rows])
        return CheckResult(
            name="deck_cards: each deck_hash has exactly 8 cards",
            ok=False,
            details=f"Found deck_hash with != 8 cards (showing up to 20):\n{sample}",
        )
    return CheckResult(name="deck_cards: each deck_hash has exactly 8 cards", ok=True)


def check_wins_uses_sanity(conn) -> CheckResult:
    # no wins > uses and no negatives in any stats table
    tables = [
        ("player_decks", "uses", "wins"),
        ("player_type_cards", "uses", "wins"),
        ("meta_deck_types", "uses", "wins"),
        ("meta_type_cards", "uses", "wins"),
        ("meta_type_deck_ids", "uses", "wins"),
    ]

    bad = []
    for t, uses_col, wins_col in tables:
        n = _run_scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM {t}
            WHERE {wins_col} > {uses_col}
               OR {wins_col} < 0
               OR {uses_col} < 0;
            """
        )
        if n and int(n) > 0:
            bad.append(f"{t} has {n} bad rows")

    if bad:
        return CheckResult(
            name="wins/uses sanity (wins<=uses and non-negative)",
            ok=False,
            details="; ".join(bad),
        )
    return CheckResult(name="wins/uses sanity (wins<=uses and non-negative)", ok=True)


def check_meta_not_empty(conn) -> CheckResult:
    n = _run_scalar(conn, "SELECT COUNT(*) FROM meta_deck_types;")
    if not n or int(n) == 0:
        return CheckResult(
            name="meta sanity: meta_deck_types not empty",
            ok=False,
            details="meta_deck_types is empty",
        )
    return CheckResult(name="meta sanity: meta_deck_types not empty", ok=True)


def check_unknown_deck_type_explosion(conn, max_unknown_ratio: float) -> CheckResult:
    # If you use 'Unknown' as a label in your deck_type classifier, catch explosions.
    # If you don't have 'Unknown', this will just return OK.
    total = _run_scalar(conn, "SELECT COALESCE(SUM(uses),0) FROM meta_deck_types;")
    unknown = _run_scalar(
        conn,
        "SELECT COALESCE(SUM(uses),0) FROM meta_deck_types WHERE deck_type ILIKE 'unknown';"
    )
    total = int(total or 0)
    unknown = int(unknown or 0)

    if total == 0:
        return CheckResult(
            name="deck_type sanity: unknown ratio",
            ok=False,
            details="meta_deck_types total uses is 0",
        )

    ratio = unknown / total
    if ratio > max_unknown_ratio:
        return CheckResult(
            name="deck_type sanity: unknown ratio",
            ok=False,
            details=f"Unknown uses ratio too high: {unknown}/{total} = {ratio:.2%} (max {max_unknown_ratio:.2%})",
        )
    return CheckResult(
        name="deck_type sanity: unknown ratio",
        ok=True,
        details=f"Unknown ratio: {unknown}/{total} = {ratio:.2%}",
    )


def check_totals_sanity_topn_vs_meta(conn) -> CheckResult:
    """
    Key invariant given your rule:
    - You ingest matches if at least one participant is TopN.
    - player_decks stores ONLY TopN players' deck observations.
    - meta_deck_types stores BOTH sides' deck observations for included matches.

    Therefore:
      topn_obs = SUM(player_decks.uses)
      meta_obs = SUM(meta_deck_types.uses)

    We must have:
      meta_obs >= topn_obs
      meta_obs <= 2 * topn_obs
    (Because each included match contributes exactly 2 deck observations into meta,
     while TopN observations per match is either 1 or 2.)
    """
    topn_obs = int(_run_scalar(conn, "SELECT COALESCE(SUM(uses),0) FROM player_decks;") or 0)
    meta_obs = int(_run_scalar(conn, "SELECT COALESCE(SUM(uses),0) FROM meta_deck_types;") or 0)

    if topn_obs == 0:
        return CheckResult(
            name="totals sanity: meta_obs between topn_obs and 2*topn_obs",
            ok=False,
            details="topn_obs (SUM(player_decks.uses)) is 0; did ETL write player_decks?",
        )

    if meta_obs < topn_obs:
        return CheckResult(
            name="totals sanity: meta_obs between topn_obs and 2*topn_obs",
            ok=False,
            details=f"meta_obs < topn_obs ({meta_obs} < {topn_obs})",
        )
    if meta_obs > 2 * topn_obs:
        return CheckResult(
            name="totals sanity: meta_obs between topn_obs and 2*topn_obs",
            ok=False,
            details=f"meta_obs > 2*topn_obs ({meta_obs} > {2*topn_obs})",
        )

    return CheckResult(
        name="totals sanity: meta_obs between topn_obs and 2*topn_obs",
        ok=True,
        details=f"topn_obs={topn_obs}, meta_obs={meta_obs}, ratio={meta_obs/topn_obs:.2f}",
    )


def check_expected_topn_player_count(conn, expected_topn: Optional[int]) -> CheckResult:
    if expected_topn is None:
        return CheckResult(name="player count matches --top-n (skipped)", ok=True)

    n = int(_run_scalar(conn, "SELECT COUNT(*) FROM player;") or 0)
    if n != expected_topn:
        return CheckResult(
            name="player count matches --top-n",
            ok=False,
            details=f"player table count = {n}, expected {expected_topn}",
        )
    return CheckResult(name="player count matches --top-n", ok=True, details=f"player={n}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate snapshot tables for sanity + integrity.")
    ap.add_argument("--database-url", default=None, help="Overrides DATABASE_URL env var.")
    ap.add_argument("--top-n", type=int, default=None, help="Expected count in player table (optional).")
    ap.add_argument(
        "--max-unknown-ratio",
        type=float,
        default=0.30,
        help="Fail if Unknown deck_type uses ratio exceeds this (default 0.30).",
    )
    args = ap.parse_args()

    url = _get_database_url(args.database_url)
    engine = create_engine(url, future=True)

    checks = []
    with engine.connect() as conn:
        checks.append(check_deck_cards_integrity(conn))
        checks.append(check_wins_uses_sanity(conn))
        checks.append(check_meta_not_empty(conn))
        checks.append(check_expected_topn_player_count(conn, args.top_n))
        checks.append(check_totals_sanity_topn_vs_meta(conn))
        checks.append(check_unknown_deck_type_explosion(conn, args.max_unknown_ratio))

    print("\n[VALIDATE] RESULTS")
    failed = 0
    for c in checks:
        status = "OK" if c.ok else "FAIL"
        print(f"  - {status}: {c.name}")
        if c.details:
            print(f"      {c.details.replace(chr(10), chr(10) + '      ')}")
        if not c.ok:
            failed += 1

    if failed:
        print(f"\n[VALIDATE] FAILED ({failed} checks).")
        sys.exit(1)

    print("\n[VALIDATE] PASSED.")
    sys.exit(0)


if __name__ == "__main__":
    main()

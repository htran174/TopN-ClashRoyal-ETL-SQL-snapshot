#!/usr/bin/env bash
set -euo pipefail

# Exports a compressed SQL dump + a small JSON summary of row counts.
# Requires: pg_dump, psql, gzip
#
# Env expected:
#   DATABASE_URL  (postgres://...)
# Optional:
#   TOPN          (for metadata in summary)
#   EXPORT_DIR    (defaults to exports)

EXPORT_DIR="${EXPORT_DIR:-exports}"
TOPN_VAL="${TOPN:-1000}"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL is not set."
  exit 1
fi

mkdir -p "$EXPORT_DIR"

echo "[export] dumping snapshot to ${EXPORT_DIR}/snapshot.sql.gz ..."
# Plain SQL -> gzip (portable, easy to inspect)
pg_dump \
  --no-owner \
  --no-acl \
  "$DATABASE_URL" \
  | gzip -9 > "${EXPORT_DIR}/snapshot.sql.gz"

echo "[export] generating run_summary.json ..."
RUN_DATE_UTC="$(date -u +%Y-%m-%d)"
RUN_TS_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Query row counts (keep it simple + stable)
PLAYER_COUNT="$(psql "$DATABASE_URL" -tA -c "SELECT COUNT(*) FROM player;")"
DECKS_COUNT="$(psql "$DATABASE_URL" -tA -c "SELECT COUNT(*) FROM decks;")"
CARDS_COUNT="$(psql "$DATABASE_URL" -tA -c "SELECT COUNT(*) FROM cards;")"
DECK_CARDS_COUNT="$(psql "$DATABASE_URL" -tA -c "SELECT COUNT(*) FROM deck_cards;")"
PLAYER_DECKS_COUNT="$(psql "$DATABASE_URL" -tA -c "SELECT COUNT(*) FROM player_decks;")"
META_DECK_TYPES_COUNT="$(psql "$DATABASE_URL" -tA -c "SELECT COUNT(*) FROM meta_deck_types;")"
META_TYPE_DECK_IDS_COUNT="$(psql "$DATABASE_URL" -tA -c "SELECT COUNT(*) FROM meta_type_deck_ids;")"
META_TYPE_CARDS_COUNT="$(psql "$DATABASE_URL" -tA -c "SELECT COUNT(*) FROM meta_type_cards;")"
PLAYER_TYPE_CARDS_COUNT="$(psql "$DATABASE_URL" -tA -c "SELECT COUNT(*) FROM player_type_cards;")"

cat > "${EXPORT_DIR}/run_summary.json" <<EOF
{
  "run_date_utc": "${RUN_DATE_UTC}",
  "run_timestamp_utc": "${RUN_TS_UTC}",
  "topn": ${TOPN_VAL},
  "row_counts": {
    "player": ${PLAYER_COUNT},
    "decks": ${DECKS_COUNT},
    "cards": ${CARDS_COUNT},
    "deck_cards": ${DECK_CARDS_COUNT},
    "player_decks": ${PLAYER_DECKS_COUNT},
    "meta_deck_types": ${META_DECK_TYPES_COUNT},
    "meta_type_deck_ids": ${META_TYPE_DECK_IDS_COUNT},
    "meta_type_cards": ${META_TYPE_CARDS_COUNT},
    "player_type_cards": ${PLAYER_TYPE_CARDS_COUNT}
  }
}
EOF

echo "[export] done:"
ls -lh "${EXPORT_DIR}/snapshot.sql.gz" "${EXPORT_DIR}/run_summary.json"

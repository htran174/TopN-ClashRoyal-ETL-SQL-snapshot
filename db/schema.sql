-- ============================================================
-- schema.sql — Clash Royale Top1K Meta Snapshot Warehouse (Postgres)
-- SNAPSHOT MODE: TRUNCATE + RELOAD each refresh
-- ============================================================

-- ============================================================
-- 0) Dimensions
-- ============================================================

-- Deck types (dimension)
CREATE TABLE IF NOT EXISTS deck_types (
  deck_type  TEXT PRIMARY KEY
);

-- Players (dimension)
CREATE TABLE IF NOT EXISTS player (
  player_tag    TEXT PRIMARY KEY,
  player_name   TEXT NOT NULL,
  trophies      INTEGER,
  rank_global   INTEGER
);

-- Cards (dimension)
CREATE TABLE IF NOT EXISTS cards (
  card_id     INTEGER PRIMARY KEY,
  card_name   TEXT NOT NULL
);

-- Decks (dimension)
-- deck_hash is derived from canonical 8-card signature
CREATE TABLE IF NOT EXISTS decks (
  deck_hash   TEXT PRIMARY KEY,
  deck_type   TEXT NOT NULL REFERENCES deck_types(deck_type)
);

-- Optional override mechanism
CREATE TABLE IF NOT EXISTS deck_type_overrides (
  deck_hash   TEXT PRIMARY KEY REFERENCES decks(deck_hash) ON DELETE CASCADE,
  deck_type   TEXT NOT NULL REFERENCES deck_types(deck_type)
);

-- ============================================================
-- 1) Bridge Tables / Base Fact
-- ============================================================

-- Deck composition (8 cards)
CREATE TABLE IF NOT EXISTS deck_cards (
  deck_hash     TEXT NOT NULL REFERENCES decks(deck_hash) ON DELETE CASCADE,
  card_id       INTEGER NOT NULL REFERENCES cards(card_id),
  card_variant  TEXT NOT NULL,
  slot          SMALLINT,

  PRIMARY KEY (deck_hash, card_id, card_variant),

  CONSTRAINT ck_deck_cards_variant
    CHECK (card_variant IN ('normal', 'evo', 'hero')),

  CONSTRAINT ck_deck_cards_slot
    CHECK (slot IS NULL OR (slot >= 1 AND slot <= 8))
);

-- Base fact: per-player per-deck totals
CREATE TABLE IF NOT EXISTS player_decks (
  player_tag  TEXT NOT NULL REFERENCES player(player_tag) ON DELETE CASCADE,
  deck_hash   TEXT NOT NULL REFERENCES decks(deck_hash) ON DELETE CASCADE,
  uses        INTEGER NOT NULL DEFAULT 0,
  wins        INTEGER NOT NULL DEFAULT 0,

  PRIMARY KEY (player_tag, deck_hash),

  CONSTRAINT ck_player_decks_nonneg
    CHECK (uses >= 0 AND wins >= 0 AND wins <= uses)
);

-- ============================================================
-- 2) Rollup Tables (stored aggregates; recomputed each refresh)
-- ============================================================

-- Global totals per deck type
CREATE TABLE IF NOT EXISTS meta_deck_types (
  deck_type  TEXT PRIMARY KEY REFERENCES deck_types(deck_type),
  uses       INTEGER NOT NULL DEFAULT 0,
  wins       INTEGER NOT NULL DEFAULT 0,

  CONSTRAINT ck_meta_deck_types_nonneg
    CHECK (uses >= 0 AND wins >= 0 AND wins <= uses)
);

-- Global totals per exact deck within type
CREATE TABLE IF NOT EXISTS meta_type_deck_ids (
  deck_type  TEXT NOT NULL REFERENCES deck_types(deck_type),
  deck_hash  TEXT NOT NULL REFERENCES decks(deck_hash) ON DELETE CASCADE,
  uses       INTEGER NOT NULL DEFAULT 0,
  wins       INTEGER NOT NULL DEFAULT 0,

  PRIMARY KEY (deck_type, deck_hash),

  CONSTRAINT ck_meta_type_deck_ids_nonneg
    CHECK (uses >= 0 AND wins >= 0 AND wins <= uses)
);

-- Global card totals within a deck type
CREATE TABLE IF NOT EXISTS meta_type_cards (
  deck_type     TEXT NOT NULL REFERENCES deck_types(deck_type),
  card_id       INTEGER NOT NULL REFERENCES cards(card_id),
  card_variant  TEXT NOT NULL,
  uses          INTEGER NOT NULL DEFAULT 0,
  wins          INTEGER NOT NULL DEFAULT 0,

  PRIMARY KEY (deck_type, card_id, card_variant),

  CONSTRAINT ck_meta_type_cards_variant
    CHECK (card_variant IN ('normal', 'evo', 'hero')),

  CONSTRAINT ck_meta_type_cards_nonneg
    CHECK (uses >= 0 AND wins >= 0 AND wins <= uses)
);

-- Per-player card totals within a deck type
CREATE TABLE IF NOT EXISTS player_type_cards (
  player_tag    TEXT NOT NULL REFERENCES player(player_tag) ON DELETE CASCADE,
  deck_type     TEXT NOT NULL REFERENCES deck_types(deck_type),
  card_id       INTEGER NOT NULL REFERENCES cards(card_id),
  card_variant  TEXT NOT NULL,
  uses          INTEGER NOT NULL DEFAULT 0,
  wins          INTEGER NOT NULL DEFAULT 0,

  PRIMARY KEY (player_tag, deck_type, card_id, card_variant),

  CONSTRAINT ck_player_type_cards_variant
    CHECK (card_variant IN ('normal', 'evo', 'hero')),

  CONSTRAINT ck_player_type_cards_nonneg
    CHECK (uses >= 0 AND wins >= 0 AND wins <= uses)
);

-- NEW: Type vs Type matchup matrix (directional, A's perspective vs B)
CREATE TABLE IF NOT EXISTS meta_type_matchups (
  deck_type      TEXT NOT NULL REFERENCES deck_types(deck_type),
  opp_deck_type  TEXT NOT NULL REFERENCES deck_types(deck_type),
  uses           INTEGER NOT NULL DEFAULT 0,
  wins           INTEGER NOT NULL DEFAULT 0,

  PRIMARY KEY (deck_type, opp_deck_type),

  CONSTRAINT ck_meta_type_matchups_nonneg
    CHECK (uses >= 0 AND wins >= 0 AND wins <= uses)

  -- Optional:
  -- ,CONSTRAINT ck_meta_type_matchups_no_mirror
  --   CHECK (deck_type <> opp_deck_type)
);

-- ============================================================
-- 3) Helpful Indexes (MVP)
-- ============================================================

-- Base fact query paths
CREATE INDEX IF NOT EXISTS idx_player_decks_deck_hash
  ON player_decks(deck_hash);

CREATE INDEX IF NOT EXISTS idx_decks_deck_type
  ON decks(deck_type);

CREATE INDEX IF NOT EXISTS idx_deck_cards_card
  ON deck_cards(card_id, card_variant);

-- Rollup query paths
CREATE INDEX IF NOT EXISTS idx_meta_type_deck_ids_deck_hash
  ON meta_type_deck_ids(deck_hash);

CREATE INDEX IF NOT EXISTS idx_meta_type_cards_card
  ON meta_type_cards(card_id, card_variant);

CREATE INDEX IF NOT EXISTS idx_player_type_cards_card
  ON player_type_cards(card_id, card_variant);

-- NEW: matchup query paths
CREATE INDEX IF NOT EXISTS idx_meta_type_matchups_opp
  ON meta_type_matchups(opp_deck_type);

-- ============================================================
-- 4) Snapshot Refresh Helper (optional)
-- ============================================================
-- TRUNCATE in child->parent order to avoid FK issues.
-- (You can TRUNCATE multiple tables at once; Postgres handles FK order with CASCADE,
--  but keeping an explicit order is clearer.)
--
-- TRUNCATE TABLE
--   player_type_cards,
--   meta_type_cards,
--   meta_type_deck_ids,
--   meta_type_matchups,
--   meta_deck_types,
--   player_decks,
--   deck_cards,
--   deck_type_overrides,
--   decks,
--   cards,
--   player,
--   deck_types
-- RESTART IDENTITY;

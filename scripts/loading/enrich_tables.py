#!/usr/bin/env python3
"""
Run all enrichment SQL to keep denormalized columns in sync.

Idempotent — safe to run after every data load. Updates denormalized
columns on players, player_game_stats, games, and team_seasons.

Usage:
	python3 scripts/loading/enrich_tables.py
	python3 scripts/loading/enrich_tables.py --dry-run
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.db import get_connection


STEPS = [
	(
		"Populate players.jersey_number and primary_position",
		"""UPDATE players p
		SET jersey_number = ps.jersey_number, primary_position = ps.primary_position
		FROM (
			SELECT DISTINCT ON (player_id) player_id, jersey_number, primary_position
			FROM player_seasons ORDER BY player_id, season_id DESC
		) ps
		WHERE p.id = ps.player_id""",
	),
	(
		"Populate players.team_id from latest season",
		"""UPDATE players p SET team_id = ps.team_id
		FROM (
			SELECT DISTINCT ON (player_id) player_id, team_id
			FROM player_seasons ORDER BY player_id, season_id DESC
		) ps
		WHERE p.id = ps.player_id""",
	),
	(
		"Populate players season aggregates",
		"""UPDATE players p
		SET season_count = agg.cnt, first_season = agg.min_season, last_season = agg.max_season
		FROM (
			SELECT player_id, COUNT(DISTINCT season_id) as cnt,
				MIN(season_id) as min_season, MAX(season_id) as max_season
			FROM player_seasons GROUP BY player_id
		) agg
		WHERE p.id = agg.player_id""",
	),
	(
		"Populate player_game_stats.player_name",
		"""UPDATE player_game_stats pgs SET player_name = p.name
		FROM players p WHERE pgs.player_id = p.id AND pgs.player_name IS NULL""",
	),
	(
		"Populate player_game_stats.team_name",
		"""UPDATE player_game_stats pgs SET team_name = t.name
		FROM lookup_teams t WHERE pgs.team_id = t.id AND pgs.team_name IS NULL""",
	),
	(
		"Populate games.home_team_name and away_team_name",
		"""UPDATE games g
		SET home_team_name = ht.name, away_team_name = at.name
		FROM lookup_teams ht, lookup_teams at
		WHERE g.home_team_id = ht.id AND g.away_team_id = at.id
		AND (g.home_team_name IS NULL OR g.away_team_name IS NULL)""",
	),
	(
		"Populate games.winning_team_id and losing_team_id",
		"""UPDATE games SET
			winning_team_id = CASE WHEN home_score > away_score THEN home_team_id WHEN away_score > home_score THEN away_team_id ELSE NULL END,
			losing_team_id = CASE WHEN home_score > away_score THEN away_team_id WHEN away_score > home_score THEN home_team_id ELSE NULL END
		WHERE status = 'final' AND winning_team_id IS NULL""",
	),
	(
		"Populate team_seasons",
		"""INSERT INTO team_seasons (team_id, season_id, team_name)
		SELECT DISTINCT pgs.team_id, pgs.season_id, t.name
		FROM player_game_stats pgs
		JOIN lookup_teams t ON pgs.team_id = t.id
		ON CONFLICT (team_id, season_id) DO NOTHING""",
	),
	(
		"Backfill game_plays.season_id",
		"""UPDATE game_plays gp SET season_id = g.season_id
		FROM games g WHERE gp.game_id = g.id AND gp.season_id IS NULL""",
	),
]

ALTER_STEPS = [
	"ALTER TABLE players ADD COLUMN IF NOT EXISTS team_id TEXT",
	"ALTER TABLE players ADD COLUMN IF NOT EXISTS season_count INTEGER DEFAULT 0",
	"ALTER TABLE players ADD COLUMN IF NOT EXISTS first_season TEXT",
	"ALTER TABLE players ADD COLUMN IF NOT EXISTS last_season TEXT",
	"ALTER TABLE player_game_stats ADD COLUMN IF NOT EXISTS player_name TEXT",
	"ALTER TABLE player_game_stats ADD COLUMN IF NOT EXISTS team_name TEXT",
	"ALTER TABLE games ADD COLUMN IF NOT EXISTS home_team_name TEXT",
	"ALTER TABLE games ADD COLUMN IF NOT EXISTS away_team_name TEXT",
	"ALTER TABLE games ADD COLUMN IF NOT EXISTS winning_team_id TEXT",
	"ALTER TABLE games ADD COLUMN IF NOT EXISTS losing_team_id TEXT",
	"ALTER TABLE game_plays ADD COLUMN IF NOT EXISTS season_id TEXT",
]

INDEX_STEPS = [
	"CREATE INDEX IF NOT EXISTS idx_pgs_season_team ON player_game_stats (season_id, team_id)",
	"CREATE INDEX IF NOT EXISTS idx_pgs_season_player ON player_game_stats (season_id, player_id)",
	"CREATE INDEX IF NOT EXISTS idx_games_season_status ON games (season_id, status)",
	"CREATE INDEX IF NOT EXISTS idx_player_seasons_player_desc ON player_seasons (player_id, season_id DESC)",
]


def run_enrichment(dry_run: bool = False):
	"""Run all enrichment steps."""
	if dry_run:
		print("DRY RUN: Would execute the following steps:")
		for desc, _ in STEPS:
			print(f"  - {desc}")
		return

	conn = get_connection()
	try:
		with conn.cursor() as cur:
			# Ensure columns exist
			print("Ensuring columns exist...")
			for sql in ALTER_STEPS:
				cur.execute(sql)
			conn.commit()

			# Run enrichment updates
			for desc, sql in STEPS:
				print(f"  {desc}...", end=" ", flush=True)
				cur.execute(sql)
				print(f"({cur.rowcount} rows)")
				conn.commit()

			# Ensure indexes exist
			print("Ensuring indexes exist...")
			for sql in INDEX_STEPS:
				cur.execute(sql)
			conn.commit()

		print("Enrichment complete.")
	except Exception:
		conn.rollback()
		raise
	finally:
		conn.close()


def main():
	parser = argparse.ArgumentParser(description="Run table enrichment SQL")
	parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
	parser.add_argument("--season", help="Ignored (accepted for sync_daily.py compat)")
	parser.add_argument("--division", type=int, help="Ignored (accepted for sync_daily.py compat)")
	args = parser.parse_args()

	run_enrichment(args.dry_run)


if __name__ == "__main__":
	main()

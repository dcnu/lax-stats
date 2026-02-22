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
		WHERE status = 'final'""",
	),
	(
		"Populate games running records",
		"""WITH game_results AS (
			SELECT id, season_id, game_date,
				home_team_id, away_team_id, home_score, away_score
			FROM games WHERE status = 'final'
		),
		team_games AS (
			SELECT id, season_id, game_date, team_id,
				CASE WHEN team_id = home_team_id
					THEN CASE WHEN home_score > away_score THEN 1 ELSE 0 END
					ELSE CASE WHEN away_score > home_score THEN 1 ELSE 0 END
				END AS won,
				CASE WHEN team_id = home_team_id
					THEN CASE WHEN home_score < away_score THEN 1 ELSE 0 END
					ELSE CASE WHEN away_score < home_score THEN 1 ELSE 0 END
				END AS lost
			FROM game_results
			CROSS JOIN LATERAL (VALUES (home_team_id), (away_team_id)) AS t(team_id)
		),
		running AS (
			SELECT id, team_id,
				SUM(won) OVER (PARTITION BY season_id, team_id ORDER BY game_date ROWS UNBOUNDED PRECEDING) AS wins,
				SUM(lost) OVER (PARTITION BY season_id, team_id ORDER BY game_date ROWS UNBOUNDED PRECEDING) AS losses
			FROM team_games
		)
		UPDATE games g SET
			home_team_wins = rh.wins,
			home_team_losses = rh.losses,
			away_team_wins = ra.wins,
			away_team_losses = ra.losses
		FROM running rh, running ra
		WHERE rh.id = g.id AND rh.team_id = g.home_team_id
		  AND ra.id = g.id AND ra.team_id = g.away_team_id""",
	),
	(
		"Populate team_seasons",
		"""INSERT INTO team_seasons (team_id, season_id, team_name)
		SELECT DISTINCT g.home_team_id, g.season_id, lt.name
		FROM games g JOIN lookup_teams lt ON lt.id = g.home_team_id
		UNION
		SELECT DISTINCT g.away_team_id, g.season_id, lt.name
		FROM games g JOIN lookup_teams lt ON lt.id = g.away_team_id
		UNION
		SELECT DISTINCT pgs.team_id, pgs.season_id, t.name
		FROM player_game_stats pgs JOIN lookup_teams t ON pgs.team_id = t.id
		ON CONFLICT (team_id, season_id) DO NOTHING""",
	),
	(
		"Backfill game_plays.season_id",
		"""UPDATE game_plays gp SET season_id = g.season_id
		FROM games g WHERE gp.game_id = g.id AND gp.season_id IS NULL""",
	),
	(
		"Populate player_game_stats.opponent_id",
		"""UPDATE player_game_stats pgs
		SET opponent_id = CASE
			WHEN pgs.team_id = g.home_team_id THEN g.away_team_id
			WHEN pgs.team_id = g.away_team_id THEN g.home_team_id
		END
		FROM games g
		WHERE pgs.game_id = g.id AND pgs.opponent_id IS NULL""",
	),
	(
		"Rebuild player_season_stats",
		"""DELETE FROM player_season_stats;
		INSERT INTO player_season_stats (
			player_id, team_id, season_id, division_id,
			player_name, team_name, primary_position,
			games_played, goals, assists, points,
			shots, shots_on_goal, ground_balls,
			turnovers, caused_turnovers,
			faceoff_wins, faceoffs_taken,
			minutes_played, goalie_minutes, goals_allowed, saves,
			points_per_game, goals_per_game,
			shooting_pct, faceoff_pct, save_pct
		)
		SELECT
			pgs.player_id, pgs.team_id, pgs.season_id,
			MAX(pgs.division_id),
			MAX(pgs.player_name), MAX(pgs.team_name),
			ps.primary_position,
			COUNT(DISTINCT pgs.game_id),
			SUM(pgs.goals), SUM(pgs.assists), SUM(pgs.points),
			SUM(pgs.shots), SUM(pgs.shots_on_goal), SUM(pgs.ground_balls),
			SUM(pgs.turnovers), SUM(pgs.caused_turnovers),
			SUM(pgs.faceoff_wins), SUM(pgs.faceoffs_taken),
			SUM(COALESCE(pgs.minutes_played, 0)),
			SUM(COALESCE(pgs.goalie_minutes, 0)),
			SUM(pgs.goals_allowed), SUM(pgs.saves),
			ROUND(SUM(pgs.points)::NUMERIC / NULLIF(COUNT(DISTINCT pgs.game_id), 0), 2),
			ROUND(SUM(pgs.goals)::NUMERIC / NULLIF(COUNT(DISTINCT pgs.game_id), 0), 2),
			ROUND(SUM(pgs.goals)::NUMERIC / NULLIF(SUM(pgs.shots), 0), 4),
			ROUND(SUM(pgs.faceoff_wins)::NUMERIC / NULLIF(SUM(pgs.faceoffs_taken), 0), 4),
			ROUND(SUM(pgs.saves)::NUMERIC / NULLIF(SUM(pgs.saves) + SUM(pgs.goals_allowed), 0), 4)
		FROM player_game_stats pgs
		JOIN players p ON p.id = pgs.player_id
		LEFT JOIN (
			SELECT DISTINCT ON (player_id) player_id, primary_position
			FROM player_seasons ORDER BY player_id, season_id DESC
		) ps ON pgs.player_id = ps.player_id
		GROUP BY pgs.player_id, pgs.team_id, pgs.season_id, ps.primary_position""",
	),
	(
		"Rebuild team_season_stats",
		"""DELETE FROM team_season_stats;
		INSERT INTO team_season_stats (
			team_id, season_id, division_id, team_name,
			wins, losses, ties, games_played,
			goals_for, goals_against, goal_diff,
			total_shots, total_shots_on_goal, total_ground_balls,
			total_turnovers, total_caused_turnovers,
			total_faceoff_wins, total_faceoffs_taken, total_saves,
			win_pct, shooting_pct, faceoff_pct, save_pct
		)
		SELECT
			ts.team_id, ts.season_id,
			COALESCE(agg.division_id, 1),
			ts.team_name,
			COALESCE(wl.wins, 0),
			COALESCE(wl.losses, 0),
			COALESCE(wl.ties, 0),
			COALESCE(wl.wins, 0) + COALESCE(wl.losses, 0) + COALESCE(wl.ties, 0),
			COALESCE(wl.goals_for, 0),
			COALESCE(wl.goals_against, 0),
			COALESCE(wl.goals_for, 0) - COALESCE(wl.goals_against, 0),
			COALESCE(agg.total_shots, 0),
			COALESCE(agg.total_shots_on_goal, 0),
			COALESCE(agg.total_ground_balls, 0),
			COALESCE(agg.total_turnovers, 0),
			COALESCE(agg.total_caused_turnovers, 0),
			COALESCE(agg.total_faceoff_wins, 0),
			COALESCE(agg.total_faceoffs_taken, 0),
			COALESCE(agg.total_saves, 0),
			ROUND(COALESCE(wl.wins, 0)::NUMERIC / NULLIF(COALESCE(wl.wins, 0) + COALESCE(wl.losses, 0) + COALESCE(wl.ties, 0), 0), 4),
			ROUND(COALESCE(agg.total_goals, 0)::NUMERIC / NULLIF(COALESCE(agg.total_shots, 0), 0), 4),
			ROUND(COALESCE(agg.total_faceoff_wins, 0)::NUMERIC / NULLIF(COALESCE(agg.total_faceoffs_taken, 0), 0), 4),
			ROUND(COALESCE(agg.total_saves, 0)::NUMERIC / NULLIF(COALESCE(agg.total_saves, 0) + COALESCE(agg.total_goals_allowed, 0), 0), 4)
		FROM team_seasons ts
		LEFT JOIN (
			SELECT
				team_id, season_id,
				SUM(CASE WHEN is_home THEN CASE WHEN home_score > away_score THEN 1 ELSE 0 END
					ELSE CASE WHEN away_score > home_score THEN 1 ELSE 0 END END) as wins,
				SUM(CASE WHEN is_home THEN CASE WHEN home_score < away_score THEN 1 ELSE 0 END
					ELSE CASE WHEN away_score < home_score THEN 1 ELSE 0 END END) as losses,
				SUM(CASE WHEN home_score = away_score THEN 1 ELSE 0 END) as ties,
				SUM(CASE WHEN is_home THEN home_score ELSE away_score END) as goals_for,
				SUM(CASE WHEN is_home THEN away_score ELSE home_score END) as goals_against
			FROM (
				SELECT home_team_id as team_id, season_id, home_score, away_score, true as is_home
				FROM games WHERE status = 'final'
				UNION ALL
				SELECT away_team_id as team_id, season_id, home_score, away_score, false as is_home
				FROM games WHERE status = 'final'
			) game_rows
			GROUP BY team_id, season_id
		) wl ON ts.team_id = wl.team_id AND ts.season_id = wl.season_id
		LEFT JOIN (
			SELECT
				team_id, season_id,
				MAX(division_id) as division_id,
				SUM(goals) as total_goals,
				SUM(shots) as total_shots,
				SUM(shots_on_goal) as total_shots_on_goal,
				SUM(ground_balls) as total_ground_balls,
				SUM(turnovers) as total_turnovers,
				SUM(caused_turnovers) as total_caused_turnovers,
				SUM(faceoff_wins) as total_faceoff_wins,
				SUM(faceoffs_taken) as total_faceoffs_taken,
				SUM(saves) as total_saves,
				SUM(goals_allowed) as total_goals_allowed
			FROM player_game_stats
			GROUP BY team_id, season_id
		) agg ON ts.team_id = agg.team_id AND ts.season_id = agg.season_id""",
	),
	(
		"Populate team_season_stats OWP and OOWP",
		"""WITH team_records AS (
			SELECT team_id, season_id, win_pct
			FROM team_season_stats
			WHERE games_played > 0
		),
		matchups AS (
			SELECT season_id, home_team_id AS team_id, away_team_id AS opp_id
			FROM games WHERE status = 'final'
			UNION ALL
			SELECT season_id, away_team_id AS team_id, home_team_id AS opp_id
			FROM games WHERE status = 'final'
		),
		owp AS (
			SELECT m.team_id, m.season_id,
				ROUND(AVG(tr.win_pct), 4) AS opp_win_pct
			FROM matchups m
			JOIN team_records tr ON m.opp_id = tr.team_id AND m.season_id = tr.season_id
			GROUP BY m.team_id, m.season_id
		),
		oowp AS (
			SELECT m.team_id, m.season_id,
				ROUND(AVG(o.opp_win_pct), 4) AS opp_opp_win_pct
			FROM matchups m
			JOIN owp o ON m.opp_id = o.team_id AND m.season_id = o.season_id
			GROUP BY m.team_id, m.season_id
		)
		UPDATE team_season_stats tss SET
			opp_win_pct = o.opp_win_pct,
			opp_opp_win_pct = oo.opp_opp_win_pct
		FROM owp o
		LEFT JOIN oowp oo ON o.team_id = oo.team_id AND o.season_id = oo.season_id
		WHERE tss.team_id = o.team_id AND tss.season_id = o.season_id""",
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
	"ALTER TABLE player_game_stats ADD COLUMN IF NOT EXISTS opponent_id TEXT",
	"ALTER TABLE games ADD COLUMN IF NOT EXISTS home_team_wins SMALLINT",
	"ALTER TABLE games ADD COLUMN IF NOT EXISTS home_team_losses SMALLINT",
	"ALTER TABLE games ADD COLUMN IF NOT EXISTS away_team_wins SMALLINT",
	"ALTER TABLE games ADD COLUMN IF NOT EXISTS away_team_losses SMALLINT",
	"ALTER TABLE team_season_stats ADD COLUMN IF NOT EXISTS opp_win_pct NUMERIC",
	"ALTER TABLE team_season_stats ADD COLUMN IF NOT EXISTS opp_opp_win_pct NUMERIC",
]

INDEX_STEPS = [
	"CREATE INDEX IF NOT EXISTS idx_pgs_season_team ON player_game_stats (season_id, team_id)",
	"CREATE INDEX IF NOT EXISTS idx_pgs_season_player ON player_game_stats (season_id, player_id)",
	"CREATE INDEX IF NOT EXISTS idx_games_season_status ON games (season_id, status)",
	"CREATE INDEX IF NOT EXISTS idx_player_seasons_player_desc ON player_seasons (player_id, season_id DESC)",
	"CREATE INDEX IF NOT EXISTS idx_pgs_opponent ON player_game_stats (opponent_id)",
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

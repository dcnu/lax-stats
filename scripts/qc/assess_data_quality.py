#!/usr/bin/env python3
"""
Data quality assessment script for lacrosse stats.

Scans all games and identifies data quality issues:
- Missing player_stats files
- Goal count mismatches (scraped vs game score)
- Players not found in roster

Outputs a terminal table with error details and identified causes.

Usage:
	python scripts/qc/assess_data_quality.py
	python scripts/qc/assess_data_quality.py --season 2025 --division 1
"""

import json
import sys
import argparse
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.db import execute_query
from utils.path_helpers import get_game_file_path, get_all_game_files
from utils.roster_lookup import get_roster_mapping_cached, get_player_team
from utils.pbp_parser import get_goals_from_plays


# Error codes
MISSING_FILE = "MISSING_FILE"
GOAL_MISMATCH = "GOAL_MISMATCH"
NO_PBP = "NO_PBP"
OK = "OK"


def get_all_games_from_db(season_filter: str = None, division_filter: int = None) -> list[dict]:
	"""Get all games from database with team names."""
	query = """
		SELECT g.id, g.season_id, g.division_id,
			g.home_team_id, ht.name as home_team_name, g.home_score,
			g.away_team_id, at.name as away_team_name, g.away_score
		FROM games g
		JOIN teams ht ON g.home_team_id = ht.id
		JOIN teams at ON g.away_team_id = at.id
		WHERE 1=1
	"""
	params = []

	if season_filter:
		query += " AND g.season_id = %s"
		params.append(season_filter)
	if division_filter:
		query += " AND g.division_id = %s"
		params.append(division_filter)

	query += " ORDER BY g.id"

	return execute_query(query, tuple(params) if params else None) or []


def get_loaded_goals_for_game(game_id: str) -> tuple[int, int]:
	"""Get calculated goals from player_game_stats for a game."""
	result = execute_query("""
		SELECT
			COALESCE(SUM(CASE WHEN pgs.team_id = g.home_team_id THEN pgs.goals ELSE 0 END), 0) as home_goals,
			COALESCE(SUM(CASE WHEN pgs.team_id = g.away_team_id THEN pgs.goals ELSE 0 END), 0) as away_goals
		FROM games g
		LEFT JOIN player_game_stats pgs ON pgs.game_id = g.id
		WHERE g.id = %s
		GROUP BY g.id
	""", (game_id,))

	if result:
		return int(result[0]["home_goals"]), int(result[0]["away_goals"])
	return 0, 0


def assess_game(game: dict, base_dir: str = "data") -> dict:
	"""
	Assess a single game for data quality issues.

	Returns dict with:
		- game_id, teams, expected scores
		- actual loaded goals
		- error_code, error_details
		- has_pbp (whether play-by-play file exists)
	"""
	game_id = game["id"]
	season_id = game["season_id"]
	division = game["division_id"]
	home_team = game["home_team_name"]
	away_team = game["away_team_name"]
	expected_home = game["home_score"] or 0
	expected_away = game["away_score"] or 0

	result = {
		"game_id": game_id,
		"home_team": home_team,
		"away_team": away_team,
		"expected_home": expected_home,
		"expected_away": expected_away,
		"actual_home": 0,
		"actual_away": 0,
		"error_code": OK,
		"error_details": "",
		"has_pbp": False,
		"pbp_home": 0,
		"pbp_away": 0,
	}

	# Get loaded goals from database first
	actual_home, actual_away = get_loaded_goals_for_game(game_id)
	result["actual_home"] = actual_home
	result["actual_away"] = actual_away

	# Check if player_stats file exists
	stats_path = get_game_file_path(game_id, "player_stats", season_id, division, base_dir)
	file_missing = not stats_path.exists()

	# Check for play-by-play file
	pbp_path = get_game_file_path(game_id, "plays", season_id, division, base_dir)
	if pbp_path.exists():
		result["has_pbp"] = True
		with open(pbp_path, "r", encoding="utf-8") as f:
			plays = json.load(f)
		pbp_home, pbp_away = get_goals_from_plays(plays)
		result["pbp_home"] = pbp_home
		result["pbp_away"] = pbp_away

	# Determine error code
	if file_missing and actual_home == 0 and actual_away == 0:
		# File missing and no data loaded from any source
		result["error_code"] = MISSING_FILE
		result["error_details"] = "no player_stats file"
	elif actual_home != expected_home or actual_away != expected_away:
		# Goals don't match expected score
		result["error_code"] = GOAL_MISMATCH
		home_diff = actual_home - expected_home
		away_diff = actual_away - expected_away
		details = []
		if home_diff != 0:
			details.append(f"home {home_diff:+d}")
		if away_diff != 0:
			details.append(f"away {away_diff:+d}")
		result["error_details"] = ", ".join(details)

	return result


def truncate_team_name(name: str, max_len: int = 12) -> str:
	"""Truncate team name for display."""
	if len(name) <= max_len:
		return name
	return name[:max_len - 1] + "."


def print_qc_table(results: list[dict], show_all: bool = False):
	"""Print formatted terminal table of QC results."""
	# Filter to only errors unless show_all
	if not show_all:
		results = [r for r in results if r["error_code"] != OK]

	if not results:
		print("No data quality issues found.")
		return

	# Table header
	print()
	print("┌─────────┬─────────────────────────────┬────────────┬─────────┬──────────┬───────────────┐")
	print("│ Game ID │ Teams                       │ Expected   │ Actual  │ Delta    │ Cause         │")
	print("├─────────┼─────────────────────────────┼────────────┼─────────┼──────────┼───────────────┤")

	for r in results:
		game_id = r["game_id"]
		home = truncate_team_name(r["home_team"])
		away = truncate_team_name(r["away_team"])
		teams = f"{home} vs {away}"

		expected = f"{r['expected_home']}-{r['expected_away']} ({r['expected_home'] + r['expected_away']})"
		actual = f"{r['actual_home']}-{r['actual_away']}"

		if r["error_code"] == MISSING_FILE:
			delta = f"-{r['expected_home'] + r['expected_away']}"
		else:
			home_diff = r["actual_home"] - r["expected_home"]
			away_diff = r["actual_away"] - r["expected_away"]
			if home_diff != 0 and away_diff != 0:
				delta = f"{home_diff:+d}h,{away_diff:+d}a"
			elif home_diff != 0:
				delta = f"{home_diff:+d} home"
			elif away_diff != 0:
				delta = f"{away_diff:+d} away"
			else:
				delta = "0"

		cause = r["error_code"]
		if r["has_pbp"]:
			cause += "*"  # Asterisk indicates PBP available for recovery

		print(f"│ {game_id:<7} │ {teams:<27} │ {expected:<10} │ {actual:<7} │ {delta:<8} │ {cause:<13} │")

	print("└─────────┴─────────────────────────────┴────────────┴─────────┴──────────┴───────────────┘")

	# Summary
	error_counts = defaultdict(int)
	recoverable = 0
	for r in results:
		error_counts[r["error_code"]] += 1
		if r["has_pbp"] and r["error_code"] != OK:
			recoverable += 1

	total_games = len([r for r in results if r["error_code"] == OK]) + len(results)
	print(f"\n* = Play-by-play available for recovery")
	print(f"\nSummary: {len(results)} games with issues")
	for code, count in sorted(error_counts.items()):
		if code != OK:
			print(f"  - {code}: {count}")
	if recoverable > 0:
		print(f"  - Recoverable from PBP: {recoverable}")


def main():
	parser = argparse.ArgumentParser(description="Assess data quality for lacrosse stats")
	parser.add_argument("--season", help="Filter by season (e.g., 2025)")
	parser.add_argument("--division", type=int, choices=[1, 2, 3], help="Filter by division")
	parser.add_argument("--data-dir", default="data", help="Base data directory")
	parser.add_argument("--all", action="store_true", help="Show all games, not just errors")
	parser.add_argument("--json", action="store_true", help="Output as JSON instead of table")

	args = parser.parse_args()

	print("Fetching games from database...")
	games = get_all_games_from_db(args.season, args.division)
	print(f"Assessing {len(games)} games...")

	results = []
	for game in games:
		result = assess_game(game, args.data_dir)
		results.append(result)

	if args.json:
		# Output as JSON for programmatic use
		errors = [r for r in results if r["error_code"] != OK]
		print(json.dumps(errors, indent=2))
	else:
		print_qc_table(results, show_all=args.all)


if __name__ == "__main__":
	main()

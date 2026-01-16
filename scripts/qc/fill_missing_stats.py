#!/usr/bin/env python3
"""
Fill missing player stats from play-by-play data.

Reconstructs player_game_stats records for games where:
- player_stats.json file is missing (MISSING_FILE)
- Goal counts don't match game scores (GOAL_MISMATCH)

Usage:
	python scripts/qc/fill_missing_stats.py --game 6380961
	python scripts/qc/fill_missing_stats.py --all-missing
	python scripts/qc/fill_missing_stats.py --all-missing --dry-run
"""

import json
import sys
import argparse
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.db import get_cursor, execute_query
from utils.path_helpers import get_game_file_path
from utils.roster_lookup import load_roster_mapping, get_player_team
from utils.pbp_parser import parse_plays, match_player_to_roster


def get_game_info(game_id: str) -> dict | None:
	"""Get game info from database."""
	result = execute_query("""
		SELECT g.id, g.season_id, g.division_id,
			g.home_team_id, ht.name as home_team_name,
			g.away_team_id, at.name as away_team_name,
			g.home_score, g.away_score
		FROM games g
		JOIN teams ht ON g.home_team_id = ht.id
		JOIN teams at ON g.away_team_id = at.id
		WHERE g.id = %s
	""", (game_id,))
	return result[0] if result else None


def load_roster_for_teams(season_id: str, division: int, home_team_id: str, away_team_id: str, base_dir: str = "data") -> dict:
	"""
	Load roster mapping and filter to just the two teams in this game.

	Returns: {playerID: {name, teamID}}
	"""
	roster_map = load_roster_mapping(season_id, division, base_dir)

	# Build a more detailed roster with names for matching
	raw_path = Path(base_dir) / season_id / f"division{division}" / "raw" / "rosters.json"
	if not raw_path.exists():
		return {}

	with open(raw_path, "r", encoding="utf-8") as f:
		rosters = json.load(f)

	result = {}
	for team in rosters:
		team_id = str(team.get("teamID", ""))
		if team_id not in (home_team_id, away_team_id):
			continue

		for player in team.get("players", []):
			player_id = player.get("playerID")
			if player_id:
				try:
					result[int(player_id)] = {
						"name": player.get("name", ""),
						"teamID": team_id,
					}
				except (ValueError, TypeError):
					continue

	return result


def reconstruct_stats_from_pbp(game_id: str, season_id: str, division: int,
							   home_team_id: str, away_team_id: str,
							   expected_home_goals: int, expected_away_goals: int,
							   base_dir: str = "data") -> list[dict]:
	"""
	Reconstruct player stats from play-by-play data.

	Returns list of stat records ready for database insertion.
	"""
	# Load play-by-play
	pbp_path = get_game_file_path(game_id, "plays", season_id, division, base_dir)
	if not pbp_path.exists():
		print(f"Error: No play-by-play file for game {game_id}", file=sys.stderr)
		return []

	with open(pbp_path, "r", encoding="utf-8") as f:
		plays = json.load(f)

	# Parse plays to extract stats (with column swap detection)
	pbp_stats = parse_plays(plays, home_team_id, away_team_id, expected_home_goals, expected_away_goals)

	# Load roster for player ID matching
	roster = load_roster_for_teams(season_id, division, home_team_id, away_team_id, base_dir)

	# Convert to database records
	records = []
	unmatched = []

	for (player_name, team_id), stats in pbp_stats.items():
		# Try to match player name to roster
		player_id = match_player_to_roster(player_name, roster)

		if player_id is None:
			unmatched.append((player_name, team_id, stats))
			continue

		# Get player info from roster
		player_info = roster.get(player_id, {})

		record = {
			"game_id": game_id,
			"player_id": player_id,
			"team_id": team_id,
			"season_id": season_id,
			"division_id": division,
			"jersey_number": None,  # Not available from PBP
			"position": None,  # Not available from PBP
			"minutes_played": None,
			"goals": stats.get("goals", 0),
			"assists": stats.get("assists", 0),
			"points": stats.get("goals", 0) + stats.get("assists", 0),
			"shots": stats.get("shots", 0),
			"shots_on_goal": stats.get("shots_on_goal", 0),
			"ground_balls": stats.get("ground_balls", 0),
			"turnovers": stats.get("turnovers", 0),
			"caused_turnovers": stats.get("caused_turnovers", 0),
			"faceoff_wins": stats.get("faceoff_wins", 0),
			"faceoffs_taken": stats.get("faceoffs_taken", 0),
			"goalie_minutes": None,
			"goals_allowed": 0,
			"gaa": None,
			"saves": stats.get("saves", 0),
			"save_percentage": None,
		}
		records.append(record)

	if unmatched:
		print(f"Warning: {len(unmatched)} players could not be matched to roster:", file=sys.stderr)
		for name, team_id, stats in unmatched[:5]:
			goals = stats.get("goals", 0)
			if goals > 0:
				print(f"  - {name} (team {team_id}): {goals} goals", file=sys.stderr)

	return records


def insert_stats_to_database(records: list[dict], dry_run: bool = False):
	"""Insert reconstructed stats into database."""
	if not records:
		print("No records to insert")
		return

	if dry_run:
		print(f"DRY RUN: Would insert {len(records)} player game stats:")
		goals_total = sum(r["goals"] for r in records)
		assists_total = sum(r["assists"] for r in records)
		print(f"  Total goals: {goals_total}, assists: {assists_total}")
		for r in records[:5]:
			if r["goals"] > 0 or r["assists"] > 0:
				print(f"  - Player {r['player_id']}: {r['goals']}G {r['assists']}A")
		if len(records) > 5:
			print(f"  ... and {len(records) - 5} more players")
		return

	query = """
		INSERT INTO player_game_stats (
			game_id, player_id, team_id, season_id, division_id,
			jersey_number, position, minutes_played,
			goals, assists, points, shots, shots_on_goal,
			ground_balls, turnovers, caused_turnovers,
			faceoff_wins, faceoffs_taken,
			goalie_minutes, goals_allowed, gaa, saves, save_percentage
		)
		VALUES (%(game_id)s, %(player_id)s, %(team_id)s, %(season_id)s, %(division_id)s,
			%(jersey_number)s, %(position)s, %(minutes_played)s,
			%(goals)s, %(assists)s, %(points)s, %(shots)s, %(shots_on_goal)s,
			%(ground_balls)s, %(turnovers)s, %(caused_turnovers)s,
			%(faceoff_wins)s, %(faceoffs_taken)s,
			%(goalie_minutes)s, %(goals_allowed)s, %(gaa)s, %(saves)s, %(save_percentage)s)
		ON CONFLICT (game_id, player_id, position) DO UPDATE SET
			goals = EXCLUDED.goals,
			assists = EXCLUDED.assists,
			points = EXCLUDED.points,
			shots = EXCLUDED.shots,
			shots_on_goal = EXCLUDED.shots_on_goal,
			ground_balls = EXCLUDED.ground_balls,
			turnovers = EXCLUDED.turnovers,
			caused_turnovers = EXCLUDED.caused_turnovers,
			faceoff_wins = EXCLUDED.faceoff_wins,
			faceoffs_taken = EXCLUDED.faceoffs_taken,
			saves = EXCLUDED.saves
	"""

	inserted = 0
	with get_cursor() as cursor:
		for record in records:
			cursor.execute(query, record)
			inserted += 1

	print(f"Inserted {inserted} player game stats")


def fill_game(game_id: str, base_dir: str = "data", dry_run: bool = False) -> bool:
	"""Fill stats for a single game from play-by-play."""
	game = get_game_info(game_id)
	if not game:
		print(f"Error: Game {game_id} not found in database", file=sys.stderr)
		return False

	print(f"Processing game {game_id}: {game['home_team_name']} vs {game['away_team_name']}")

	records = reconstruct_stats_from_pbp(
		game_id=game_id,
		season_id=game["season_id"],
		division=game["division_id"],
		home_team_id=game["home_team_id"],
		away_team_id=game["away_team_id"],
		expected_home_goals=game["home_score"] or 0,
		expected_away_goals=game["away_score"] or 0,
		base_dir=base_dir,
	)

	if not records:
		print("No stats could be reconstructed")
		return False

	# Summary
	home_goals = sum(r["goals"] for r in records if r["team_id"] == game["home_team_id"])
	away_goals = sum(r["goals"] for r in records if r["team_id"] == game["away_team_id"])
	print(f"Reconstructed: {home_goals}-{away_goals} (expected: {game['home_score']}-{game['away_score']})")

	insert_stats_to_database(records, dry_run)
	return True


def get_games_with_missing_files(season: str = None, division: int = None) -> list[str]:
	"""Get list of game IDs that have missing player_stats files."""
	# This requires checking the filesystem
	from utils.path_helpers import get_all_game_files

	missing = []
	game_files = get_all_game_files(season, division)

	for season_id, div, game_id, info_path in game_files:
		stats_path = info_path.parent / f"game_{game_id}_player_stats.json"
		pbp_path = info_path.parent / f"game_{game_id}_plays.json"

		if not stats_path.exists() and pbp_path.exists():
			missing.append(game_id)

	return missing


def main():
	parser = argparse.ArgumentParser(description="Fill missing stats from play-by-play")
	parser.add_argument("--game", help="Fill specific game ID")
	parser.add_argument("--all-missing", action="store_true", help="Fill all games with missing files")
	parser.add_argument("--season", help="Filter by season (with --all-missing)")
	parser.add_argument("--division", type=int, choices=[1, 2, 3], help="Filter by division")
	parser.add_argument("--data-dir", default="data", help="Base data directory")
	parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")

	args = parser.parse_args()

	if args.game:
		fill_game(args.game, args.data_dir, args.dry_run)
	elif args.all_missing:
		missing = get_games_with_missing_files(args.season, args.division)
		print(f"Found {len(missing)} games with missing player_stats files")

		for game_id in missing:
			print()
			fill_game(game_id, args.data_dir, args.dry_run)
	else:
		parser.print_help()
		print("\nError: Must specify --game or --all-missing", file=sys.stderr)
		sys.exit(1)


if __name__ == "__main__":
	main()

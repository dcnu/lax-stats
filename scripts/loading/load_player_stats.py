#!/usr/bin/env python3
"""
Load player game statistics from scraped files into local PostgreSQL.

Processes all game_*_player_stats.json files and loads individual player
statistics per game, with time fields converted to seconds.

Usage:
	python3 scripts/loading/load_player_stats.py
	python3 scripts/loading/load_player_stats.py --season 2025 --division 1
	python3 scripts/loading/load_player_stats.py --dry-run
"""

import json
import sys
import argparse
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.db import get_cursor, parse_time_to_seconds, execute_query
from utils.path_helpers import get_all_season_dirs
from utils.roster_lookup import get_roster_mapping_cached, get_player_team


def safe_int(value, default=0):
	"""Safely convert value to int."""
	if value is None or value == "":
		return default
	try:
		return int(value)
	except (ValueError, TypeError):
		return default


def safe_float(value, default=None):
	"""Safely convert value to float."""
	if value is None or value == "":
		return default
	try:
		return float(value)
	except (ValueError, TypeError):
		return default


def get_game_metadata(game_id: str):
	"""Get season_id, home_team_id, away_team_id for a game."""
	result = execute_query(
		"SELECT season_id, home_team_id, away_team_id FROM games WHERE id = %s",
		(game_id,),
	)
	if result:
		return result[0]
	return None


def extract_player_stats(data_dir: str = "data", season_filter: str = None, division_filter: int = None):
	"""Extract player game stats from all player stats files."""
	data_path = Path(data_dir)
	if not data_path.exists():
		print(f"Error: Data directory {data_dir} not found", file=sys.stderr)
		sys.exit(1)

	stats_files = []

	if season_filter:
		seasons = [(season_filter, data_path / season_filter)]
	else:
		seasons = get_all_season_dirs(data_dir)

	if not seasons:
		if (data_path / "games").exists():
			seasons = [("2025", data_path)]
		else:
			print(f"Error: No season directories found", file=sys.stderr)
			sys.exit(1)

	for season_id, season_path in seasons:
		division_dirs = [d for d in season_path.iterdir() if d.is_dir() and d.name.startswith("division")]

		if division_dirs:
			for div_dir in division_dirs:
				try:
					division = int(div_dir.name.replace("division", ""))
					if division_filter and division != division_filter:
						continue
					games_dir = div_dir / "games"
					if games_dir.exists():
						for f in games_dir.glob("game_*_player_stats.json"):
							stats_files.append((season_id, division, f))
				except ValueError:
					continue
		else:
			games_dir = season_path / "games"
			if games_dir.exists():
				for f in games_dir.glob("game_*_player_stats.json"):
					stats_files.append((season_id, division_filter or 1, f))

	if not stats_files:
		print(f"Error: No player stats files found", file=sys.stderr)
		sys.exit(1)

	print(f"Processing {len(stats_files)} player stats files...")

	player_stats = []
	game_cache = {}

	for season_id, division, file_path in stats_files:
		try:
			# Extract game ID from filename
			game_id = file_path.stem.split("_")[1]

			# Get game metadata
			if game_id not in game_cache:
				game_cache[game_id] = get_game_metadata(game_id)

			game_meta = game_cache[game_id]
			if not game_meta:
				print(f"Warning: No game metadata for {game_id}, skipping", file=sys.stderr)
				continue

			home_team_id = game_meta["home_team_id"]
			away_team_id = game_meta["away_team_id"]

			with open(file_path, "r", encoding="utf-8") as f:
				players_data = json.load(f)

			# Load roster mapping for team assignment
			roster_map = get_roster_mapping_cached(season_id, division)

			for player_data in players_data:
				if "playerId" not in player_data or "name" not in player_data:
					continue

				player_id = player_data["playerId"]

				# Look up team from roster (source of truth)
				team_id = get_player_team(player_id, roster_map, home_team_id, away_team_id)
				if team_id is None:
					player_name = player_data.get("name", "Unknown")
					print(f"Warning: Player {player_id} ({player_name}) not found in roster for game {game_id}, skipping", file=sys.stderr)
					continue

				# Check if goalie stats
				is_goalie_stat = "G Min" in player_data

				if is_goalie_stat:
					stat = {
						"game_id": game_id,
						"player_id": player_id,
						"season_id": season_id,
						"division_id": division,
						"team_id": team_id,
						"jersey_number": player_data.get("jersey"),
						"position": player_data.get("position"),
						"minutes_played": None,
						"goals": 0,
						"assists": 0,
						"points": 0,
						"shots": 0,
						"shots_on_goal": 0,
						"ground_balls": 0,
						"turnovers": 0,
						"caused_turnovers": 0,
						"faceoff_wins": 0,
						"faceoffs_taken": 0,
						# Convert goalie minutes to seconds
						"goalie_minutes": parse_time_to_seconds(player_data.get("G Min")),
						"goals_allowed": safe_int(player_data.get("Goals Allowed")),
						"gaa": safe_float(player_data.get("GAA")),
						"saves": safe_int(player_data.get("Saves")),
						"save_percentage": safe_float(player_data.get("Save Pct")),
					}
				else:
					stat = {
						"game_id": game_id,
						"player_id": player_id,
						"season_id": season_id,
						"division_id": division,
						"team_id": team_id,
						"jersey_number": player_data.get("jersey"),
						"position": player_data.get("position"),
						# Convert minutes to seconds
						"minutes_played": parse_time_to_seconds(player_data.get("Min")),
						"goals": safe_int(player_data.get("Goals")),
						"assists": safe_int(player_data.get("Assists")),
						"points": safe_int(player_data.get("Points")),
						"shots": safe_int(player_data.get("Shots")),
						"shots_on_goal": safe_int(player_data.get("SOG")),
						"ground_balls": safe_int(player_data.get("GB")),
						"turnovers": safe_int(player_data.get("TO")),
						"caused_turnovers": safe_int(player_data.get("CT")),
						"faceoff_wins": safe_int(player_data.get("FO_Won")),
						"faceoffs_taken": safe_int(player_data.get("FOs_Taken")),
						"goalie_minutes": None,
						"goals_allowed": 0,
						"gaa": None,
						"saves": 0,
						"save_percentage": None,
					}

				player_stats.append(stat)

		except Exception as e:
			print(f"Warning: Error processing {file_path}: {e}", file=sys.stderr)
			continue

	return player_stats


def deduplicate_stats(player_stats):
	"""Deduplicate by (game_id, player_id, position)."""
	seen = set()
	deduplicated = []
	duplicates = 0

	for stat in player_stats:
		key = (stat["game_id"], stat["player_id"], stat["position"])
		if key not in seen:
			seen.add(key)
			deduplicated.append(stat)
		else:
			duplicates += 1

	if duplicates > 0:
		print(f"Note: Removed {duplicates} duplicate stats")

	return deduplicated


def build_player_seasons(player_stats):
	"""Build player_seasons records from stats."""
	player_season_attrs = defaultdict(lambda: {"jerseys": [], "positions": []})

	for stat in player_stats:
		key = (stat["player_id"], stat["team_id"], stat["season_id"])
		if stat.get("jersey_number"):
			player_season_attrs[key]["jerseys"].append(stat["jersey_number"])
		if stat.get("position"):
			player_season_attrs[key]["positions"].append(stat["position"])

	player_seasons = []
	for (player_id, team_id, season_id), attrs in player_season_attrs.items():
		jersey = max(set(attrs["jerseys"]), key=attrs["jerseys"].count) if attrs["jerseys"] else "0"
		position = max(set(attrs["positions"]), key=attrs["positions"].count) if attrs["positions"] else None

		player_seasons.append({
			"player_id": player_id,
			"team_id": team_id,
			"season_id": season_id,
			"jersey_number": jersey,
			"primary_position": position,
		})

	return player_seasons


def load_player_stats_to_database(player_stats: list, dry_run: bool = False):
	"""Load player stats into PostgreSQL."""
	player_stats = deduplicate_stats(player_stats)

	if dry_run:
		print(f"DRY RUN: Would load {len(player_stats)} player game stats:")
		for stat in player_stats[:10]:
			print(f"  Game {stat['game_id']}, Player {stat['player_id']}: {stat['goals']}G {stat['assists']}A")
		if len(player_stats) > 10:
			print(f"  ... and {len(player_stats) - 10} more")
		return

	print(f"Loading {len(player_stats)} player game stats to database...")

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
			goalie_minutes = EXCLUDED.goalie_minutes,
			goals_allowed = EXCLUDED.goals_allowed,
			gaa = EXCLUDED.gaa,
			saves = EXCLUDED.saves,
			save_percentage = EXCLUDED.save_percentage
	"""

	loaded = 0
	batch_size = 100

	with get_cursor() as cursor:
		for i in range(0, len(player_stats), batch_size):
			batch = player_stats[i:i + batch_size]
			for stat in batch:
				cursor.execute(query, stat)
				loaded += 1

			print(f"Loaded batch {i // batch_size + 1}: {len(batch)} stats")

	print(f"Successfully loaded {loaded} player game stats")


def load_player_seasons_to_database(player_seasons: list, dry_run: bool = False):
	"""Load player_seasons records."""
	if dry_run:
		print(f"DRY RUN: Would load {len(player_seasons)} player-season records")
		return

	print(f"Loading {len(player_seasons)} player-season records...")

	query = """
		INSERT INTO player_seasons (player_id, team_id, season_id, jersey_number, primary_position)
		VALUES (%s, %s, %s, %s, %s)
		ON CONFLICT (player_id, team_id, season_id) DO UPDATE SET
			jersey_number = EXCLUDED.jersey_number,
			primary_position = EXCLUDED.primary_position,
			updated_at = NOW()
	"""

	loaded = 0
	with get_cursor() as cursor:
		for ps in player_seasons:
			cursor.execute(
				query,
				(ps["player_id"], ps["team_id"], ps["season_id"], ps["jersey_number"], ps["primary_position"]),
			)
			loaded += 1

	print(f"Successfully loaded {loaded} player-season records")


def main():
	parser = argparse.ArgumentParser(description="Load player game stats to PostgreSQL")
	parser.add_argument("--data-dir", default="data", help="Base data directory")
	parser.add_argument("--season", help="Only load from specific season")
	parser.add_argument("--division", type=int, choices=[1, 2, 3], help="Only load from specific division")
	parser.add_argument("--dry-run", action="store_true", help="Show what would be loaded")

	args = parser.parse_args()

	player_stats = extract_player_stats(args.data_dir, season_filter=args.season, division_filter=args.division)

	if not player_stats:
		print("No player stats found", file=sys.stderr)
		sys.exit(1)

	print(f"Extracted {len(player_stats)} player game statistics")

	# Summary
	total_goals = sum(s["goals"] for s in player_stats)
	total_assists = sum(s["assists"] for s in player_stats)
	unique_games = len(set(s["game_id"] for s in player_stats))
	unique_players = len(set(s["player_id"] for s in player_stats))

	print(f"Summary: {unique_games} games, {unique_players} players")
	print(f"Total goals: {total_goals}, Total assists: {total_assists}")

	load_player_stats_to_database(player_stats, args.dry_run)

	# Build and load player_seasons
	player_seasons = build_player_seasons(player_stats)
	print(f"Built {len(player_seasons)} player-season records")
	load_player_seasons_to_database(player_seasons, args.dry_run)


if __name__ == "__main__":
	main()

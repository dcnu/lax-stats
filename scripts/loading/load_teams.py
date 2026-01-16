#!/usr/bin/env python3
"""
Load team data from scraped game info files into local PostgreSQL.

Extracts unique teams from all game_*_info.json files and loads them
into the teams table with proper ID mapping.

Usage:
	python3 scripts/loading/load_teams.py
	python3 scripts/loading/load_teams.py --data-dir data/2025/division1/games --dry-run
	python3 scripts/loading/load_teams.py --division 1
"""

import json
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.db import get_cursor
from utils.path_helpers import get_all_season_dirs


def extract_teams_from_games(data_dir: str = "data", season_filter: str = None, division_filter: int = None):
	"""Extract unique teams from all game info files."""
	data_path = Path(data_dir)
	if not data_path.exists():
		print(f"Error: Data directory {data_dir} not found", file=sys.stderr)
		sys.exit(1)

	teams = {}
	game_files = []

	# Check if this is a games directory directly
	if (data_path / "games").exists() or any(data_path.glob("game_*_info.json")):
		# Direct path to games
		if data_path.name == "games":
			game_files = list(data_path.glob("game_*_info.json"))
			division = 1  # Default
		else:
			game_files = list((data_path / "games").glob("game_*_info.json"))
			division = 1
		# Assign division to all files
		game_files = [(f, division) for f in game_files]
	else:
		# Structured directory: data/{season}/division{n}/games/
		seasons = get_all_season_dirs(data_dir) if not season_filter else [(season_filter, data_path / season_filter)]

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
							for f in games_dir.glob("game_*_info.json"):
								game_files.append((f, division))
					except ValueError:
						continue
			else:
				games_dir = season_path / "games"
				if games_dir.exists():
					for f in games_dir.glob("game_*_info.json"):
						game_files.append((f, division_filter or 1))

	if not game_files:
		print(f"Error: No game info files found", file=sys.stderr)
		sys.exit(1)

	print(f"Processing {len(game_files)} game files...")

	for file_path, division in game_files:
		try:
			with open(file_path, "r", encoding="utf-8") as f:
				game_data = json.load(f)

			# Extract home team
			if "homeTeamId" in game_data and "homeTeam" in game_data:
				team_id = game_data["homeTeamId"]
				team_name = game_data["homeTeam"]
				if team_id not in teams:
					teams[team_id] = {
						"id": team_id,
						"name": team_name,
						"short_name": None,
						"division_id": division,
					}

			# Extract away team
			if "awayTeamId" in game_data and "awayTeam" in game_data:
				team_id = game_data["awayTeamId"]
				team_name = game_data["awayTeam"]
				if team_id not in teams:
					teams[team_id] = {
						"id": team_id,
						"name": team_name,
						"short_name": None,
						"division_id": division,
					}

		except Exception as e:
			print(f"Warning: Error processing {file_path}: {e}", file=sys.stderr)
			continue

	return list(teams.values())


def load_teams_to_database(teams: list, dry_run: bool = False):
	"""Load teams into PostgreSQL teams table."""
	if dry_run:
		print(f"DRY RUN: Would load {len(teams)} teams:")
		for team in sorted(teams, key=lambda x: x["name"])[:20]:
			print(f"  {team['id']}: {team['name']} (D{team['division_id']})")
		if len(teams) > 20:
			print(f"  ... and {len(teams) - 20} more")
		return

	print(f"Loading {len(teams)} teams to database...")

	query = """
		INSERT INTO teams (id, name, short_name, division_id)
		VALUES (%s, %s, %s, %s)
		ON CONFLICT (id) DO UPDATE SET
			name = EXCLUDED.name,
			short_name = EXCLUDED.short_name,
			division_id = EXCLUDED.division_id
	"""

	loaded = 0
	with get_cursor() as cursor:
		for team in teams:
			cursor.execute(
				query, (team["id"], team["name"], team["short_name"], team["division_id"])
			)
			loaded += 1

	print(f"Successfully loaded {loaded} teams")

	# Show sample
	if teams:
		print("Sample loaded teams:")
		for team in sorted(teams, key=lambda x: x["name"])[:5]:
			print(f"  {team['id']}: {team['name']}")


def main():
	parser = argparse.ArgumentParser(description="Load team data from game files to PostgreSQL")
	parser.add_argument("--data-dir", default="data", help="Directory containing game JSON files")
	parser.add_argument("--season", help="Only load from specific season")
	parser.add_argument("--division", type=int, choices=[1, 2, 3], help="Only load from specific division")
	parser.add_argument("--dry-run", action="store_true", help="Show what would be loaded without actually loading")

	args = parser.parse_args()

	# Extract teams from game files
	teams = extract_teams_from_games(args.data_dir, season_filter=args.season, division_filter=args.division)

	if not teams:
		print("No teams found in game files", file=sys.stderr)
		sys.exit(1)

	print(f"Extracted {len(teams)} unique teams")

	load_teams_to_database(teams, args.dry_run)


if __name__ == "__main__":
	main()

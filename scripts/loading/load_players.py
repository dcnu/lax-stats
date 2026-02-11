#!/usr/bin/env python3
"""
Load player data from scraped player stats files into PostgreSQL.

Extracts unique players from all game_*_player_stats.json files.

Usage:
	python3 scripts/loading/load_players.py
	python3 scripts/loading/load_players.py --season 2025 --division 1
	python3 scripts/loading/load_players.py --dry-run
"""

import json
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.db import get_cursor
from utils.path_helpers import get_all_season_dirs


def load_roster_data(data_dir: str, season_filter: str = None, division_filter: int = None) -> dict:
	"""Load player data from roster files.

	Returns:
		Dict mapping playerId -> {hometown, high_school, class_year, position}
	"""
	data_path = Path(data_dir)
	roster_data = {}

	if season_filter:
		seasons = [(season_filter, data_path / season_filter)]
	else:
		seasons = get_all_season_dirs(data_dir)

	for season_id, season_path in seasons:
		division_dirs = [d for d in season_path.iterdir() if d.is_dir() and d.name.startswith("division")]
		for div_dir in division_dirs:
			try:
				division = int(div_dir.name.replace("division", ""))
				if division_filter and division != division_filter:
					continue
			except ValueError:
				continue

			raw_dir = div_dir / "raw"
			rosters_file = raw_dir / "rosters.json"
			if not rosters_file.exists():
				continue

			with open(rosters_file, "r", encoding="utf-8") as f:
				teams = json.load(f)

			for team in teams:
				for player in team.get("players", []):
					pid = player.get("playerID")
					if pid:
						try:
							pid = int(pid)
						except (ValueError, TypeError):
							continue
						roster_data[pid] = {
							"hometown": player.get("hometown", ""),
							"high_school": player.get("highSchool", ""),
							"class_year": player.get("classYear", ""),
						}

	return roster_data


def extract_players_from_files(data_dir: str = "data", season_filter: str = None, division_filter: int = None):
	"""Extract unique players from all player stats files."""
	data_path = Path(data_dir)
	if not data_path.exists():
		print(f"Error: Data directory {data_dir} not found", file=sys.stderr)
		sys.exit(1)

	players = {}
	stats_files = []

	# Get all player stats files
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
							stats_files.append((division, f))
				except ValueError:
					continue
		else:
			games_dir = season_path / "games"
			if games_dir.exists():
				for f in games_dir.glob("game_*_player_stats.json"):
					stats_files.append((division_filter or 1, f))

	if not stats_files:
		print(f"Error: No player stats files found", file=sys.stderr)
		sys.exit(1)

	print(f"Processing {len(stats_files)} player stats files...")

	# Load roster data for enrichment
	roster_data = load_roster_data(data_dir, season_filter, division_filter)
	if roster_data:
		print(f"Loaded roster data for {len(roster_data)} players")

	for division, file_path in stats_files:
		try:
			with open(file_path, "r", encoding="utf-8") as f:
				players_data = json.load(f)

			for player_data in players_data:
				player_id = player_data.get("playerId")
				name = player_data.get("name")

				if player_id and name and player_id not in players:
					player = {
						"id": player_id,
						"name": name,
						"division_id": division,
						"hometown": None,
						"high_school": None,
					}

					# Enrich from roster data
					roster = roster_data.get(player_id)
					if roster:
						if roster["hometown"]:
							player["hometown"] = roster["hometown"]
						if roster["high_school"]:
							player["high_school"] = roster["high_school"]

					players[player_id] = player

		except Exception as e:
			print(f"Warning: Error processing {file_path}: {e}", file=sys.stderr)
			continue

	return list(players.values())


def load_players_to_database(players: list, dry_run: bool = False):
	"""Load players into PostgreSQL players table."""
	if dry_run:
		print(f"DRY RUN: Would load {len(players)} players:")
		for player in list(players)[:20]:
			print(f"  {player['id']}: {player['name']}")
		if len(players) > 20:
			print(f"  ... and {len(players) - 20} more")
		return

	print(f"Loading {len(players)} players to database...")

	query = """
		INSERT INTO players (id, name, division_id, hometown, high_school)
		VALUES (%s, %s, %s, %s, %s)
		ON CONFLICT (id) DO UPDATE SET
			name = EXCLUDED.name,
			hometown = COALESCE(EXCLUDED.hometown, players.hometown),
			high_school = COALESCE(EXCLUDED.high_school, players.high_school),
			updated_at = NOW()
	"""

	loaded = 0
	with get_cursor() as cursor:
		for player in players:
			cursor.execute(query, (
				player["id"], player["name"], player["division_id"],
				player.get("hometown"), player.get("high_school"),
			))
			loaded += 1

	print(f"Successfully loaded {loaded} players")


def main():
	parser = argparse.ArgumentParser(description="Load player data from stats files to PostgreSQL")
	parser.add_argument("--data-dir", default="data", help="Base data directory")
	parser.add_argument("--season", help="Only load from specific season")
	parser.add_argument("--division", type=int, choices=[1, 2, 3], help="Only load from specific division")
	parser.add_argument("--dry-run", action="store_true", help="Show what would be loaded without actually loading")

	args = parser.parse_args()

	players = extract_players_from_files(args.data_dir, season_filter=args.season, division_filter=args.division)

	if not players:
		print("No players found in files", file=sys.stderr)
		sys.exit(1)

	print(f"Extracted {len(players)} unique players")

	load_players_to_database(players, args.dry_run)


if __name__ == "__main__":
	main()

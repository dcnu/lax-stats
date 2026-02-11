#!/usr/bin/env python3
"""
Load game data from scraped game info files into PostgreSQL.

Processes all game_*_info.json files and loads game records with scores,
teams, and metadata.

Usage:
	python3 scripts/loading/load_games.py
	python3 scripts/loading/load_games.py --season 2025 --division 1
	python3 scripts/loading/load_games.py --dry-run
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.db import get_cursor, upsert_season
from utils.path_helpers import get_all_season_dirs


def safe_int(value, default=None):
	"""Safely convert value to int."""
	if value is None or value == "":
		return default
	try:
		return int(value)
	except (ValueError, TypeError):
		return default


def parse_game_date(date_str: str):
	"""Parse game date from various formats."""
	if not date_str:
		return None
	try:
		# Try MM/DD/YYYY format
		return datetime.strptime(date_str, "%m/%d/%Y").date()
	except ValueError:
		pass
	try:
		# Try YYYY-MM-DD format
		return datetime.strptime(date_str, "%Y-%m-%d").date()
	except ValueError:
		pass
	return None


def ensure_season_exists(season_id: str, division_id: int):
	"""Ensure the season record exists."""
	start_year = int(season_id)
	end_year = start_year
	upsert_season(
		season_id=season_id,
		division_id=division_id,
		start_year=start_year,
		end_year=end_year,
		start_date=datetime(start_year, 2, 1).date(),
		end_date=datetime(start_year, 5, 31).date(),
		is_current=(start_year == datetime.now().year),
	)


def extract_games_from_files(data_dir: str = "data", season_filter: str = None, division_filter: int = None):
	"""Extract games from all game info files."""
	data_path = Path(data_dir)
	if not data_path.exists():
		print(f"Error: Data directory {data_dir} not found", file=sys.stderr)
		sys.exit(1)

	games = []
	game_files = []

	# Get all game files
	if season_filter:
		seasons = [(season_filter, data_path / season_filter)]
	else:
		seasons = get_all_season_dirs(data_dir)

	if not seasons:
		# Try direct games directory
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
						for f in games_dir.glob("game_*_info.json"):
							game_files.append((season_id, division, f))
				except ValueError:
					continue
		else:
			games_dir = season_path / "games"
			if games_dir.exists():
				for f in games_dir.glob("game_*_info.json"):
					game_files.append((season_id, division_filter or 1, f))

	if not game_files:
		print(f"Error: No game info files found", file=sys.stderr)
		sys.exit(1)

	print(f"Processing {len(game_files)} game files...")

	for season_id, division, file_path in game_files:
		try:
			with open(file_path, "r", encoding="utf-8") as f:
				game_data = json.load(f)

			game_id = game_data.get("gameId") or file_path.stem.split("_")[1]
			game_date = parse_game_date(game_data.get("gameDate") or game_data.get("date"))

			game = {
				"id": str(game_id),
				"season_id": season_id,
				"division_id": division,
				"game_date": game_date,
				"home_team_id": game_data.get("homeTeamId"),
				"away_team_id": game_data.get("awayTeamId"),
				"home_score": safe_int(game_data.get("homeScore")),
				"away_score": safe_int(game_data.get("awayScore")),
				"location": game_data.get("location"),
				"attendance": safe_int(game_data.get("attendance")),
				"status": "final",
			}

			if game["home_team_id"] and game["away_team_id"]:
				games.append(game)

		except Exception as e:
			print(f"Warning: Error processing {file_path}: {e}", file=sys.stderr)
			continue

	return games


def load_games_to_database(games: list, dry_run: bool = False):
	"""Load games into PostgreSQL games table."""
	if dry_run:
		print(f"DRY RUN: Would load {len(games)} games:")
		for game in games[:10]:
			print(f"  {game['id']}: {game['home_team_id']} vs {game['away_team_id']} ({game['home_score']}-{game['away_score']})")
		if len(games) > 10:
			print(f"  ... and {len(games) - 10} more")
		return

	# Ensure seasons exist
	seasons_created = set()
	for game in games:
		key = (game["season_id"], game["division_id"])
		if key not in seasons_created:
			ensure_season_exists(game["season_id"], game["division_id"])
			seasons_created.add(key)

	print(f"Loading {len(games)} games to database...")

	query = """
		INSERT INTO games (
			id, season_id, division_id, game_date, home_team_id, away_team_id,
			home_score, away_score, location, attendance, status
		)
		VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
		ON CONFLICT (id) DO UPDATE SET
			home_score = EXCLUDED.home_score,
			away_score = EXCLUDED.away_score,
			location = EXCLUDED.location,
			attendance = EXCLUDED.attendance,
			status = EXCLUDED.status,
			updated_at = NOW()
	"""

	loaded = 0
	with get_cursor() as cursor:
		for game in games:
			cursor.execute(
				query,
				(
					game["id"],
					game["season_id"],
					game["division_id"],
					game["game_date"],
					game["home_team_id"],
					game["away_team_id"],
					game["home_score"],
					game["away_score"],
					game["location"],
					game["attendance"],
					game["status"],
				),
			)
			loaded += 1

	print(f"Successfully loaded {loaded} games")


def main():
	parser = argparse.ArgumentParser(description="Load game data from info files to PostgreSQL")
	parser.add_argument("--data-dir", default="data", help="Base data directory")
	parser.add_argument("--season", help="Only load from specific season")
	parser.add_argument("--division", type=int, choices=[1, 2, 3], help="Only load from specific division")
	parser.add_argument("--dry-run", action="store_true", help="Show what would be loaded without actually loading")

	args = parser.parse_args()

	games = extract_games_from_files(args.data_dir, season_filter=args.season, division_filter=args.division)

	if not games:
		print("No games found in files", file=sys.stderr)
		sys.exit(1)

	print(f"Extracted {len(games)} games")

	# Show summary
	unique_seasons = len(set(g["season_id"] for g in games))
	unique_teams = len(set(g["home_team_id"] for g in games) | set(g["away_team_id"] for g in games))
	print(f"Summary: {unique_seasons} seasons, {unique_teams} teams")

	load_games_to_database(games, args.dry_run)


if __name__ == "__main__":
	main()

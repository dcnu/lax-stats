#!/usr/bin/env python3
"""
Daily sync script for NCAA lacrosse statistics.

Discovers new games, fetches data, loads to database, and runs QC.
Designed to run as a cron job at midnight PT.

Usage:
	python scripts/sync_daily.py --season 2026
	python scripts/sync_daily.py --season 2026 --date 02/15/2026
	python scripts/sync_daily.py --season 2026 --dry-run
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytz

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))
from utils.path_helpers import get_season_raw_dir, get_season_games_dir
from utils.db import execute_query


def load_config(config_file: str = "config.json") -> dict:
	"""Load configuration from JSON file."""
	config_path = Path(__file__).parent.parent / config_file
	try:
		with open(config_path, "r") as f:
			return json.load(f)
	except FileNotFoundError:
		print(f"Error: Config file not found: {config_path}", file=sys.stderr)
		sys.exit(1)


def get_yesterday_pt() -> str:
	"""Get yesterday's date in PT timezone as MM/DD/YYYY."""
	pt = pytz.timezone("US/Pacific")
	now_pt = datetime.now(pt)
	yesterday = now_pt - timedelta(days=1)
	return yesterday.strftime("%m/%d/%Y")


def discover_season_id(division: int = 1) -> int | None:
	"""
	Attempt to discover the season_division_id for the current season.

	This queries the NCAA site to find the active season ID.
	Returns None if not yet available.
	"""
	# The season_division_id typically follows a pattern but needs manual discovery
	# For now, return None to indicate manual configuration needed
	return None


def fetch_game_ids(date: str, season: str, division: int, config: dict, dry_run: bool = False) -> list[str]:
	"""Fetch game IDs for a specific date."""
	print(f"Discovering games for {date}...")

	if dry_run:
		print("DRY RUN: Would fetch game IDs")
		return []

	# Check if season_division_id is configured
	season_div_id = config.get("season_division_ids", {}).get(str(division), {}).get(season)
	if season_div_id is None:
		print(f"Warning: season_division_id not configured for {season} D{division}")
		print("Run: python scripts/utils/get_game_ids.py --season 2026 --test --debug")
		print("to discover the season_division_id, then update config.json")
		return []

	# Run get_game_ids.py for the specific date
	cmd = [
		sys.executable,
		"scripts/utils/get_game_ids.py",
		"--season", season,
		"--division", str(division),
		"--test",
		"--start-date", date,
		"--output", "daily_games.json"
	]

	result = subprocess.run(cmd, capture_output=True, text=True)
	if result.returncode != 0:
		print(f"Error fetching game IDs: {result.stderr}", file=sys.stderr)
		return []

	# Read the discovered games
	raw_dir = get_season_raw_dir(season, division)
	daily_file = raw_dir / "daily_games.json"

	if not daily_file.exists():
		return []

	with open(daily_file, "r") as f:
		games = json.load(f)

	return [g["gameID"] for g in games]


def fetch_game_data(game_ids: list[str], season: str, division: int, config: dict, dry_run: bool = False) -> dict:
	"""Fetch game data and play-by-play via agent-browser."""
	results = {"success": [], "failed": []}

	if not game_ids:
		print("No new games to fetch")
		return results

	print(f"Fetching data for {len(game_ids)} games via agent-browser...")

	if dry_run:
		print(f"DRY RUN: Would fetch {len(game_ids)} games")
		return results

	cmd = [
		sys.executable, "scripts/fetching/fetch_games_browser.py",
		"--season", season,
		"--division", str(division),
	]

	result = subprocess.run(cmd, capture_output=False, text=True)
	if result.returncode != 0:
		print("Browser fetch failed", file=sys.stderr)

	# Check which games succeeded by looking for output files
	games_dir = get_season_games_dir(season, division)
	for game_id in game_ids:
		info_file = games_dir / f"game_{game_id}_info.json"
		if info_file.exists():
			results["success"].append(game_id)
		else:
			results["failed"].append(game_id)

	return results


def load_to_database(season: str, division: int, dry_run: bool = False) -> bool:
	"""Load scraped data into database."""
	print("Loading data to database...")

	if dry_run:
		print("DRY RUN: Would load data to database")
		return True

	# Run loading scripts in order
	scripts = [
		("load_teams.py", "Loading teams"),
		("load_games.py", "Loading games"),
		("load_players.py", "Loading players"),
		("load_player_stats.py", "Loading player stats"),
		("load_game_plays.py", "Loading game plays"),
		("enrich_tables.py", "Running enrichment"),
	]

	for script, description in scripts:
		print(f"  {description}...")
		cmd = [
			sys.executable,
			f"scripts/loading/{script}",
			"--season", season,
			"--division", str(division)
		]

		result = subprocess.run(cmd, capture_output=True, text=True)
		if result.returncode != 0:
			print(f"Error in {script}: {result.stderr}", file=sys.stderr)
			return False

	return True


def run_qc(season: str, division: int, dry_run: bool = False) -> dict:
	"""Run QC assessment and return results."""
	print("Running QC assessment...")

	if dry_run:
		print("DRY RUN: Would run QC")
		return {"errors": 0, "ok": 0}

	cmd = [
		sys.executable,
		"scripts/qc/assess_data_quality.py",
		"--season", season,
		"--division", str(division),
		"--json"
	]

	result = subprocess.run(cmd, capture_output=True, text=True)
	if result.returncode != 0:
		print(f"QC error: {result.stderr}", file=sys.stderr)
		return {"errors": -1, "ok": 0}

	try:
		errors = json.loads(result.stdout)
		return {"errors": len(errors), "ok": 0}
	except json.JSONDecodeError:
		return {"errors": -1, "ok": 0}


def main():
	parser = argparse.ArgumentParser(description="Daily sync for NCAA lacrosse stats")
	parser.add_argument("--season", required=True, help="Season year (e.g., 2026)")
	parser.add_argument("--division", type=int, default=1, choices=[1, 2, 3],
						help="NCAA division (default: 1)")
	parser.add_argument("--date", help="Specific date MM/DD/YYYY (default: yesterday PT)")
	parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
	parser.add_argument("--skip-fetch", action="store_true", help="Skip fetching, only load and QC")
	parser.add_argument("--config", default="config.json", help="Config file path")

	args = parser.parse_args()

	# Load config
	config = load_config(args.config)

	# Determine date
	sync_date = args.date or get_yesterday_pt()

	print(f"=== Daily Sync: {args.season} D{args.division} ===")
	print(f"Date: {sync_date}")
	print(f"Dry run: {args.dry_run}")
	print()

	if not args.skip_fetch:
		# Step 1: Discover game IDs
		game_ids = fetch_game_ids(sync_date, args.season, args.division, config, args.dry_run)
		print(f"Found {len(game_ids)} games")

		# Step 2: Fetch game data
		if game_ids:
			fetch_results = fetch_game_data(game_ids, args.season, args.division, config, args.dry_run)
			print(f"Fetched: {len(fetch_results['success'])} success, {len(fetch_results['failed'])} failed")

	# Step 3: Load to database
	load_success = load_to_database(args.season, args.division, args.dry_run)
	if not load_success:
		print("Database load failed", file=sys.stderr)
		sys.exit(1)

	# Step 4: Run QC
	qc_results = run_qc(args.season, args.division, args.dry_run)
	print(f"QC: {qc_results['errors']} errors found")

	print()
	print("=== Sync complete ===")


if __name__ == "__main__":
	main()

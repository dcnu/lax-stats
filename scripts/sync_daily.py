#!/usr/bin/env python3
"""
Daily sync script for NCAA lacrosse statistics.

Uses the ncaa.com GraphQL pipeline (no browser required):
  get_game_ids_ncaa → fetch_games_ncaa → map_game_ids →
  load_games_ncaa → load_players → load_player_stats →
  load_game_plays → enrich_tables

Designed to run as a cron job at midnight PT.

Usage:
	python scripts/sync_daily.py --season 2026
	python scripts/sync_daily.py --season 2026 --dry-run
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytz

sys.path.insert(0, str(Path(__file__).parent))


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
	yesterday = datetime.now(pt) - timedelta(days=1)
	return yesterday.strftime("%m/%d/%Y")


def run(cmd: list[str], description: str, dry_run: bool = False) -> bool:
	"""Run a subprocess command, printing description and result."""
	print(f"  {description}...")
	if dry_run:
		print(f"    DRY RUN: {' '.join(cmd)}")
		return True
	result = subprocess.run(cmd, capture_output=False, text=True)
	if result.returncode != 0:
		print(f"    FAILED (exit {result.returncode})", file=sys.stderr)
		return False
	return True


def main():
	parser = argparse.ArgumentParser(description="Daily sync for NCAA lacrosse stats")
	parser.add_argument("--season", required=True, help="Season year (e.g., 2026)")
	parser.add_argument("--division", type=int, default=1, choices=[1, 2, 3])
	parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
	parser.add_argument("--skip-fetch", action="store_true", help="Skip fetch steps; only load and enrich")
	args = parser.parse_args()

	config = load_config()
	date_ranges = config.get("date_ranges", {})
	start_date = date_ranges.get("start_date", "01/15/2026")
	end_date = date_ranges.get("end_date", "06/01/2026")
	py = sys.executable
	s = args.season
	d = str(args.division)

	print(f"=== Daily Sync: {s} D{d} ===")
	print(f"Date: {get_yesterday_pt()}")
	print(f"Dry run: {args.dry_run}")
	print()

	if not args.skip_fetch:
		# Step 1: Refresh game IDs for the full season (idempotent)
		ok = run(
			[py, "scripts/utils/get_game_ids_ncaa.py",
			 "--season", s, "--division", d,
			 "--start-date", start_date, "--end-date", end_date],
			"Refreshing game IDs (ncaa.com scoreboard)",
			args.dry_run,
		)
		if not ok:
			sys.exit(1)

		# Step 2: Fetch game data for new final games; include-scheduled for venue info
		ok = run(
			[py, "scripts/fetching/fetch_games_ncaa.py",
			 "--season", s, "--division", d, "--include-scheduled"],
			"Fetching game data (box scores, play-by-play)",
			args.dry_run,
		)
		if not ok:
			sys.exit(1)

		# Step 3: Rebuild game ID map (ncaa.com ↔ stats.ncaa.org cross-reference)
		ok = run(
			[py, "scripts/utils/map_game_ids.py", "--season", s, "--division", d],
			"Rebuilding game ID map",
			args.dry_run,
		)
		if not ok:
			sys.exit(1)

	# Step 4: Populate lookup_teams.short_name from ncaa.com names
	ok = run(
		[py, "scripts/loading/parse_team_names.py", "--season", s, "--division", d],
		"Updating team short names",
		args.dry_run,
	)
	if not ok:
		sys.exit(1)

	# Step 5: Load games (matched, unmatched, and scheduled)
	ok = run(
		[py, "scripts/loading/load_games_ncaa.py", "--season", s, "--division", d],
		"Loading games",
		args.dry_run,
	)
	if not ok:
		sys.exit(1)

	# Steps 6-8: Load player-level data (for stats.ncaa.org matched games)
	for script, description in [
		("load_players.py", "Loading players"),
		("load_player_stats.py", "Loading player stats"),
		("load_game_plays.py", "Loading game plays"),
	]:
		ok = run(
			[py, f"scripts/loading/{script}", "--season", s, "--division", d],
			description,
			args.dry_run,
		)
		if not ok:
			sys.exit(1)

	# Step 9: Rebuild aggregated stats tables
	ok = run(
		[py, "scripts/loading/enrich_tables.py", "--season", s, "--division", d],
		"Running enrichment (aggregated stats)",
		args.dry_run,
	)
	if not ok:
		sys.exit(1)

	print()
	print("=== Sync complete ===")


if __name__ == "__main__":
	main()

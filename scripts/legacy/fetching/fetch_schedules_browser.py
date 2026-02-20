#!/usr/bin/env python3
"""
Fetch schedule data for future (unplayed) NCAA lacrosse games.

Scrapes scoreboard pages date-by-date to extract scheduled matchups.
Saves game_{id}_schedule.json files that load_games.py can pick up.

Prerequisite: Launch browser with --remote-debugging-port=9222, then:
	agent-browser connect 9222

Usage:
	python3 scripts/fetching/fetch_schedules_browser.py --season 2026
	python3 scripts/fetching/fetch_schedules_browser.py --season 2026 --dry-run
"""

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.path_helpers import get_season_games_dir, get_season_raw_dir
from utils.browser_common import run_ab, eval_js

JS_FILE = Path(__file__).parent.parent / "utils" / "_extract_games.js"


def load_config(config_file="config.json"):
	"""Load configuration from JSON file."""
	config_path = Path(__file__).resolve().parent.parent.parent / config_file
	with open(config_path, "r") as f:
		return json.load(f)


def load_existing_ids(games_dir: Path) -> set[str]:
	"""Get game IDs that already have info files (played games with box scores)."""
	ids = set()
	for f in games_dir.glob("game_*_info.json"):
		gid = f.stem.split("_")[1]
		ids.add(gid)
	return ids


def scrape_date(base_url: str, date_str: str) -> list[dict]:
	"""Scrape game data for a single date from the scoreboard."""
	encoded_date = date_str.replace("/", "%2F")
	url = f"{base_url}?utf8=%E2%9C%93&season_division_id=&game_date={encoded_date}&conference_id=0&tournament_id=&commit=Submit"

	run_ab("open", url)
	time.sleep(4)

	raw = eval_js(JS_FILE)

	try:
		import re
		match = re.search(r'\[.*\]', raw, re.DOTALL)
		if match:
			return json.loads(match.group())
	except (json.JSONDecodeError, AttributeError):
		pass

	return []


def main():
	parser = argparse.ArgumentParser(
		description="Fetch schedule data for future NCAA lacrosse games"
	)
	parser.add_argument("--season", default="2026", help="Season year (default: 2026)")
	parser.add_argument(
		"--division", type=int, default=1, choices=[1, 2, 3],
		help="NCAA division (default: 1)"
	)
	parser.add_argument("--dry-run", action="store_true", help="List games without saving")
	args = parser.parse_args()

	config = load_config()
	div_id = config["season_division_ids"][str(args.division)].get(args.season)
	if not div_id:
		print(f"Error: No season_division_id for {args.season} D{args.division}", file=sys.stderr)
		sys.exit(1)

	base_url = f"https://stats.ncaa.org/season_divisions/{div_id}/livestream_scoreboards"
	games_dir = get_season_games_dir(args.season, args.division)

	# Load game IDs from the raw directory
	raw_dir = get_season_raw_dir(args.season, args.division)
	ids_file = raw_dir / "game_ids.json"
	if not ids_file.exists():
		print(f"Error: {ids_file} not found. Run get_game_ids_browser.py first.", file=sys.stderr)
		sys.exit(1)
	with open(ids_file, "r") as f:
		all_game_ids = json.load(f)

	# Build set of game IDs and their dates from game_ids.json
	game_dates = {}
	for g in all_game_ids:
		gid = str(g["gameID"])
		date = g.get("date", "")
		game_dates[gid] = date

	# Skip games that already have info files (played games with box scores)
	info_ids = load_existing_ids(games_dir)
	# Also skip games that already have schedule files
	schedule_ids = set()
	for f in games_dir.glob("game_*_schedule.json"):
		schedule_ids.add(f.stem.split("_")[1])

	need_schedule = set(game_dates.keys()) - info_ids - schedule_ids
	if not need_schedule:
		print("All games already have info or schedule files")
		return

	# Find unique future dates that have games needing schedule data
	dates_to_scrape = sorted(set(
		game_dates[gid] for gid in need_schedule if game_dates.get(gid)
	))

	print(f"{len(need_schedule)} games need schedule data across {len(dates_to_scrape)} dates")
	print(f"  ({len(info_ids)} have info files, {len(schedule_ids)} have schedule files)")

	if args.dry_run:
		for d in dates_to_scrape:
			count = sum(1 for gid in need_schedule if game_dates.get(gid) == d)
			print(f"  {d}: {count} games")
		return

	saved = 0
	skipped = 0

	for i, date_str in enumerate(dates_to_scrape, 1):
		print(f"[{i}/{len(dates_to_scrape)}] {date_str}...", end=" ", flush=True)
		games = scrape_date(base_url, date_str)
		date_saved = 0

		for game in games:
			gid = str(game["gameID"])
			if gid not in need_schedule:
				skipped += 1
				continue

			# Only save schedule files for games without scores
			if "homeScore" in game and "awayScore" in game:
				skipped += 1
				continue

			schedule_data = {
				"gameId": gid,
				"homeTeamId": game["homeTeamId"],
				"homeTeam": game["homeTeam"],
				"awayTeamId": game["awayTeamId"],
				"awayTeam": game["awayTeam"],
				"gameDate": date_str,
				"status": "scheduled"
			}

			out_path = games_dir / f"game_{gid}_schedule.json"
			with open(out_path, "w", encoding="utf-8") as f:
				json.dump(schedule_data, f, indent=2)

			saved += 1
			date_saved += 1
			need_schedule.discard(gid)

		print(f"{date_saved} saved, {len(games)} on page")

		if i < len(dates_to_scrape):
			time.sleep(1)

	print(f"\nComplete: {saved} schedule files saved")


if __name__ == "__main__":
	main()

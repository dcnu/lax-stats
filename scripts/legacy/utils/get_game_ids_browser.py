#!/usr/bin/env python3
"""
Discover game IDs using agent-browser connected to a real browser via CDP.

Prerequisite: Launch browser with --remote-debugging-port=9222, then:
    agent-browser connect 9222

Usage:
	python3 scripts/utils/get_game_ids_browser.py --season 2026
	python3 scripts/utils/get_game_ids_browser.py --season 2026 --start-date 01/30/2026 --end-date 02/11/2026
"""

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.path_helpers import get_season_raw_dir

JS_FILE = Path(__file__).parent / "_extract_games.js"


def load_config(config_file="config.json"):
	"""Load configuration from JSON file."""
	config_path = Path(__file__).resolve().parent.parent.parent / config_file
	with open(config_path, "r") as f:
		return json.load(f)


def run_ab(*args) -> str:
	"""Run an agent-browser command and return stdout."""
	result = subprocess.run(
		["agent-browser"] + list(args),
		capture_output=True, text=True, timeout=30
	)
	return result.stdout.strip()


def scrape_date(base_url: str, date_str: str, page_load_wait: int = 8) -> list[dict]:
	"""Scrape game IDs for a single date."""
	encoded_date = date_str.replace("/", "%2F")
	url = f"{base_url}?utf8=%E2%9C%93&season_division_id=&game_date={encoded_date}&conference_id=0&tournament_id=&commit=Submit"

	run_ab("open", url)
	# Wait for page content to render
	time.sleep(page_load_wait)

	js = JS_FILE.read_text().replace("\n", " ").replace("\t", " ")
	# Use shell=True to preserve JS quoting
	result = subprocess.run(
		f'agent-browser eval {json.dumps(js)}',
		capture_output=True, text=True, timeout=30, shell=True
	)
	raw = result.stdout.strip()

	try:
		# agent-browser wraps eval output in quotes with escaped inner quotes
		# e.g. '"[{\"gameID\":...}]"' — strip outer quotes and unescape
		stripped = raw.strip('"').replace('\\"', '"')
		match = re.search(r'\[.*\]', stripped, re.DOTALL)
		if match:
			return json.loads(match.group())
	except (json.JSONDecodeError, AttributeError):
		pass

	return []


def main():
	parser = argparse.ArgumentParser(description="Discover game IDs via agent-browser")
	parser.add_argument("--season", required=True, help="Season year")
	parser.add_argument("--division", type=int, default=1, help="Division")
	parser.add_argument("--start-date", help="Start date MM/DD/YYYY")
	parser.add_argument("--end-date", help="End date MM/DD/YYYY")
	parser.add_argument("--output", default="game_ids.json", help="Output filename")
	args = parser.parse_args()

	config = load_config()
	div_id = config["season_division_ids"][str(args.division)].get(args.season)
	if not div_id:
		print(f"Error: No season_division_id for {args.season} D{args.division}", file=sys.stderr)
		sys.exit(1)

	base_url = f"https://stats.ncaa.org/season_divisions/{div_id}/livestream_scoreboards"

	rl = config.get("browser_rate_limiting", {})
	page_load_wait = rl.get("page_load_wait", 8)
	between_dates = rl.get("between_dates", 4)

	date_ranges = config.get("date_ranges", {})
	start_str = args.start_date or date_ranges.get("start_date", "01/30/2026")
	end_str = args.end_date or date_ranges.get("end_date", "06/01/2026")
	start = datetime.strptime(start_str, "%m/%d/%Y")
	end = datetime.strptime(end_str, "%m/%d/%Y")

	all_games = []
	seen_ids = set()
	daily_counts = []

	date = start
	while date <= end:
		date_str = date.strftime("%m/%d/%Y")
		games = scrape_date(base_url, date_str, page_load_wait)

		new_count = 0
		for g in games:
			if g["gameID"] not in seen_ids:
				seen_ids.add(g["gameID"])
				g["date"] = date_str
				all_games.append(g)
				new_count += 1

		daily_counts.append({"date": date_str, "game_count": new_count})
		print(f"{new_count} games on {date_str}")

		date += timedelta(days=1)
		time.sleep(between_dates)

	# Save
	output_dir = get_season_raw_dir(args.season, args.division)
	output_path = output_dir / args.output
	with open(output_path, "w") as f:
		json.dump(all_games, f, indent=2)

	counts_path = output_dir / args.output.replace(".json", "_daily_counts.json")
	with open(counts_path, "w") as f:
		json.dump(daily_counts, f, indent=2)

	print(f"\nSaved {len(all_games)} unique games to {output_path}")


if __name__ == "__main__":
	main()

#!/usr/bin/env python3
"""
Extract detailed play-by-play data from NCAA lacrosse games.

This script fetches comprehensive play-by-play information from NCAA game pages,
parsing quarter-by-quarter events including goals, assists, penalties, and other
game actions. Typically called by main.py during batch processing.

Usage (usually called by main.py):
    python3 scripts/fetch_game_plays.py --test 6309665
    python3 scripts/fetch_game_plays.py --config config.json --test 6309665
    python3 scripts/fetch_game_plays.py 6309665  # outputs to stdout

Output:
    - data/{season}/games/game_{id}_plays.json: Detailed play-by-play events by quarter
    - stdout: JSON output when not in test mode
"""

import requests
from bs4 import BeautifulSoup
import json
import argparse
import os
import sys
import time
import random
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.path_helpers import get_game_file_path, get_season_from_date


def load_config(config_file="config.json"):
	"""Load configuration from JSON file."""
	# If running from scripts folder, look for config in parent directory
	if not Path(config_file).exists() and Path.cwd().name == "scripts":
		config_file = f"../{config_file}"
	
	try:
		with open(config_file, 'r') as f:
			return json.load(f)
	except FileNotFoundError:
		print(f"Warning: Config file {config_file} not found. Using defaults.", file=sys.stderr)
		return {
			"rate_limiting": {
				"base_delay": 0.625,
				"random_jitter": [0.125, 0.375]
			},
			"scraping": {
				"user_agents": ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"]
			}
		}
	except json.JSONDecodeError as e:
		print(f"Error reading config file: {e}", file=sys.stderr)
		sys.exit(1)


def apply_rate_limiting(config):
	"""Apply rate limiting delay with jitter."""
	base_delay = config.get("rate_limiting", {}).get("base_delay", 0.625)
	jitter_range = config.get("rate_limiting", {}).get("random_jitter", [0.125, 0.375])
	
	jitter = random.uniform(jitter_range[0], jitter_range[1])
	delay = base_delay + jitter
	
	time.sleep(delay)


def normalize_quarter(quarter_text):
	"""Convert quarter text like '1st', '2nd', '3rd', '4th' to numbers 1, 2, 3, 4"""
	if not quarter_text:
		return "Unknown"
	
	quarter_text = quarter_text.lower().strip()
	if "1st" in quarter_text:
		return "1"
	elif "2nd" in quarter_text:
		return "2"
	elif "3rd" in quarter_text:
		return "3"
	elif "4th" in quarter_text:
		return "4"
	else:
		return quarter_text

def extract_play_by_play(game_id, config=None):
	if config is None:
		config = load_config()
	
	# Apply rate limiting
	apply_rate_limiting(config)
	
	url = f"https://stats.ncaa.org/contests/{game_id}/play_by_play"
	
	# Use configured user agent
	user_agents = config.get("scraping", {}).get("user_agents", ["Mozilla/5.0"])
	headers = {"User-Agent": random.choice(user_agents)}
	
	resp = requests.get(url, headers=headers)
	soup = BeautifulSoup(resp.text, "html.parser")

	play_by_play = []

	quarter_cards = soup.select(".card.table-responsive")
	for card in quarter_cards:
		quarter_header = card.select_one(".card-header")
		quarter_raw = quarter_header.get_text(strip=True) if quarter_header else "Unknown"
		quarter = normalize_quarter(quarter_raw)

		rows = card.select("table tbody tr")
		for row in rows:
			cells = row.find_all("td")
			if len(cells) != 4:
				continue

			event = {
				"quarter": quarter,
				"time": cells[0].get_text(strip=True),
				"home_event": cells[1].get_text(strip=True),
				"score": cells[2].get_text(strip=True),
				"away_event": cells[3].get_text(strip=True)
			}
			play_by_play.append(event)

	return play_by_play

def main():
	parser = argparse.ArgumentParser(description="Extract play-by-play data from NCAA lacrosse games")
	parser.add_argument("--test", action="store_true", help="Run in test mode")
	parser.add_argument("--config", default="config.json", help="Configuration file path")
	parser.add_argument("--season", help="Season ID (year). If not provided, will attempt to infer from game info file")
	parser.add_argument("--division", type=int, default=None,
	                    choices=[1, 2, 3],
	                    help="NCAA division (1, 2, or 3). Default from config.json or 1.")
	parser.add_argument("game_id", nargs="?", help="Game ID to process")

	args = parser.parse_args()

	if not args.game_id:
		print("Error: Game ID is required", file=sys.stderr)
		parser.print_help()
		exit(1)

	# Load config
	config = load_config(args.config)

	# Get division from args or config
	division = args.division if args.division is not None else config.get('division', 1)

	# Remove leading dashes if present (handles --6309665 format)
	game_id = args.game_id.lstrip("-")

	print(f"Processing game ID: {game_id}")
	print(f"URL: https://stats.ncaa.org/contests/{game_id}/play_by_play")

	try:
		events = extract_play_by_play(game_id, config)

		if args.test:
			# Determine season
			season_id = args.season
			if not season_id:
				# Try to get season and division from existing game info file
				from utils.path_helpers import get_all_game_files
				for sid, div, gid, file_path in get_all_game_files():
					if gid == game_id:
						season_id = sid
						if div is not None:
							division = div
						break

				if not season_id:
					# If no game info found, try to infer from any existing files in data/
					data_path = Path("data")
					for season_dir in data_path.iterdir():
						if season_dir.is_dir() and season_dir.name.isdigit():
							# Check new structure: data/{season}/division{n}/games/
							for div_dir in season_dir.iterdir():
								if div_dir.is_dir() and div_dir.name.startswith("division"):
									games_dir = div_dir / "games"
									info_file = games_dir / f"game_{game_id}_info.json"
									if info_file.exists():
										with open(info_file) as f:
											game_data = json.load(f)
											season_id = get_season_from_date(game_data["gameDate"])
										# Extract division from directory name
										try:
											division = int(div_dir.name.replace("division", ""))
										except ValueError:
											pass
										break
							if season_id:
								break

				if not season_id:
					print("Error: Could not determine season. Please provide --season or ensure game info file exists", file=sys.stderr)
					exit(1)

			# Get season and division-aware file path
			output_file = get_game_file_path(game_id, "plays", season_id, division)

			with open(output_file, "w", encoding="utf-8") as f:
				json.dump(events, f, indent=2)

			print(f"Play-by-play data saved to: {output_file}")
			print(f"Total events extracted: {len(events)}")
		else:
			# Print to stdout in normal mode
			print(json.dumps(events, indent=2))

	except Exception as e:
		print(f"Error processing game {game_id}: {e}", file=sys.stderr)
		exit(1)

if __name__ == "__main__":
	import sys
	main()
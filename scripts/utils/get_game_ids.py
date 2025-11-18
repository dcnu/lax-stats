#!/usr/bin/env python3
"""
Extract game IDs from NCAA lacrosse statistics for a specified date range.

This utility script fetches game IDs and team information from the NCAA stats
website by querying daily scoreboards. Outputs structured JSON data for use
by the main processing pipeline.

Usage (run from project root):
    python3 scripts/utils/get_game_ids.py --season 2025
    python3 scripts/utils/get_game_ids.py --season 2025 --start-date 02/01/2025 --end-date 02/28/2025
    python3 scripts/utils/get_game_ids.py --season 2025 --test --start-date 02/15/2025

Output:
    - data/{season}/raw/game_ids.json: Game IDs with dates and team information
    - data/{season}/raw/game_ids_daily_counts.json: Daily game counts for verification
"""

import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta
import argparse
import sys
import time
import random
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.path_helpers import get_season_raw_dir

def get_base_url(division, season_id, config):
	"""
	Get the base URL for a specific division and season.

	Args:
		division: NCAA division (1, 2, or 3)
		season_id: Season ID (year as string)
		config: Config dict with season_division_ids

	Returns:
		Base URL for NCAA scoreboard queries

	Raises:
		ValueError: If division/season combination not configured
	"""
	season_div_ids = config.get('season_division_ids', {})
	div_ids = season_div_ids.get(str(division), {})

	if str(season_id) not in div_ids:
		raise ValueError(
			f"Season {season_id} not configured for Division {division}. "
			f"Available seasons: {list(div_ids.keys())}"
		)

	division_id = div_ids[str(season_id)]
	if division_id is None:
		raise ValueError(
			f"Division {division} season {season_id} ID not yet discovered. "
			f"Update config.json with NCAA season_division_id."
		)

	return f"https://stats.ncaa.org/season_divisions/{division_id}/livestream_scoreboards"


def load_config(config_file="config.json"):
    """Load configuration from JSON file."""
    # If running from utils folder, look for config in parent directory
    if not Path(config_file).exists() and Path.cwd().name == "utils":
        config_file = f"../{config_file}"
    
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: Config file {config_file} not found. Using defaults.", file=sys.stderr)
        return {
            "date_ranges": {
                "start_date": "02/01/2025",
                "end_date": "05/26/2025"
            }
        }
    except json.JSONDecodeError as e:
        print(f"Error reading config file: {e}", file=sys.stderr)
        sys.exit(1)


def apply_rate_limiting(config):
	"""Apply rate limiting delay with jitter."""
	rate_limiting = config.get("rate_limiting", {})
	base_delay = rate_limiting.get("base_delay", 0.625)
	jitter_range = rate_limiting.get("random_jitter", [0.125, 0.375])
	
	jitter = random.uniform(jitter_range[0], jitter_range[1])
	delay = base_delay + jitter
	
	time.sleep(delay)


def scrape_games(start_date_str, end_date_str, season_id, division=1, output_file="game_ids.json", config=None, debug=False):
	if config is None:
		config = load_config()

	# Get division and season-specific base URL
	base_url = get_base_url(division, season_id, config)

	if debug:
		print(f"DEBUG: Season ID: {season_id}")
		print(f"DEBUG: Division: {division}")
		season_div_ids = config.get('season_division_ids', {})
		div_id = season_div_ids.get(str(division), {}).get(str(season_id))
		print(f"DEBUG: Division ID: {div_id}")
		print(f"DEBUG: Base URL: {base_url}")

	start_date = datetime.strptime(start_date_str, "%m/%d/%Y")
	end_date = datetime.strptime(end_date_str, "%m/%d/%Y")
	results = []
	daily_counts = []

	# Use configured user agents
	user_agents = config.get("scraping", {}).get("user_agents", ["Mozilla/5.0"])

	# Create a session for cookie persistence
	session = requests.Session()

	# Add comprehensive browser-like headers
	base_headers = {
		"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
		"Accept-Language": "en-US,en;q=0.9",
		"Accept-Encoding": "gzip, deflate, br",
		"DNT": "1",
		"Connection": "keep-alive",
		"Upgrade-Insecure-Requests": "1",
		"Sec-Fetch-Dest": "document",
		"Sec-Fetch-Mode": "navigate",
		"Sec-Fetch-Site": "same-origin",
		"Cache-Control": "max-age=0"
	}

	date = start_date
	blocked_count = 0
	max_blocked = 3

	while date <= end_date:
		# Apply rate limiting before each request
		apply_rate_limiting(config)

		date_str = date.strftime("%m/%d/%Y")
		params = {
			"utf8": "✓",
			"season_division_id": "",
			"game_date": date_str,
			"conference_id": "0",
			"tournament_id": "",
			"commit": "Submit"
		}

		# Combine base headers with random user agent
		headers = base_headers.copy()
		headers["User-Agent"] = random.choice(user_agents)
		headers["Referer"] = "https://stats.ncaa.org/"

		if debug:
			# Construct full URL for debugging
			from urllib.parse import urlencode
			full_url = f"{base_url}?{urlencode(params)}"
			print(f"\nDEBUG: Requesting URL: {full_url}")
			print(f"DEBUG: User-Agent: {headers['User-Agent']}")

		resp = session.get(base_url, params=params, headers=headers, timeout=15)

		if debug:
			print(f"DEBUG: Response status: {resp.status_code}")
			print(f"DEBUG: Response length: {len(resp.text)} bytes")

		# Check for blocking
		if resp.status_code == 403:
			blocked_count += 1
			print(f"WARNING: Request blocked (403) for {date_str}. Attempt {blocked_count}/{max_blocked}")

			if blocked_count >= max_blocked:
				print(f"ERROR: Blocked {blocked_count} times. NCAA firewall is blocking requests.")
				print("Possible solutions:")
				print("  1. Wait several hours/days for rate limit to expire")
				print("  2. Use a VPN or different IP address")
				print("  3. Increase delays in config.json")
				print("  4. Run script during off-peak hours")
				break

			# Exponential backoff on blocking
			backoff_delay = 30 * (2 ** (blocked_count - 1))
			print(f"Backing off for {backoff_delay} seconds...")
			time.sleep(backoff_delay)
			continue

		# Reset blocked count on successful request
		if resp.status_code == 200:
			blocked_count = 0

		soup = BeautifulSoup(resp.text, "html.parser")

		daily_games = 0
		game_ids_found = set()

		# Find contest rows to extract game IDs and team IDs
		# Games span multiple rows with same contest_<game_id> ID
		game_teams = {}
		all_tr_with_ids = soup.find_all("tr", id=True)

		if debug:
			print(f"DEBUG: Found {len(all_tr_with_ids)} <tr> elements with id attributes")
			contest_trs = [tr for tr in all_tr_with_ids if tr.get("id", "").startswith("contest_")]
			print(f"DEBUG: Found {len(contest_trs)} <tr> elements with contest_ prefix")
			if len(contest_trs) > 0:
				print(f"DEBUG: First contest ID: {contest_trs[0].get('id')}")

		for tr in all_tr_with_ids:
			if tr.get("id", "").startswith("contest_"):
				game_id = tr.get("id").replace("contest_", "")

				# Initialize team list for this game if not seen
				if game_id not in game_teams:
					game_teams[game_id] = []

				# Extract team IDs from href attributes within this contest row
				for a in tr.find_all("a", href=True):
					if "/teams/" in a["href"]:
						team_id = a["href"].split("/teams/")[1].split("/")[0]
						if team_id.isdigit() and team_id not in game_teams[game_id]:
							game_teams[game_id].append(team_id)

		if debug:
			print(f"DEBUG: Parsed {len(game_teams)} unique games from HTML")

		# Convert to results format
		for game_id, team_ids in game_teams.items():
			results.append({
				"gameID": game_id,
				"date": date_str,
				"teamIDs": team_ids
			})
			daily_games += 1

		daily_counts.append({"date": date_str, "game_count": daily_games})
		print(f"{daily_games} games on {date_str}")

		if debug and daily_games == 0:
			# Save HTML for inspection
			debug_file = f"/tmp/ncaa_response_{date_str.replace('/', '_')}.html"
			with open(debug_file, 'w', encoding='utf-8') as f:
				f.write(resp.text)
			print(f"DEBUG: Saved response HTML to {debug_file}")
			break  # Stop after first day with 0 games in debug mode

		date += timedelta(days=1)

	total_found = len(results)
	
	unique_games = []
	seen_game_ids = set()
	duplicates_found = 0
	
	for game in results:
		if game["gameID"] not in seen_game_ids:
			unique_games.append(game)
			seen_game_ids.add(game["gameID"])
		else:
			duplicates_found += 1
	
	# Get season and division-specific raw directory
	output_dir = get_season_raw_dir(season_id, division)

	# Write to season raw directory
	output_path = output_dir / output_file
	with open(output_path, 'w', encoding='utf-8') as f:
		json.dump(unique_games, f, indent=2)
	
	# Save daily counts for error checking
	counts_file = output_file.replace('.json', '_daily_counts.json')
	counts_path = output_dir / counts_file
	with open(counts_path, 'w', encoding='utf-8') as f:
		json.dump(daily_counts, f, indent=2)
	
	print(f"Found {total_found} total games")
	if duplicates_found > 0:
		print(f"Found {duplicates_found} duplicate game IDs")
	print(f"Saved {len(unique_games)} unique games to {output_path}")
	print(f"Saved daily counts to {counts_path}")

def test_single_date(test_date, season_id, division=1, output_file=None, config=None, debug=False):
	if config is None:
		config = load_config()

	# Get division and season-specific base URL
	base_url = get_base_url(division, season_id, config)

	if debug:
		print(f"DEBUG: Season ID: {season_id}")
		print(f"DEBUG: Division: {division}")
		season_div_ids = config.get('season_division_ids', {})
		div_id = season_div_ids.get(str(division), {}).get(str(season_id))
		print(f"DEBUG: Division ID: {div_id}")
		print(f"DEBUG: Base URL: {base_url}")

	# Apply rate limiting
	apply_rate_limiting(config)

	params = {
		"utf8": "✓",
		"season_division_id": "",
		"game_date": test_date,
		"conference_id": "0",
		"tournament_id": "",
		"commit": "Submit"
	}

	# Use configured user agent
	user_agents = config.get("scraping", {}).get("user_agents", ["Mozilla/5.0"])

	# Create a session and add comprehensive browser-like headers
	session = requests.Session()
	headers = {
		"User-Agent": random.choice(user_agents),
		"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
		"Accept-Language": "en-US,en;q=0.9",
		"Accept-Encoding": "gzip, deflate, br",
		"DNT": "1",
		"Connection": "keep-alive",
		"Upgrade-Insecure-Requests": "1",
		"Sec-Fetch-Dest": "document",
		"Sec-Fetch-Mode": "navigate",
		"Sec-Fetch-Site": "same-origin",
		"Referer": "https://stats.ncaa.org/",
		"Cache-Control": "max-age=0"
	}

	if debug:
		# Construct full URL for debugging
		from urllib.parse import urlencode
		full_url = f"{base_url}?{urlencode(params)}"
		print(f"DEBUG: Requesting URL: {full_url}")
		print(f"DEBUG: User-Agent: {headers['User-Agent']}")

	resp = session.get(base_url, params=params, headers=headers, timeout=15)

	if debug:
		print(f"DEBUG: Response status: {resp.status_code}")
		print(f"DEBUG: Response length: {len(resp.text)} bytes")

	# Check for blocking
	if resp.status_code == 403:
		print(f"ERROR: Request blocked (403) by NCAA firewall")
		print("The NCAA website is currently blocking automated requests.")
		print("Possible solutions:")
		print("  1. Wait several hours/days for rate limit to expire")
		print("  2. Use a VPN or different IP address")
		print("  3. Increase delays in config.json")
		print("  4. Run script during off-peak hours")
		if debug:
			debug_file = f"/tmp/ncaa_403_response_{test_date.replace('/', '_')}.html"
			with open(debug_file, 'w', encoding='utf-8') as f:
				f.write(resp.text)
			print(f"DEBUG: Saved 403 response to {debug_file}")
		return

	soup = BeautifulSoup(resp.text, "html.parser")

	results = []

	# Find contest rows to extract game IDs and team IDs
	# Games span multiple rows with same contest_<game_id> ID
	game_teams = {}
	all_tr_with_ids = soup.find_all("tr", id=True)

	if debug:
		print(f"DEBUG: Found {len(all_tr_with_ids)} <tr> elements with id attributes")
		contest_trs = [tr for tr in all_tr_with_ids if tr.get("id", "").startswith("contest_")]
		print(f"DEBUG: Found {len(contest_trs)} <tr> elements with contest_ prefix")
		if len(contest_trs) > 0:
			print(f"DEBUG: First contest ID: {contest_trs[0].get('id')}")

	for tr in all_tr_with_ids:
		if tr.get("id", "").startswith("contest_"):
			game_id = tr.get("id").replace("contest_", "")

			# Initialize team list for this game if not seen
			if game_id not in game_teams:
				game_teams[game_id] = []

			# Extract team IDs from href attributes within this contest row
			for a in tr.find_all("a", href=True):
				if "/teams/" in a["href"]:
					team_id = a["href"].split("/teams/")[1].split("/")[0]
					if team_id.isdigit() and team_id not in game_teams[game_id]:
						game_teams[game_id].append(team_id)

	if debug:
		print(f"DEBUG: Parsed {len(game_teams)} unique games from HTML")

	# Convert to results format
	for game_id, team_ids in game_teams.items():
		results.append({
			"gameID": game_id,
			"date": test_date,
			"teamIDs": team_ids
		})

	print(f"Found {len(results)} games on {test_date}")

	if debug and len(results) == 0:
		# Save HTML for inspection
		debug_file = f"/tmp/ncaa_response_{test_date.replace('/', '_')}.html"
		with open(debug_file, 'w', encoding='utf-8') as f:
			f.write(resp.text)
		print(f"DEBUG: Saved response HTML to {debug_file}")
	
	if output_file:
		# Get season and division-specific raw directory
		output_dir = get_season_raw_dir(season_id, division)

		# Write to season raw directory
		output_path = output_dir / output_file
		with open(output_path, 'w', encoding='utf-8') as f:
			json.dump(results, f, indent=2)
		print(f"Saved {len(results)} games to {output_path}")
	else:
		print("Games found:")
		for i, game in enumerate(results[:20]):
			team_str = f" (teams: {', '.join(game['teamIDs'])})" if game['teamIDs'] else " (no teams found)"
			print(f"  {game['gameID']} - {game['date']}{team_str}")
		if len(results) > 20:
			print(f"  ... and {len(results) - 20} more")

def main():
	parser = argparse.ArgumentParser(description="Scrape NCAA lacrosse game IDs from stats.ncaa.org")
	parser.add_argument("--season", required=True, help="Season ID (year, e.g., 2025)")
	parser.add_argument("--division", type=int, default=None,
	                    choices=[1, 2, 3],
	                    help="NCAA division (1, 2, or 3). Default from config.json or 1.")
	parser.add_argument("--config", default="config.json", help="Configuration file path (default: config.json)")
	parser.add_argument("--start-date", help="Start date in MM/DD/YYYY format (overrides config)")
	parser.add_argument("--end-date", help="End date in MM/DD/YYYY format (overrides config)")
	parser.add_argument("--test", action="store_true", help="Run test mode with single date (uses start-date)")
	parser.add_argument("--output", default="game_ids.json", help="Output JSON filename (default: game_ids.json)")
	parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")

	args = parser.parse_args()

	# Load configuration
	config = load_config(args.config)

	# Get division from args or config
	division = args.division if args.division is not None else config.get('division', 1)

	# Use command line args if provided, otherwise use config
	start_date = args.start_date or config.get("date_ranges", {}).get("start_date")
	end_date = args.end_date or config.get("date_ranges", {}).get("end_date")

	if not start_date:
		print("Error: Start date required (via --start-date or config.json)", file=sys.stderr)
		sys.exit(1)
	if not args.test and not end_date:
		print("Error: End date required (via --end-date or config.json)", file=sys.stderr)
		sys.exit(1)

	try:
		datetime.strptime(start_date, "%m/%d/%Y")
		if not args.test and end_date:
			datetime.strptime(end_date, "%m/%d/%Y")
	except ValueError:
		print("Error: Date format must be MM/DD/YYYY", file=sys.stderr)
		sys.exit(1)

	print(f"Season: {args.season}")
	print(f"Division: {division}")
	print(f"Using date range: {start_date} to {end_date if not args.test else start_date}")

	if args.test:
		test_output = f"test_{args.output}" if args.output == "game_ids.json" else args.output
		# If output is /dev/null, don't save file to see console output
		if args.output == "/dev/null":
			test_single_date(start_date, args.season, division, None, config, debug=args.debug)
		else:
			test_single_date(start_date, args.season, division, test_output, config, debug=args.debug)
	else:
		scrape_games(start_date, end_date, args.season, division, args.output, config, debug=args.debug)

if __name__ == "__main__":
	main()

#!/usr/bin/env python3
"""
Fetch game information and individual player statistics from NCAA lacrosse stats.

This script extracts comprehensive game metadata and individual player statistics
from a single NCAA game page. It outputs two separate JSON files: game information
and player statistics. Typically called by main.py during batch processing.

Usage (usually called by main.py):
    python3 scripts/fetch_game_data.py https://stats.ncaa.org/contests/6309665/individual_stats
    python3 scripts/fetch_game_data.py --url https://stats.ncaa.org/contests/6309665/individual_stats
    python3 scripts/fetch_game_data.py --config config.json https://stats.ncaa.org/contests/6309665/individual_stats

Output:
    - data/{season}/games/game_{id}_info.json: Game metadata (teams, scores, date, venue)
    - data/{season}/games/game_{id}_player_stats.json: Individual player statistics
"""

import requests
from bs4 import BeautifulSoup
import json
import argparse
import sys
import time
import random
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.path_helpers import get_season_from_date, get_game_file_path


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


def extract_game_info(soup, game_id):
    """Extract game metadata from the page."""
    try:
        # Get the first table-responsive div
        table_div = soup.find("div", class_="table-responsive")
        if not table_div:
            raise ValueError("No table-responsive div found")
        
        table = table_div.find("table")
        if not table:
            raise ValueError("No table found in table-responsive div")
        
        rows = table.find_all("tr")
        if not rows:
            raise ValueError("No rows found in table")
        
        first_row = rows[0]
        cells = first_row.find_all("td")
        
        if len(cells) < 30:
            raise ValueError(f"Expected at least 30 cells, found {len(cells)}")
        
        # Detect if this is an overtime game by checking for overtime columns
        # Overtime games have extra columns (1OT, 2OT, etc.) that shift positions
        is_overtime = len(cells) > 30
        ot_shift = len(cells) - 30 if is_overtime else 0
        
        # Extract team information from the correct cells
        # Cell 1: Away team info (always the same)
        away_team_cell = cells[1]
        away_team_link = away_team_cell.find("a")
        if not away_team_link:
            raise ValueError("Away team link not found")
        away_team = away_team_link.get_text(strip=True)
        away_team_id = away_team_link.get('href', '').split('/')[-1] if away_team_link.get('href') else None
        
        # Home team position shifts in overtime games
        home_team_pos = 27 + ot_shift
        if home_team_pos >= len(cells):
            raise ValueError(f"Home team position {home_team_pos} exceeds cell count {len(cells)}")
        
        home_team_cell = cells[home_team_pos]
        home_team_link = home_team_cell.find("a")
        if not home_team_link:
            raise ValueError("Home team link not found")
        home_team = home_team_link.get_text(strip=True)
        home_team_id = home_team_link.get('href', '').split('/')[-1] if home_team_link.get('href') else None
        
        # Scores - away is always cell 3, home shifts in overtime
        away_score = int(cells[3].get_text(strip=True))
        home_score_pos = 29 + ot_shift
        home_score = int(cells[home_score_pos].get_text(strip=True))
        
        # Game details positions also shift in overtime
        game_date_pos = 23 + ot_shift
        location_pos = 24 + ot_shift
        attendance_pos = 25 + ot_shift
        
        game_date = cells[game_date_pos].get_text(strip=True)
        location = cells[location_pos].get_text(strip=True)
        attendance_text = cells[attendance_pos].get_text(strip=True)
        
        # Clean up attendance
        attendance_clean = attendance_text.replace("Attendance: ", "").replace(",", "").strip()
        attendance = int(attendance_clean) if attendance_clean.isdigit() else 0
        
        return {
            "gameId": game_id,
            "awayTeam": away_team,
            "awayTeamId": away_team_id,
            "awayScore": away_score,
            "homeTeam": home_team,
            "homeTeamId": home_team_id,
            "homeScore": home_score,
            "location": location,
            "attendance": attendance,
            "gameDate": game_date,
            "isOvertime": is_overtime,
            "overtimePeriods": ot_shift
        }
        
    except (AttributeError, IndexError, ValueError) as e:
        raise ValueError(f"Failed to extract game info: {e}")


def extract_player_stats(soup):
    """Extract individual player statistics from the page."""
    results = []
    for table in soup.select('table.dataTable'):
        thead = table.find('thead')
        if not thead:
            continue
            
        header_ths = thead.find_all('th')
        fields = [th.get_text(" ", strip=True).replace('FO Won', 'FO_Won').replace('FOs Taken', 'FOs_Taken') for th in header_ths][3:]
        
        tbody = table.find('tbody')
        if not tbody:
            continue
            
        for row in tbody.find_all('tr', id=lambda x: x and x.startswith('game_player')):
            cells = row.find_all('td')
            if len(cells) < 3:
                continue
                
            jersey = cells[0].get_text(strip=True)
            link = cells[1].find('a')
            
            # Skip rows without player links (totals, etc.)
            if not link or not link.get('href'):
                continue
                
            try:
                player_id = int(link['href'].split('/')[-1])
            except (ValueError, IndexError):
                continue
                
            name = link.get_text(strip=True)
            position = cells[2].get_text(strip=True)
            values = [c.get_text(strip=True) for c in cells[3:]]
            stats = dict(zip(fields, values))
            stats['jersey'] = jersey
            stats['position'] = position
            stats['playerId'] = player_id
            stats['name'] = name
            results.append(stats)
    
    return results


def scrape_game_data(url, config=None):
    """Scrape both game info and player stats from a single request."""
    if config is None:
        config = load_config()
    
    # Apply rate limiting
    apply_rate_limiting(config)
    
    game_id = url.split("/")[4]
    
    # Use configured user agent
    user_agents = config.get("scraping", {}).get("user_agents", ["Mozilla/5.0"])
    headers = {'User-Agent': random.choice(user_agents)}
    
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    game_info = extract_game_info(soup, game_id)
    player_stats = extract_player_stats(soup)
    
    return game_info, player_stats


def main():
    parser = argparse.ArgumentParser(description="Scrape NCAA lacrosse game data")
    parser.add_argument("url", nargs="?", help="Game individual stats URL")
    parser.add_argument("--url", help="Game individual stats URL (alternative flag)")
    parser.add_argument("--division", type=int, default=None,
                        choices=[1, 2, 3],
                        help="NCAA division (1, 2, or 3). Default from config.json or 1.")
    parser.add_argument("--config", default="config.json", help="Configuration file path")

    args = parser.parse_args()

    url = args.url or getattr(args, 'url', None)
    if not url:
        print("Error: URL is required", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    # Load config
    config = load_config(args.config)

    # Get division from args or config
    division = args.division if args.division is not None else config.get('division', 1)

    try:
        game_info, player_stats = scrape_game_data(url, config)
        game_id = game_info["gameId"]

        # Determine season from game date
        season_id = get_season_from_date(game_info["gameDate"])

        # Get season and division-aware file paths
        info_filename = get_game_file_path(game_id, "info", season_id, division)
        stats_filename = get_game_file_path(game_id, "player_stats", season_id, division)

        # Write game info
        with open(info_filename, 'w', encoding='utf-8') as f:
            json.dump(game_info, f, indent=2)
        print(f"Game info written to {info_filename}")

        # Write player stats
        with open(stats_filename, 'w', encoding='utf-8') as f:
            json.dump(player_stats, f, indent=2)
        print(f"Player stats written to {stats_filename}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
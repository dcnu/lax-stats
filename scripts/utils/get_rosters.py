#!/usr/bin/env python3
"""
Extract comprehensive roster information for all NCAA lacrosse teams.

This utility script fetches detailed player and goalkeeper roster data for each
team ID found in the team_ids.json file. It extracts biographical information,
statistics, and performance data from both field player and goalkeeper pages.

Usage (run from project root):
    python3 utils/get_rosters.py
    python3 utils/get_rosters.py --limit 5
    python3 utils/get_rosters.py --dry-run
    python3 utils/get_rosters.py --output data/raw/custom_rosters.json

Input:
    - data/raw/team_ids.json: Team IDs with game participation counts

Output:  
    - data/raw/rosters.json: Complete roster data with player statistics

Important Note:
    These URLs and category IDs (15649 for players, 15650 for goalkeepers) are
    specific to the 2024-2025 NCAA lacrosse season. Category IDs and team IDs
    change each year in the NCAA database and must be updated annually.
"""

import argparse
import json
import logging
import re
import ssl
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE_URL = "https://stats.ncaa.org"
PLAYERS_CATEGORY_ID = "15649"
GOALKEEPERS_CATEGORY_ID = "15650"

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def load_team_ids(team_ids_file: str) -> List[Dict[str, any]]:
	"""Load team IDs from JSON file."""
	try:
		with open(team_ids_file, 'r', encoding='utf-8') as f:
			return json.load(f)
	except FileNotFoundError:
		logger.error(f"Team IDs file not found: {team_ids_file}")
		sys.exit(1)
	except json.JSONDecodeError as e:
		logger.error(f"Invalid JSON in {team_ids_file}: {e}")
		sys.exit(1)


def fetch_page(url: str) -> str:
	"""Fetch a web page with error handling and rate limiting."""
	try:
		time.sleep(0.5)  # Rate limiting
		req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
		
		# Create SSL context that doesn't verify certificates
		ssl_context = ssl.create_default_context()
		ssl_context.check_hostname = False
		ssl_context.verify_mode = ssl.CERT_NONE
		
		with urlopen(req, context=ssl_context) as response:
			return response.read().decode('utf-8')
	except HTTPError as e:
		logger.error(f"HTTP error {e.code} for URL: {url}")
		return ""
	except URLError as e:
		logger.error(f"URL error for {url}: {e}")
		return ""
	except Exception as e:
		logger.error(f"Unexpected error fetching {url}: {e}")
		return ""


def extract_player_data(html: str, team_id: str, category: str) -> List[Dict[str, any]]:
	"""Extract player data from HTML table."""
	players = []
	
	# Find the statistics table - try multiple patterns
	table_patterns = [
		r'<table[^>]*class="[^"]*statsTable[^"]*"[^>]*>(.*?)</table>',
		r'<table[^>]*class="[^"]*dataTable[^"]*"[^>]*>(.*?)</table>',
		r'<table[^>]*id="stat_grid"[^>]*>(.*?)</table>'
	]
	
	table_match = None
	for pattern in table_patterns:
		table_match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
		if table_match:
			break
	
	if not table_match:
		logger.warning(f"No statistics table found for team {team_id}, category {category}")
		return players
	
	table_html = table_match.group(1)
	
	# Extract table rows
	row_pattern = r'<tr[^>]*>(.*?)</tr>'
	rows = re.findall(row_pattern, table_html, re.DOTALL | re.IGNORECASE)
	
	# Find header row to understand column structure
	header_row = None
	for row in rows[:3]:  # Check first few rows for header
		if re.search(r'<th[^>]*>', row, re.IGNORECASE):
			header_row = row
			break
	
	if not header_row:
		logger.warning(f"No header row found for team {team_id}, category {category}")
		return players
	
	# Extract header columns
	header_pattern = r'<th[^>]*>(.*?)</th>'
	headers = [re.sub(r'<[^>]+>', '', h).strip() for h in re.findall(header_pattern, header_row, re.DOTALL | re.IGNORECASE)]
	
	# Process data rows
	for row in rows:
		if re.search(r'<th[^>]*>', row, re.IGNORECASE):
			continue  # Skip header rows
		
		# Extract player link and data - try multiple patterns
		player_link_patterns = [
			r'<a[^>]*href="/players/(\d+)"[^>]*>(.*?)</a>',
			r'<a[^>]*href="/players/(\d+)\?[^"]*"[^>]*>(.*?)</a>'
		]
		
		player_match = None
		for pattern in player_link_patterns:
			player_match = re.search(pattern, row, re.IGNORECASE)
			if player_match:
				break
		
		if not player_match:
			continue  # Skip rows without player links
		
		player_id = player_match.group(1)
		player_name = re.sub(r'<[^>]+>', '', player_match.group(2)).strip()
		
		# Extract all cell data
		cell_pattern = r'<td[^>]*>(.*?)</td>'
		cells = [re.sub(r'<[^>]+>', '', cell).strip() for cell in re.findall(cell_pattern, row, re.DOTALL | re.IGNORECASE)]
		
		if not cells:
			continue
		
		# Create player record
		player_data = {
			"playerID": player_id,
			"name": player_name,
			"teamID": team_id,
			"category": category,
			"rosterNumber": None,
			"year": None,
			"statistics": {}
		}
		
		# Map cell data to headers
		for i, cell_value in enumerate(cells):
			if i < len(headers):
				header = headers[i].lower().replace(' ', '_')
				
				# Special handling for common fields
				if header in ['jersey', '#', 'no', 'number']:
					try:
						player_data["rosterNumber"] = int(cell_value) if cell_value.isdigit() else cell_value
					except ValueError:
						player_data["rosterNumber"] = cell_value
				elif header in ['yr', 'year', 'class']:
					player_data["year"] = cell_value
				elif cell_value and cell_value != '-':
					# Store as statistic
					player_data["statistics"][header] = cell_value
		
		players.append(player_data)
	
	return players


def get_team_roster(team_id: str, dry_run: bool = False) -> Dict[str, List[Dict[str, any]]]:
	"""Get complete roster for a team (players and goalkeepers)."""
	roster_data = {
		"teamID": team_id,
		"players": [],
		"goalkeepers": []
	}
	
	# Fetch players data
	players_url = f"{BASE_URL}/teams/{team_id}/season_to_date_stats?year_stat_category_id={PLAYERS_CATEGORY_ID}"
	logger.info(f"Fetching players for team {team_id}")
	
	if not dry_run:
		players_html = fetch_page(players_url)
		if players_html:
			roster_data["players"] = extract_player_data(players_html, team_id, "players")
			logger.info(f"Found {len(roster_data['players'])} players for team {team_id}")
	
	# Fetch goalkeepers data
	goalkeepers_url = f"{BASE_URL}/teams/{team_id}/season_to_date_stats?year_stat_category_id={GOALKEEPERS_CATEGORY_ID}"
	logger.info(f"Fetching goalkeepers for team {team_id}")
	
	if not dry_run:
		goalkeepers_html = fetch_page(goalkeepers_url)
		if goalkeepers_html:
			roster_data["goalkeepers"] = extract_player_data(goalkeepers_html, team_id, "goalkeepers")
			logger.info(f"Found {len(roster_data['goalkeepers'])} goalkeepers for team {team_id}")
	
	return roster_data


def main():
	parser = argparse.ArgumentParser(description="Extract roster data for all NCAA lacrosse teams")
	parser.add_argument("--team-ids", default="data/raw/team_ids.json",
						help="Path to team IDs JSON file (default: data/raw/team_ids.json)")
	parser.add_argument("--output", default="data/raw/rosters.json",
						help="Output file path (default: data/raw/rosters.json)")
	parser.add_argument("--dry-run", action="store_true",
						help="Show what would be done without making HTTP requests")
	parser.add_argument("--limit", type=int,
						help="Limit number of teams to process (for testing)")
	
	args = parser.parse_args()
	
	# Load team IDs
	team_data = load_team_ids(args.team_ids)
	teams_to_process = team_data[:args.limit] if args.limit else team_data
	
	logger.info(f"Processing {len(teams_to_process)} teams")
	
	if args.dry_run:
		logger.info("DRY RUN - No HTTP requests will be made")
		for team in teams_to_process[:5]:  # Show first 5 teams
			team_id = team["teamID"]
			logger.info(f"Would fetch roster for team {team_id}")
		return
	
	# Create output directory if it doesn't exist
	output_path = Path(args.output)
	output_path.parent.mkdir(parents=True, exist_ok=True)
	
	# Process each team
	all_rosters = []
	
	try:
		for i, team in enumerate(teams_to_process, 1):
			team_id = team["teamID"]
			logger.info(f"Processing team {i}/{len(teams_to_process)}: {team_id}")
			
			roster_data = get_team_roster(team_id, dry_run=args.dry_run)
			all_rosters.append(roster_data)
			
			# Save progress periodically
			if i % 10 == 0:
				logger.info(f"Saving progress after {i} teams...")
				with open(args.output, 'w', encoding='utf-8') as f:
					json.dump(all_rosters, f, indent=2, ensure_ascii=False)
	
	except KeyboardInterrupt:
		logger.info("Process interrupted by user")
		
	finally:
		# Save final results
		if all_rosters:
			logger.info(f"Saving {len(all_rosters)} team rosters to {args.output}")
			with open(args.output, 'w', encoding='utf-8') as f:
				json.dump(all_rosters, f, indent=2, ensure_ascii=False)
			
			# Print summary
			total_players = sum(len(roster["players"]) + len(roster["goalkeepers"]) for roster in all_rosters)
			logger.info(f"Extraction complete: {len(all_rosters)} teams, {total_players} total players")


if __name__ == "__main__":
	main()
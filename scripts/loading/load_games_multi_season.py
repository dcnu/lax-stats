#!/usr/bin/env python3
"""
Load game data from scraped game info files into Supabase (Multi-Season Support).

Processes all game_*_info.json files from season-based directories and loads them
into the games table with proper date parsing, team ID mapping, and season assignment.

Usage:
	python3 scripts/load_games_multi_season.py
	python3 scripts/load_games_multi_season.py --season 2025
	python3 scripts/load_games_multi_season.py --data-dir data --dry-run
"""

import json
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
from supabase import create_client, Client

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.path_helpers import get_all_game_files, get_all_season_dirs

def load_config():
	"""Load Supabase configuration from config.json."""
	config_path = Path("config.json")
	if not config_path.exists():
		print("Error: config.json not found. Please create it with Supabase credentials.", file=sys.stderr)
		sys.exit(1)

	with open(config_path) as f:
		config = json.load(f)

	required_keys = ['supabase_url', 'supabase_key']
	for key in required_keys:
		if key not in config:
			print(f"Error: {key} not found in config.json", file=sys.stderr)
			sys.exit(1)

	return config

def parse_game_date(date_str):
	"""Parse game date from MM/DD/YYYY format to YYYY-MM-DD."""
	try:
		# Parse MM/DD/YYYY format
		date_obj = datetime.strptime(date_str, "%m/%d/%Y")
		return date_obj.strftime("%Y-%m-%d")
	except Exception as e:
		print(f"Warning: Could not parse date '{date_str}': {e}", file=sys.stderr)
		return None

def get_season_id(game_date):
	"""Determine season_id from game date (YYYY from date)."""
	try:
		date_obj = datetime.strptime(game_date, "%Y-%m-%d")
		return str(date_obj.year)
	except Exception as e:
		print(f"Warning: Could not extract season from date '{game_date}': {e}", file=sys.stderr)
		return None

def ensure_seasons_exist(games, supabase_client, dry_run=False):
	"""Ensure all seasons referenced by games exist in seasons table."""
	# Group games by season
	seasons_data = {}
	for game in games:
		season_id = game.get('season_id')
		if not season_id:
			continue

		if season_id not in seasons_data:
			date_obj = datetime.strptime(game['game_date'], "%Y-%m-%d")
			seasons_data[season_id] = {
				'id': season_id,
				'start_year': int(season_id),
				'end_year': int(season_id),
				'start_date': game['game_date'],
				'end_date': game['game_date'],
				'is_current': False,
				'division_id': game.get('division_id', 1)
			}
		else:
			# Update date range
			if game['game_date'] < seasons_data[season_id]['start_date']:
				seasons_data[season_id]['start_date'] = game['game_date']
			if game['game_date'] > seasons_data[season_id]['end_date']:
				seasons_data[season_id]['end_date'] = game['game_date']

	seasons = list(seasons_data.values())

	# Mark most recent season as current
	if seasons:
		most_recent = max(seasons, key=lambda s: s['start_year'])
		most_recent['is_current'] = True

	if dry_run:
		print(f"DRY RUN: Would ensure {len(seasons)} seasons exist:")
		for season in sorted(seasons, key=lambda s: s['start_year']):
			print(f"  {season['id']}: {season['start_date']} to {season['end_date']}")
		return

	print(f"Ensuring {len(seasons)} seasons exist...")

	try:
		for season in seasons:
			result = supabase_client.table('seasons').upsert(season).execute()
		print(f"Successfully ensured {len(seasons)} seasons exist")
	except Exception as e:
		print(f"Error ensuring seasons exist: {e}", file=sys.stderr)
		sys.exit(1)

def extract_games_from_info_files(data_dir="data", season_filter=None, division_filter=None):
	"""Extract games from all game info files in season and division-based directories."""
	data_path = Path(data_dir)
	if not data_path.exists():
		print(f"Error: Data directory {data_dir} not found", file=sys.stderr)
		sys.exit(1)

	# Get all game files from season directories
	game_files = get_all_game_files(season_id=season_filter, division=division_filter, base_dir=data_dir)

	if not game_files:
		if season_filter:
			print(f"Error: No game info files found for season {season_filter}", file=sys.stderr)
		else:
			print(f"Error: No game info files found in {data_dir}", file=sys.stderr)
		sys.exit(1)

	print(f"Processing {len(game_files)} game info files...")

	games = []
	for season_id, division, game_id, file_path in game_files:
		try:
			with open(file_path, 'r', encoding='utf-8') as f:
				game_data = json.load(f)

			# Validate required fields
			if not game_id:
				print(f"Warning: No gameId in {file_path}", file=sys.stderr)
				continue

			# Parse game date
			raw_date = game_data.get('gameDate')
			if not raw_date:
				print(f"Warning: No gameDate in {file_path}", file=sys.stderr)
				continue

			game_date = parse_game_date(raw_date)
			if not game_date:
				continue

			# Use season from directory structure
			# Verify it matches the game date
			date_season = get_season_id(game_date)
			if date_season != season_id:
				print(f"Warning: Season mismatch for {file_path}: directory={season_id}, date={date_season}", file=sys.stderr)

			# Extract team information
			home_team_id = game_data.get('homeTeamId')
			away_team_id = game_data.get('awayTeamId')

			if not home_team_id or not away_team_id:
				print(f"Warning: Missing team IDs in {file_path}", file=sys.stderr)
				continue

			game = {
				'id': game_id,
				'game_date': game_date,
				'season_id': season_id,
				'division_id': division,  # From directory structure
				'home_team_id': home_team_id,
				'away_team_id': away_team_id,
				'home_score': game_data.get('homeScore'),
				'away_score': game_data.get('awayScore'),
				'location': game_data.get('location'),
				'attendance': game_data.get('attendance')
			}

			games.append(game)

		except Exception as e:
			print(f"Warning: Error processing {file_path}: {e}", file=sys.stderr)
			continue

	return games

def load_games_to_supabase(games, supabase_client, dry_run=False):
	"""Load games into Supabase games table."""
	if dry_run:
		print(f"DRY RUN: Would load {len(games)} games:")
		for game in sorted(games, key=lambda x: x['game_date'])[:10]:
			home_score = game['home_score'] or 'N/A'
			away_score = game['away_score'] or 'N/A'
			print(f"  {game['id']}: {game['game_date']} (Season {game['season_id']}) - {game['home_team_id']} vs {game['away_team_id']} ({home_score}-{away_score})")
		if len(games) > 10:
			print(f"  ... and {len(games) - 10} more")
		return

	print(f"Loading {len(games)} games to Supabase...")

	# Load in batches to avoid timeout
	batch_size = 50
	loaded_count = 0

	try:
		for i in range(0, len(games), batch_size):
			batch = games[i:i + batch_size]
			result = supabase_client.table('games').upsert(batch).execute()
			loaded_count += len(result.data)
			print(f"Loaded batch {i//batch_size + 1}: {len(result.data)} games")

		print(f"Successfully loaded {loaded_count} games total")

		# Show date range
		if games:
			dates = [g['game_date'] for g in games if g['game_date']]
			seasons = [g['season_id'] for g in games if g['season_id']]
			if dates:
				print(f"Date range: {min(dates)} to {max(dates)}")
			if seasons:
				print(f"Seasons: {', '.join(sorted(set(seasons)))}")

	except Exception as e:
		print(f"Error loading games to Supabase: {e}", file=sys.stderr)
		sys.exit(1)

def ensure_team_seasons_exist(games, supabase_client, dry_run=False):
	"""Ensure all team-season combinations exist in team_seasons table."""
	team_seasons = {}

	for game in games:
		season_id = game.get('season_id')
		home_team_id = game.get('home_team_id')
		away_team_id = game.get('away_team_id')

		if not season_id or not home_team_id or not away_team_id:
			continue

		division_id = game.get('division_id', 1)

		# Add home team-season
		key = (home_team_id, season_id, division_id)
		if key not in team_seasons:
			team_seasons[key] = {
				'team_id': home_team_id,
				'season_id': season_id,
				'division_id': division_id,
				'team_name': home_team_id,  # Will be updated from teams table
				'conference': None
			}

		# Add away team-season
		key = (away_team_id, season_id, division_id)
		if key not in team_seasons:
			team_seasons[key] = {
				'team_id': away_team_id,
				'season_id': season_id,
				'division_id': division_id,
				'team_name': away_team_id,  # Will be updated from teams table
				'conference': None
			}

	team_seasons_list = list(team_seasons.values())

	if dry_run:
		print(f"DRY RUN: Would ensure {len(team_seasons_list)} team-season combinations exist")
		return

	print(f"Ensuring {len(team_seasons_list)} team-season combinations exist...")

	try:
		# Get team names from teams table
		teams_result = supabase_client.table('teams').select('id, name').execute()
		team_names = {team['id']: team['name'] for team in teams_result.data}

		# Update team_name from teams table
		for ts in team_seasons_list:
			if ts['team_id'] in team_names:
				ts['team_name'] = team_names[ts['team_id']]

		# Upsert team_seasons
		batch_size = 50
		for i in range(0, len(team_seasons_list), batch_size):
			batch = team_seasons_list[i:i + batch_size]
			supabase_client.table('team_seasons').upsert(batch).execute()

		print(f"Successfully ensured {len(team_seasons_list)} team-season combinations exist")
	except Exception as e:
		print(f"Error ensuring team-seasons exist: {e}", file=sys.stderr)
		sys.exit(1)

def main():
	parser = argparse.ArgumentParser(description="Load game data from info files to Supabase (multi-season)")
	parser.add_argument("--data-dir", default="data", help="Base data directory containing season folders")
	parser.add_argument("--season", help="Only load games from specific season (year)")
	parser.add_argument("--division", type=int, choices=[1, 2, 3],
	                    help="Only load games from specific division (1, 2, or 3)")
	parser.add_argument("--dry-run", action="store_true", help="Show what would be loaded without actually loading")

	args = parser.parse_args()

	# Extract games from info files
	games = extract_games_from_info_files(args.data_dir, season_filter=args.season, division_filter=args.division)

	if not games:
		print("No games found in info files", file=sys.stderr)
		sys.exit(1)

	print(f"Extracted {len(games)} games")

	# Show summary stats
	dates = [g['game_date'] for g in games if g['game_date']]
	seasons = [g['season_id'] for g in games if g['season_id']]
	if dates:
		print(f"Date range: {min(dates)} to {max(dates)}")
	if seasons:
		print(f"Seasons: {', '.join(sorted(set(seasons)))}")

	# Load to Supabase unless dry run
	supabase = None
	if not args.dry_run:
		config = load_config()
		supabase = create_client(config['supabase_url'], config['supabase_key'])

	# Ensure seasons exist first
	ensure_seasons_exist(games, supabase, args.dry_run)

	# Load games
	load_games_to_supabase(games, supabase, args.dry_run)

	# Ensure team_seasons exist
	ensure_team_seasons_exist(games, supabase, args.dry_run)

if __name__ == "__main__":
	main()

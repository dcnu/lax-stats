#!/usr/bin/env python3
"""
Load player game statistics from scraped player stats files into Supabase (Multi-Season Support).

Processes all game_*_player_stats.json files from season-based directories and loads
individual player statistics per game, handling both regular stats and goalie-specific stats.
Also updates player_seasons table with season-specific player attributes.

Usage:
	python3 scripts/load_player_stats_multi_season.py
	python3 scripts/load_player_stats_multi_season.py --season 2025
	python3 scripts/load_player_stats_multi_season.py --data-dir data --dry-run
"""

import json
import os
import sys
import argparse
from pathlib import Path
from collections import defaultdict
from supabase import create_client, Client

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.path_helpers import get_all_season_dirs

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

def safe_int(value, default=0):
	"""Safely convert value to int, return default if not possible."""
	if value is None or value == '':
		return default
	try:
		return int(value)
	except (ValueError, TypeError):
		return default

def safe_float(value, default=None):
	"""Safely convert value to float, return default if not possible."""
	if value is None or value == '':
		return default
	try:
		return float(value)
	except (ValueError, TypeError):
		return default

def get_game_metadata(game_id, supabase_client):
	"""Get season_id, home_team_id, away_team_id for a game."""
	try:
		result = supabase_client.table('games').select('season_id, home_team_id, away_team_id').eq('id', game_id).execute()
		if result.data and len(result.data) > 0:
			return result.data[0]
		return None
	except Exception as e:
		print(f"Warning: Error fetching game metadata for {game_id}: {e}", file=sys.stderr)
		return None

def extract_player_stats_from_files(data_dir="data", season_filter=None, division_filter=None, supabase_client=None):
	"""Extract player game stats from all player stats files in season and division-based directories."""
	data_path = Path(data_dir)
	if not data_path.exists():
		print(f"Error: Data directory {data_dir} not found", file=sys.stderr)
		sys.exit(1)

	# Get all season directories
	if season_filter:
		seasons = [(season_filter, data_path / season_filter)]
	else:
		seasons = get_all_season_dirs(data_dir)

	if not seasons:
		print(f"Error: No season directories found in {data_dir}", file=sys.stderr)
		sys.exit(1)

	# Collect all player stats files from season/division directories
	stats_files = []
	for season_id, season_path in seasons:
		# Check for division subdirectories (new structure)
		division_dirs = [d for d in season_path.iterdir() if d.is_dir() and d.name.startswith("division")]

		if division_dirs:
			# New structure: data/{season}/division{n}/games/
			for div_dir in division_dirs:
				try:
					division = int(div_dir.name.replace("division", ""))
					if division_filter and division != division_filter:
						continue
					games_dir = div_dir / "games"
					if games_dir.exists():
						for file_path in games_dir.glob("game_*_player_stats.json"):
							stats_files.append((season_id, division, file_path))
				except ValueError:
					continue
		else:
			# Old structure: data/{season}/games/ (assume division 1)
			games_dir = season_path / "games"
			if games_dir.exists():
				for file_path in games_dir.glob("game_*_player_stats.json"):
					stats_files.append((season_id, 1, file_path))

	if not stats_files:
		if season_filter:
			print(f"Error: No player stats files found for season {season_filter}", file=sys.stderr)
		else:
			print(f"Error: No player stats files found in {data_dir}", file=sys.stderr)
		sys.exit(1)

	print(f"Processing {len(stats_files)} player stats files...")

	player_stats = []
	# Cache game metadata to avoid repeated queries
	game_cache = {}

	for season_id, division, file_path in stats_files:
		try:
			# Extract game ID from filename
			game_id = file_path.stem.split('_')[1]  # game_6309366_player_stats -> 6309366

			# Get game metadata (season_id, teams)
			if game_id not in game_cache:
				if supabase_client:
					game_cache[game_id] = get_game_metadata(game_id, supabase_client)
				else:
					game_cache[game_id] = None

			game_meta = game_cache[game_id]
			if not game_meta:
				print(f"Warning: Could not get metadata for game {game_id}, skipping", file=sys.stderr)
				continue

			# Use season_id from directory, verify it matches game metadata
			game_season_id = game_meta['season_id']
			if game_season_id != season_id:
				print(f"Warning: Season mismatch for game {game_id}: directory={season_id}, metadata={game_season_id}", file=sys.stderr)

			home_team_id = game_meta['home_team_id']
			away_team_id = game_meta['away_team_id']

			with open(file_path, 'r', encoding='utf-8') as f:
				players_data = json.load(f)

			# Group players by team (assume first half is home, second half is away)
			# This is a heuristic - in reality, team_id would be in the scraped data
			midpoint = len(players_data) // 2

			for idx, player_data in enumerate(players_data):
				if 'playerId' not in player_data or 'name' not in player_data:
					continue

				player_id = player_data['playerId']

				# Heuristic: assign team based on position in file
				# TODO: Improve this by getting actual team from scraped data
				team_id = home_team_id if idx < midpoint else away_team_id

				# Check if this is goalie stats (has different structure)
				is_goalie_stat = 'G Min' in player_data

				if is_goalie_stat:
					# Handle goalie-specific stats
					stat = {
						'game_id': game_id,
						'player_id': player_id,
						'season_id': season_id,
						'division_id': division,
						'team_id': team_id,
						'jersey_number': player_data.get('jersey'),
						'position': player_data.get('position'),
						'minutes_played': None,  # Regular minutes not applicable for goalie stats
						'goals': 0,
						'assists': 0,
						'points': 0,
						'shots': 0,
						'shots_on_goal': 0,
						'ground_balls': 0,
						'turnovers': 0,
						'caused_turnovers': 0,
						'faceoff_wins': 0,
						'faceoffs_taken': 0,

						# Goalie-specific fields
						'goalie_minutes': player_data.get('G Min'),
						'goals_allowed': safe_int(player_data.get('Goals Allowed')),
						'gaa': safe_float(player_data.get('GAA')),
						'saves': safe_int(player_data.get('Saves')),
						'save_percentage': safe_float(player_data.get('Save Pct'))
					}
				else:
					# Handle regular player stats
					stat = {
						'game_id': game_id,
						'player_id': player_id,
						'season_id': season_id,
						'division_id': division,
						'team_id': team_id,
						'jersey_number': player_data.get('jersey'),
						'position': player_data.get('position'),
						'minutes_played': player_data.get('Min'),
						'goals': safe_int(player_data.get('Goals')),
						'assists': safe_int(player_data.get('Assists')),
						'points': safe_int(player_data.get('Points')),
						'shots': safe_int(player_data.get('Shots')),
						'shots_on_goal': safe_int(player_data.get('SOG')),
						'ground_balls': safe_int(player_data.get('GB')),
						'turnovers': safe_int(player_data.get('TO')),
						'caused_turnovers': safe_int(player_data.get('CT')),
						'faceoff_wins': safe_int(player_data.get('FO_Won')),
						'faceoffs_taken': safe_int(player_data.get('FOs_Taken')),

						# Goalie-specific fields (null for regular players)
						'goalie_minutes': None,
						'goals_allowed': 0,
						'gaa': None,
						'saves': 0,
						'save_percentage': None
					}

				player_stats.append(stat)

		except Exception as e:
			print(f"Warning: Error processing {file_path}: {e}", file=sys.stderr)
			continue

	return player_stats

def deduplicate_stats(player_stats):
	"""Deduplicate by (game_id, player_id, position) - keep first occurrence."""
	seen = set()
	deduplicated_stats = []
	duplicates_found = 0

	for stat in player_stats:
		key = (stat['game_id'], stat['player_id'], stat['position'])
		if key not in seen:
			seen.add(key)
			deduplicated_stats.append(stat)
		else:
			duplicates_found += 1

	if duplicates_found > 0:
		print(f"Note: Removed {duplicates_found} duplicate (game_id, player_id, position) tuples from source data")

	return deduplicated_stats

def build_player_seasons(player_stats):
	"""Build player_seasons records from player_game_stats."""
	# Track player attributes by (player_id, team_id, season_id, division_id)
	player_season_attrs = defaultdict(lambda: defaultdict(lambda: {'jerseys': [], 'positions': []}))

	for stat in player_stats:
		player_id = stat['player_id']
		team_id = stat['team_id']
		season_id = stat['season_id']
		division_id = stat.get('division_id', 1)
		jersey = stat.get('jersey_number')
		position = stat.get('position')

		key = (player_id, team_id, season_id, division_id)

		if jersey:
			player_season_attrs[key]['jerseys'].append(jersey)
		if position:
			player_season_attrs[key]['positions'].append(position)

	# Build player_seasons records
	player_seasons = []
	for (player_id, team_id, season_id, division_id), attrs in player_season_attrs.items():
		# Use most common jersey and position
		most_common_jersey = max(set(attrs['jerseys']), key=attrs['jerseys'].count) if attrs['jerseys'] else '0'
		most_common_position = max(set(attrs['positions']), key=attrs['positions'].count) if attrs['positions'] else None

		player_seasons.append({
			'player_id': player_id,
			'team_id': team_id,
			'season_id': season_id,
			'division_id': division_id,
			'jersey_number': most_common_jersey,
			'primary_position': most_common_position
		})

	return player_seasons

def load_player_stats_to_supabase(player_stats, supabase_client, dry_run=False):
	"""Load player stats into Supabase player_game_stats table."""
	player_stats = deduplicate_stats(player_stats)

	if dry_run:
		print(f"DRY RUN: Would load {len(player_stats)} player game stats:")
		for stat in player_stats[:10]:
			goals = stat['goals']
			assists = stat['assists']
			pos = stat['position'] or 'N/A'
			season = stat['season_id']
			team = stat['team_id']
			print(f"  Game {stat['game_id']}, Player {stat['player_id']} ({team}, Season {season}): {goals}G {assists}A ({pos})")
		if len(player_stats) > 10:
			print(f"  ... and {len(player_stats) - 10} more")
		return

	print(f"Loading {len(player_stats)} player game stats to Supabase...")

	# Load in batches to avoid timeout
	batch_size = 100
	loaded_count = 0

	try:
		for i in range(0, len(player_stats), batch_size):
			batch = player_stats[i:i + batch_size]
			result = supabase_client.table('player_game_stats').upsert(batch).execute()
			loaded_count += len(result.data)
			print(f"Loaded batch {i//batch_size + 1}: {len(result.data)} player stats")

		print(f"Successfully loaded {loaded_count} player game stats total")

	except Exception as e:
		print(f"Error loading player stats to Supabase: {e}", file=sys.stderr)
		sys.exit(1)

def load_player_seasons_to_supabase(player_seasons, supabase_client, dry_run=False):
	"""Load player_seasons records into Supabase."""
	if dry_run:
		print(f"DRY RUN: Would load {len(player_seasons)} player-season records")
		return

	print(f"Loading {len(player_seasons)} player-season records to Supabase...")

	# Load in batches
	batch_size = 100
	loaded_count = 0

	try:
		for i in range(0, len(player_seasons), batch_size):
			batch = player_seasons[i:i + batch_size]
			result = supabase_client.table('player_seasons').upsert(batch).execute()
			loaded_count += len(result.data)
			print(f"Loaded batch {i//batch_size + 1}: {len(result.data)} player-seasons")

		print(f"Successfully loaded {loaded_count} player-season records total")

	except Exception as e:
		print(f"Error loading player-seasons to Supabase: {e}", file=sys.stderr)
		sys.exit(1)

def refresh_materialized_view(supabase_client, dry_run=False):
	"""Refresh the player_season_stats materialized view."""
	if dry_run:
		print("DRY RUN: Would refresh player_season_stats materialized view")
		return

	print("Refreshing player_season_stats materialized view...")

	try:
		supabase_client.rpc('refresh_player_season_stats').execute()
		print("Successfully refreshed materialized view")
	except Exception as e:
		print(f"Warning: Could not refresh materialized view: {e}", file=sys.stderr)

def main():
	parser = argparse.ArgumentParser(description="Load player game stats from stats files to Supabase (multi-season)")
	parser.add_argument("--data-dir", default="data", help="Base data directory containing season folders")
	parser.add_argument("--season", help="Only load stats from specific season (year)")
	parser.add_argument("--division", type=int, choices=[1, 2, 3],
	                    help="Only load stats from specific division (1, 2, or 3)")
	parser.add_argument("--dry-run", action="store_true", help="Show what would be loaded without actually loading")

	args = parser.parse_args()

	# Load Supabase client
	supabase = None
	if not args.dry_run:
		config = load_config()
		supabase = create_client(config['supabase_url'], config['supabase_key'])

	# Extract player stats from files
	player_stats = extract_player_stats_from_files(args.data_dir, season_filter=args.season,
	                                               division_filter=args.division, supabase_client=supabase)

	if not player_stats:
		print("No player stats found in files", file=sys.stderr)
		sys.exit(1)

	print(f"Extracted {len(player_stats)} player game statistics")

	# Show summary stats
	total_goals = sum(stat['goals'] for stat in player_stats)
	total_assists = sum(stat['assists'] for stat in player_stats)
	unique_games = len(set(stat['game_id'] for stat in player_stats))
	unique_players = len(set(stat['player_id'] for stat in player_stats))
	unique_seasons = len(set(stat['season_id'] for stat in player_stats))

	print(f"Summary: {unique_games} games, {unique_players} unique players, {unique_seasons} seasons")
	print(f"Total goals: {total_goals}, Total assists: {total_assists}")

	# Load player stats
	load_player_stats_to_supabase(player_stats, supabase, args.dry_run)

	# Build and load player_seasons
	player_seasons = build_player_seasons(player_stats)
	print(f"Built {len(player_seasons)} player-season records")
	load_player_seasons_to_supabase(player_seasons, supabase, args.dry_run)

	# Refresh materialized view
	refresh_materialized_view(supabase, args.dry_run)

if __name__ == "__main__":
	main()

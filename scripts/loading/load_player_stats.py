#!/usr/bin/env python3
"""
Load player game statistics from scraped player stats files into Supabase.

Processes all game_*_player_stats.json files and loads individual player
statistics per game, handling both regular stats and goalie-specific stats.

Usage:
    python3 scripts/load_player_stats.py
    python3 scripts/load_player_stats.py --data-dir data/games --dry-run
"""

import json
import os
import sys
import argparse
from pathlib import Path
from supabase import create_client, Client

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

def extract_player_stats_from_files(data_dir="data/games"):
    """Extract player game stats from all player stats files."""
    data_path = Path(data_dir)
    if not data_path.exists():
        print(f"Error: Data directory {data_dir} not found", file=sys.stderr)
        sys.exit(1)
    
    player_stats = []
    stats_files = list(data_path.glob("game_*_player_stats.json"))
    
    if not stats_files:
        print(f"Error: No player stats files found in {data_dir}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Processing {len(stats_files)} player stats files...")
    
    for file_path in stats_files:
        try:
            # Extract game ID from filename
            game_id = file_path.stem.split('_')[1]  # game_6309366_player_stats -> 6309366
            
            with open(file_path, 'r', encoding='utf-8') as f:
                players_data = json.load(f)
            
            for player_data in players_data:
                if 'playerId' not in player_data or 'name' not in player_data:
                    continue
                
                player_id = player_data['playerId']
                
                # Check if this is goalie stats (has different structure)
                is_goalie_stat = 'G Min' in player_data
                
                if is_goalie_stat:
                    # Handle goalie-specific stats
                    stat = {
                        'game_id': game_id,
                        'player_id': player_id,
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

def load_player_stats_to_supabase(player_stats, supabase_client, dry_run=False):
    """Load player stats into Supabase player_game_stats table."""
    # Deduplicate by (game_id, player_id) - keep first occurrence
    seen = set()
    deduplicated_stats = []
    duplicates_found = 0

    for stat in player_stats:
        key = (stat['game_id'], stat['player_id'])
        if key not in seen:
            seen.add(key)
            deduplicated_stats.append(stat)
        else:
            duplicates_found += 1

    if duplicates_found > 0:
        print(f"Note: Removed {duplicates_found} duplicate (game_id, player_id) pairs from source data")

    player_stats = deduplicated_stats

    if dry_run:
        print(f"DRY RUN: Would load {len(player_stats)} player game stats:")
        for stat in player_stats[:10]:
            goals = stat['goals']
            assists = stat['assists']
            pos = stat['position'] or 'N/A'
            print(f"  Game {stat['game_id']}, Player {stat['player_id']}: {goals}G {assists}A ({pos})")
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

def main():
    parser = argparse.ArgumentParser(description="Load player game stats from stats files to Supabase")
    parser.add_argument("--data-dir", default="data/games", help="Directory containing game JSON files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be loaded without actually loading")
    
    args = parser.parse_args()
    
    # Extract player stats from files
    player_stats = extract_player_stats_from_files(args.data_dir)
    
    if not player_stats:
        print("No player stats found in files", file=sys.stderr)
        sys.exit(1)
    
    print(f"Extracted {len(player_stats)} player game statistics")
    
    # Show summary stats
    total_goals = sum(stat['goals'] for stat in player_stats)
    total_assists = sum(stat['assists'] for stat in player_stats)
    unique_games = len(set(stat['game_id'] for stat in player_stats))
    unique_players = len(set(stat['player_id'] for stat in player_stats))
    
    print(f"Summary: {unique_games} games, {unique_players} unique players")
    print(f"Total goals: {total_goals}, Total assists: {total_assists}")
    
    # Load to Supabase unless dry run
    if not args.dry_run:
        config = load_config()
        supabase: Client = create_client(config['supabase_url'], config['supabase_key'])
        
    load_player_stats_to_supabase(player_stats, supabase if not args.dry_run else None, args.dry_run)

if __name__ == "__main__":
    main()
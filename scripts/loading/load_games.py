#!/usr/bin/env python3
"""
Load game data from scraped game info files into Supabase.

Processes all game_*_info.json files and loads them into the games table
with proper date parsing and team ID mapping.

Usage:
    python3 scripts/load_games.py
    python3 scripts/load_games.py --data-dir data/games --dry-run
"""

import json
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
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

def parse_game_date(date_str):
    """Parse game date from MM/DD/YYYY format to YYYY-MM-DD."""
    try:
        # Parse MM/DD/YYYY format
        date_obj = datetime.strptime(date_str, "%m/%d/%Y")
        return date_obj.strftime("%Y-%m-%d")
    except Exception as e:
        print(f"Warning: Could not parse date '{date_str}': {e}", file=sys.stderr)
        return None

def extract_games_from_info_files(data_dir="data/games"):
    """Extract games from all game info files."""
    data_path = Path(data_dir)
    if not data_path.exists():
        print(f"Error: Data directory {data_dir} not found", file=sys.stderr)
        sys.exit(1)
    
    games = []
    info_files = list(data_path.glob("game_*_info.json"))
    
    if not info_files:
        print(f"Error: No game info files found in {data_dir}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Processing {len(info_files)} game info files...")
    
    for file_path in info_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                game_data = json.load(f)
            
            # Extract required fields
            game_id = game_data.get('gameId')
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
            
            # Extract team information
            home_team_id = game_data.get('homeTeamId')
            away_team_id = game_data.get('awayTeamId')
            
            if not home_team_id or not away_team_id:
                print(f"Warning: Missing team IDs in {file_path}", file=sys.stderr)
                continue
            
            game = {
                'id': game_id,
                'game_date': game_date,
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
            print(f"  {game['id']}: {game['game_date']} - {game['home_team_id']} vs {game['away_team_id']} ({home_score}-{away_score})")
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
            if dates:
                print(f"Date range: {min(dates)} to {max(dates)}")
        
    except Exception as e:
        print(f"Error loading games to Supabase: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Load game data from info files to Supabase")
    parser.add_argument("--data-dir", default="data/games", help="Directory containing game JSON files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be loaded without actually loading")
    
    args = parser.parse_args()
    
    # Extract games from info files
    games = extract_games_from_info_files(args.data_dir)
    
    if not games:
        print("No games found in info files", file=sys.stderr)
        sys.exit(1)
    
    print(f"Extracted {len(games)} games")
    
    # Show summary stats
    dates = [g['game_date'] for g in games if g['game_date']]
    if dates:
        print(f"Date range: {min(dates)} to {max(dates)}")
    
    # Load to Supabase unless dry run
    if not args.dry_run:
        config = load_config()
        supabase: Client = create_client(config['supabase_url'], config['supabase_key'])
        
    load_games_to_supabase(games, supabase if not args.dry_run else None, args.dry_run)

if __name__ == "__main__":
    main()
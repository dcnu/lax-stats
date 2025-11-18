#!/usr/bin/env python3
"""
Load play-by-play data from scraped game plays files into Supabase.

Processes all game_*_plays.json files and loads individual plays
into the game_plays table with proper sequencing.

Usage:
    python3 scripts/load_plays.py
    python3 scripts/load_plays.py --data-dir data/games --dry-run
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

def extract_plays_from_files(data_dir="data/games"):
    """Extract game plays from all plays files."""
    data_path = Path(data_dir)
    if not data_path.exists():
        print(f"Error: Data directory {data_dir} not found", file=sys.stderr)
        sys.exit(1)
    
    all_plays = []
    plays_files = list(data_path.glob("game_*_plays.json"))
    
    if not plays_files:
        print(f"Error: No plays files found in {data_dir}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Processing {len(plays_files)} plays files...")
    
    for file_path in plays_files:
        try:
            # Extract game ID from filename
            game_id = file_path.stem.split('_')[1]  # game_6309366_plays -> 6309366
            
            with open(file_path, 'r', encoding='utf-8') as f:
                plays_data = json.load(f)
            
            for sequence, play_data in enumerate(plays_data, 1):
                play = {
                    'game_id': game_id,
                    'quarter': play_data.get('quarter', ''),
                    'time_remaining': play_data.get('time', ''),
                    'home_event': play_data.get('home_event', ''),
                    'away_event': play_data.get('away_event', ''),
                    'score': play_data.get('score', ''),
                    'play_sequence': sequence
                }
                
                all_plays.append(play)
                        
        except Exception as e:
            print(f"Warning: Error processing {file_path}: {e}", file=sys.stderr)
            continue
    
    return all_plays

def load_plays_to_supabase(plays, supabase_client, dry_run=False):
    """Load plays into Supabase game_plays table."""
    if dry_run:
        print(f"DRY RUN: Would load {len(plays)} plays:")
        for play in plays[:10]:
            quarter = play['quarter']
            time = play['time_remaining']
            home_event = play['home_event'][:50] + "..." if len(play['home_event']) > 50 else play['home_event']
            away_event = play['away_event'][:50] + "..." if len(play['away_event']) > 50 else play['away_event']
            
            if home_event:
                print(f"  Game {play['game_id']}, Q{quarter} {time}: {home_event}")
            elif away_event:
                print(f"  Game {play['game_id']}, Q{quarter} {time}: {away_event}")
            
        if len(plays) > 10:
            print(f"  ... and {len(plays) - 10} more")
        return
    
    print(f"Loading {len(plays)} plays to Supabase...")
    
    # Load in batches to avoid timeout
    batch_size = 200
    loaded_count = 0
    
    try:
        for i in range(0, len(plays), batch_size):
            batch = plays[i:i + batch_size]
            result = supabase_client.table('game_plays').upsert(batch).execute()
            loaded_count += len(result.data)
            print(f"Loaded batch {i//batch_size + 1}: {len(result.data)} plays")
        
        print(f"Successfully loaded {loaded_count} plays total")
        
    except Exception as e:
        print(f"Error loading plays to Supabase: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Load play-by-play data from plays files to Supabase")
    parser.add_argument("--data-dir", default="data/games", help="Directory containing game JSON files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be loaded without actually loading")
    
    args = parser.parse_args()
    
    # Extract plays from files
    plays = extract_plays_from_files(args.data_dir)
    
    if not plays:
        print("No plays found in files", file=sys.stderr)
        sys.exit(1)
    
    print(f"Extracted {len(plays)} plays")
    
    # Show summary stats
    unique_games = len(set(play['game_id'] for play in plays))
    quarters = set(play['quarter'] for play in plays if play['quarter'])
    
    print(f"Summary: {unique_games} games")
    print(f"Quarters found: {sorted(quarters)}")
    
    # Count plays with events
    home_events = sum(1 for play in plays if play['home_event'])
    away_events = sum(1 for play in plays if play['away_event'])
    
    print(f"Home events: {home_events}, Away events: {away_events}")
    
    # Load to Supabase unless dry run
    if not args.dry_run:
        config = load_config()
        supabase: Client = create_client(config['supabase_url'], config['supabase_key'])
        
    load_plays_to_supabase(plays, supabase if not args.dry_run else None, args.dry_run)

if __name__ == "__main__":
    main()
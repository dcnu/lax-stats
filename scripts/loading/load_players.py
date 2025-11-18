#!/usr/bin/env python3
"""
Load player data from scraped player stats files into Supabase.

Extracts unique players from all game_*_player_stats.json files and loads them
into the players table with most common position as primary position.

Usage:
    python3 scripts/load_players.py
    python3 scripts/load_players.py --data-dir data/games --dry-run
"""

import json
import os
import sys
import argparse
from pathlib import Path
from collections import defaultdict, Counter
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

def extract_players_from_stats(data_dir="data/games"):
    """Extract unique players from all player stats files."""
    data_path = Path(data_dir)
    if not data_path.exists():
        print(f"Error: Data directory {data_dir} not found", file=sys.stderr)
        sys.exit(1)
    
    players_data = defaultdict(lambda: {
        'positions': Counter(),
        'jersey_numbers': Counter(),
        'name': None
    })
    
    stats_files = list(data_path.glob("game_*_player_stats.json"))
    
    if not stats_files:
        print(f"Error: No player stats files found in {data_dir}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Processing {len(stats_files)} player stats files...")
    
    for file_path in stats_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                players_stats = json.load(f)
            
            for player_stat in players_stats:
                if 'playerId' not in player_stat or 'name' not in player_stat:
                    continue
                    
                player_id = player_stat['playerId']
                player_name = player_stat['name']
                position = player_stat.get('position', '')
                jersey = player_stat.get('jersey', '')
                
                # Track player data
                players_data[player_id]['name'] = player_name
                if position:
                    players_data[player_id]['positions'][position] += 1
                if jersey:
                    players_data[player_id]['jersey_numbers'][jersey] += 1
                        
        except Exception as e:
            print(f"Warning: Error processing {file_path}: {e}", file=sys.stderr)
            continue
    
    # Convert to final player list with most common position
    players = []
    for player_id, data in players_data.items():
        # Get most common position
        primary_position = data['positions'].most_common(1)[0][0] if data['positions'] else None
        # Get most common jersey number
        jersey_number = data['jersey_numbers'].most_common(1)[0][0] if data['jersey_numbers'] else None
        
        players.append({
            'id': player_id,
            'name': data['name'],
            'jersey_number': jersey_number,
            'primary_position': primary_position
        })
    
    return players

def load_players_to_supabase(players, supabase_client, dry_run=False):
    """Load players into Supabase players table."""
    if dry_run:
        print(f"DRY RUN: Would load {len(players)} players:")
        for player in sorted(players, key=lambda x: x['name'])[:10]:
            pos = player['primary_position'] or 'N/A'
            jersey = player['jersey_number'] or 'N/A'
            print(f"  {player['id']}: {player['name']} (#{jersey}, {pos})")
        if len(players) > 10:
            print(f"  ... and {len(players) - 10} more")
        return
    
    print(f"Loading {len(players)} players to Supabase...")
    
    # Load in batches to avoid timeout
    batch_size = 100
    loaded_count = 0
    
    try:
        for i in range(0, len(players), batch_size):
            batch = players[i:i + batch_size]
            result = supabase_client.table('players').upsert(batch).execute()
            loaded_count += len(result.data)
            print(f"Loaded batch {i//batch_size + 1}: {len(result.data)} players")
        
        print(f"Successfully loaded {loaded_count} players total")
        
    except Exception as e:
        print(f"Error loading players to Supabase: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Load player data from stats files to Supabase")
    parser.add_argument("--data-dir", default="data/games", help="Directory containing game JSON files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be loaded without actually loading")
    
    args = parser.parse_args()
    
    # Extract players from stats files
    players = extract_players_from_stats(args.data_dir)
    
    if not players:
        print("No players found in stats files", file=sys.stderr)
        sys.exit(1)
    
    print(f"Extracted {len(players)} unique players")
    
    # Show position distribution
    positions = Counter(p['primary_position'] for p in players if p['primary_position'])
    print("Position distribution:")
    for pos, count in positions.most_common():
        print(f"  {pos}: {count}")
    
    # Load to Supabase unless dry run
    if not args.dry_run:
        config = load_config()
        supabase: Client = create_client(config['supabase_url'], config['supabase_key'])
        
    load_players_to_supabase(players, supabase if not args.dry_run else None, args.dry_run)

if __name__ == "__main__":
    main()
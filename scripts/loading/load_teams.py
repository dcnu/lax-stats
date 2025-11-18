#!/usr/bin/env python3
"""
Load team data from scraped game info files into Supabase.

Extracts unique teams from all game_*_info.json files and loads them
into the teams table with proper ID mapping.

Usage:
    python3 scripts/load_teams.py
    python3 scripts/load_teams.py --data-dir data/games --dry-run
"""

import json
import os
import sys
import argparse
from pathlib import Path
from collections import defaultdict
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

def extract_teams_from_games(data_dir="data/games"):
    """Extract unique teams from all game info files."""
    data_path = Path(data_dir)
    if not data_path.exists():
        print(f"Error: Data directory {data_dir} not found", file=sys.stderr)
        sys.exit(1)
    
    teams = {}
    game_files = list(data_path.glob("game_*_info.json"))
    
    if not game_files:
        print(f"Error: No game info files found in {data_dir}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Processing {len(game_files)} game files...")
    
    for file_path in game_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                game_data = json.load(f)
            
            # Extract home team
            if 'homeTeamId' in game_data and 'homeTeam' in game_data:
                team_id = game_data['homeTeamId']
                team_name = game_data['homeTeam']
                if team_id not in teams:
                    teams[team_id] = {
                        'id': team_id,
                        'name': team_name,
                        'short_name': None  # Will be derived later if needed
                    }
            
            # Extract away team
            if 'awayTeamId' in game_data and 'awayTeam' in game_data:
                team_id = game_data['awayTeamId']
                team_name = game_data['awayTeam']
                if team_id not in teams:
                    teams[team_id] = {
                        'id': team_id,
                        'name': team_name,
                        'short_name': None
                    }
                        
        except Exception as e:
            print(f"Warning: Error processing {file_path}: {e}", file=sys.stderr)
            continue
    
    return list(teams.values())

def load_teams_to_supabase(teams, supabase_client, dry_run=False):
    """Load teams into Supabase teams table."""
    if dry_run:
        print(f"DRY RUN: Would load {len(teams)} teams:")
        for team in sorted(teams, key=lambda x: x['name']):
            print(f"  {team['id']}: {team['name']}")
        return
    
    print(f"Loading {len(teams)} teams to Supabase...")
    
    # Use upsert to handle duplicates
    try:
        result = supabase_client.table('teams').upsert(teams).execute()
        print(f"Successfully loaded {len(result.data)} teams")
        
        # Show sample of loaded teams
        if result.data:
            print("Sample loaded teams:")
            for team in sorted(result.data[:5], key=lambda x: x['name']):
                print(f"  {team['id']}: {team['name']}")
                
    except Exception as e:
        print(f"Error loading teams to Supabase: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Load team data from game files to Supabase")
    parser.add_argument("--data-dir", default="data/games", help="Directory containing game JSON files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be loaded without actually loading")
    
    args = parser.parse_args()
    
    # Extract teams from game files
    teams = extract_teams_from_games(args.data_dir)
    
    if not teams:
        print("No teams found in game files", file=sys.stderr)
        sys.exit(1)
    
    print(f"Extracted {len(teams)} unique teams")
    
    # Load to Supabase unless dry run
    if not args.dry_run:
        config = load_config()
        supabase: Client = create_client(config['supabase_url'], config['supabase_key'])
        
    load_teams_to_supabase(teams, supabase if not args.dry_run else None, args.dry_run)

if __name__ == "__main__":
    main()
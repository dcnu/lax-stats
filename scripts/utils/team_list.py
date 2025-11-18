#!/usr/bin/env python3
"""
Extract unique team IDs from game data with game participation counts.

This utility script parses the game IDs data file and creates a comprehensive
list of all unique team IDs found, along with the number of games each team
participated in. Results are sorted by team ID for consistent output.

Usage (run from project root):
    python3 utils/team_list.py
    python3 utils/team_list.py --input data/raw/game_ids.json
    python3 utils/team_list.py --output data/raw/custom_team_ids.json

Input:
    - data/raw/game_ids.json: Game data with team ID information

Output:
    - data/raw/team_ids.json: Unique team IDs with game participation counts
"""

import json
import argparse
import sys
from pathlib import Path
from collections import Counter


def parse_team_ids(input_file="data/raw/game_ids.json", output_file="data/raw/team_ids.json"):
    """Parse game IDs file and extract unique team IDs with game counts."""
    
    # Handle relative paths if running from utils directory
    if Path.cwd().name == "utils":
        if not Path(input_file).is_absolute():
            input_file = f"../{input_file}"
        if not Path(output_file).is_absolute():
            output_file = f"../{output_file}"
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            games_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Input file {input_file} not found", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Count team occurrences
    team_counter = Counter()
    
    for game in games_data:
        if "teamIDs" in game:
            for team_id in game["teamIDs"]:
                team_counter[team_id] += 1
    
    # Convert to sorted list of dictionaries
    team_list = []
    for team_id in sorted(team_counter.keys()):
        team_list.append({
            "teamID": team_id,
            "gameCount": team_counter[team_id]
        })
    
    # Create output directory if it doesn't exist
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write output file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(team_list, f, indent=2)
    
    print(f"Found {len(team_list)} unique teams")
    print(f"Total games processed: {len(games_data)}")
    print(f"Saved team list to {output_file}")
    
    # Show summary statistics
    game_counts = [team["gameCount"] for team in team_list]
    print(f"Team game counts - Min: {min(game_counts)}, Max: {max(game_counts)}, Avg: {sum(game_counts)/len(game_counts):.1f}")


def main():
    parser = argparse.ArgumentParser(description="Parse game IDs and create unique team list")
    parser.add_argument("--input", default="data/raw/game_ids.json", help="Input game IDs JSON file")
    parser.add_argument("--output", default="data/raw/team_ids.json", help="Output team IDs JSON file")
    
    args = parser.parse_args()
    
    parse_team_ids(args.input, args.output)


if __name__ == "__main__":
    main()
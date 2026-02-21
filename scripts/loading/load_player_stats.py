#!/usr/bin/env python3
"""
Load player game statistics from scraped files into PostgreSQL.

Processes all game_*_player_stats.json files and loads individual player
statistics per game, with time fields converted to seconds.

Usage:
	python3 scripts/loading/load_player_stats.py
	python3 scripts/loading/load_player_stats.py --season 2025 --division 1
	python3 scripts/loading/load_player_stats.py --dry-run
"""

import csv
import io
import json
import sys
import argparse
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.db import get_connection, parse_time_to_seconds, execute_query
from utils.path_helpers import get_all_season_dirs
from utils.roster_lookup import get_roster_mapping_cached, get_player_team
from utils.pbp_parser import match_player_to_roster
# tableIndex in player_stats.json: even (0,2) = away, odd (1,3) = home


POSITION_MAP = {
	"ATT": "A", "ATTACKER": "A", "AM": "A",
	"MF": "M", "MID": "M", "MIDFIELDER": "M",
	"DM": "SSDM",
	"DEF": "D", "DEFENDER": "D",
	"GK": "G", "GOALKEEPER": "G",
	"F": "FO", "F/M": "FO",
	"LS": "LSM",
}
VALID_POSITIONS = {"A", "D", "FO", "G", "LSM", "M", "SSDM"}


def normalize_position(pos):
	"""Normalize position code to canonical value."""
	if not pos or pos in ("*", "N/A", "S", "D/M", ""):
		return None
	mapped = POSITION_MAP.get(pos, pos)
	return mapped if mapped in VALID_POSITIONS else None


def safe_int(value, default=0):
	"""Safely convert value to int."""
	if value is None or value == "":
		return default
	try:
		return int(value)
	except (ValueError, TypeError):
		return default


def safe_float(value, default=None):
	"""Safely convert value to float."""
	if value is None or value == "":
		return default
	try:
		return float(value)
	except (ValueError, TypeError):
		return default


def load_roster_for_teams(season_id: str, division: int, home_team_id: str, away_team_id: str, base_dir: str = "data") -> dict:
	"""
	Load full roster mapping for two teams.

	Returns: {playerID: {name, teamID}}
	"""
	raw_path = Path(base_dir) / season_id / f"division{division}" / "raw" / "rosters.json"
	if not raw_path.exists():
		return {}

	with open(raw_path, "r", encoding="utf-8") as f:
		rosters = json.load(f)

	result = {}
	for team in rosters:
		team_id = str(team.get("teamID", ""))
		if team_id not in (home_team_id, away_team_id):
			continue
		for player in team.get("players", []):
			player_id = player.get("playerID")
			if player_id:
				try:
					result[int(player_id)] = {
						"name": player.get("name", ""),
						"teamID": team_id,
					}
				except (ValueError, TypeError):
					continue
	return result


def extract_ncaa_player_stats(season_filter: str, division_filter: int = None, data_dir: str = "data", skip_game_ids: set = None) -> list:
	"""
	Extract player stats from ncaa.com files for final games missing box scores.

	ncaa.com format: away/home.players[] for field players, away/home.goalies[]
	for goalies. No playerID — player names matched via roster.
	"""
	if not season_filter:
		return []

	division = division_filter or 1
	data_path = Path(data_dir)
	ncaa_dir = data_path / season_filter / f"division{division}" / "ncaa"
	if not ncaa_dir.exists():
		return []

	# Discover ncaa stats files directly; filter out games already covered by games/ pass
	available_ids = {
		f.stem.split("_")[1]
		for f in ncaa_dir.glob("game_*_player_stats.json")
	}
	if skip_game_ids:
		available_ids -= skip_game_ids

	if not available_ids:
		return []

	games = execute_query(
		"SELECT id, home_team_id, away_team_id, season_id, division_id FROM games WHERE id = ANY(%s) AND status = 'final'",
		(list(available_ids),),
	)
	if not games:
		return []

	print(f"Found {len(games)} ncaa-only final games with stats files...")

	all_stats = []
	roster_cache = {}
	found = 0

	for game in games:
		game_id = str(game["id"])
		stats_file = ncaa_dir / f"game_{game_id}_player_stats.json"

		if not stats_file.exists():
			continue

		found += 1
		try:
			with open(stats_file, "r", encoding="utf-8") as f:
				data = json.load(f)

			home_team_id = game["home_team_id"]
			away_team_id = game["away_team_id"]
			div_id = game["division_id"]

			roster_key = (season_filter, division, home_team_id, away_team_id)
			if roster_key not in roster_cache:
				roster_cache[roster_key] = load_roster_for_teams(
					season_filter, division, home_team_id, away_team_id, data_dir
				)
			roster = roster_cache[roster_key]

			for side, team_id in [("away", away_team_id), ("home", home_team_id)]:
				side_data = data.get(side, {})

				# Field players
				for p in side_data.get("players", []):
					name = p.get("Name", "").title()
					if not name:
						continue
					player_id = match_player_to_roster(name, roster) if roster else None
					if player_id is None:
						print(f"Warning: no roster match for '{name}' in game {game_id}", file=sys.stderr)
						continue

					pos = normalize_position(p.get("POS", ""))
					goals = safe_int(p.get("G"))
					assists = safe_int(p.get("A"))
					all_stats.append({
						"game_id": game_id,
						"player_id": player_id,
						"season_id": season_filter,
						"division_id": div_id,
						"team_id": team_id,
						"jersey_number": p.get("NO"),
						"position": pos,
						"minutes_played": None,
						"goals": goals,
						"assists": assists,
						"points": goals + assists,
						"shots": safe_int(p.get("SH")),
						"shots_on_goal": safe_int(p.get("SOG")),
						"ground_balls": safe_int(p.get("GB")),
						"turnovers": 0,
						"caused_turnovers": 0,
						"faceoff_wins": 0,
						"faceoffs_taken": 0,
						"goalie_minutes": None,
						"goals_allowed": 0,
						"gaa": None,
						"saves": 0,
						"save_percentage": None,
					})

				# Goalies
				for g in side_data.get("goalies", []):
					name = g.get("Goalies", "").title()
					if not name:
						continue
					player_id = match_player_to_roster(name, roster) if roster else None
					if player_id is None:
						print(f"Warning: no roster match for goalie '{name}' in game {game_id}", file=sys.stderr)
						continue

					all_stats.append({
						"game_id": game_id,
						"player_id": player_id,
						"season_id": season_filter,
						"division_id": div_id,
						"team_id": team_id,
						"jersey_number": None,
						"position": normalize_position(g.get("POS", "")),
						"minutes_played": None,
						"goals": 0,
						"assists": 0,
						"points": 0,
						"shots": 0,
						"shots_on_goal": 0,
						"ground_balls": 0,
						"turnovers": 0,
						"caused_turnovers": 0,
						"faceoff_wins": 0,
						"faceoffs_taken": 0,
						# MIN is already in seconds in ncaa.com format
						"goalie_minutes": safe_int(g.get("MIN")),
						"goals_allowed": safe_int(g.get("GA")),
						"gaa": None,
						"saves": safe_int(g.get("SAVES")),
						"save_percentage": None,
					})

		except Exception as e:
			print(f"Warning: Error processing ncaa stats for game {game_id}: {e}", file=sys.stderr)
			continue

	print(f"Processed {found} ncaa player stats files, extracted {len(all_stats)} stat rows")
	return all_stats


def get_game_metadata(game_id: str):
	"""Get season_id, home_team_id, away_team_id for a game."""
	result = execute_query(
		"SELECT season_id, home_team_id, away_team_id FROM games WHERE id = %s",
		(game_id,),
	)
	if result:
		return result[0]
	return None


def get_all_game_metadata():
	"""Prefetch all game metadata in a single query."""
	result = execute_query(
		"SELECT id, season_id, home_team_id, away_team_id FROM games",
	)
	if not result:
		return {}
	return {str(row["id"]): row for row in result}


def extract_player_stats(data_dir: str = "data", season_filter: str = None, division_filter: int = None):
	"""Extract player game stats from all player stats files."""
	data_path = Path(data_dir)
	if not data_path.exists():
		print(f"Error: Data directory {data_dir} not found", file=sys.stderr)
		sys.exit(1)

	stats_files = []

	if season_filter:
		seasons = [(season_filter, data_path / season_filter)]
	else:
		seasons = get_all_season_dirs(data_dir)

	if not seasons:
		if (data_path / "games").exists():
			seasons = [("2025", data_path)]
		else:
			print(f"Error: No season directories found", file=sys.stderr)
			sys.exit(1)

	for season_id, season_path in seasons:
		division_dirs = [d for d in season_path.iterdir() if d.is_dir() and d.name.startswith("division")]

		if division_dirs:
			for div_dir in division_dirs:
				try:
					division = int(div_dir.name.replace("division", ""))
					if division_filter and division != division_filter:
						continue
					games_dir = div_dir / "games"
					if games_dir.exists():
						for f in games_dir.glob("game_*_player_stats.json"):
							stats_files.append((season_id, division, f))
				except ValueError:
					continue
		else:
			games_dir = season_path / "games"
			if games_dir.exists():
				for f in games_dir.glob("game_*_player_stats.json"):
					stats_files.append((season_id, division_filter or 1, f))

	if not stats_files:
		print(f"Error: No player stats files found", file=sys.stderr)
		sys.exit(1)

	print(f"Processing {len(stats_files)} player stats files...")

	player_stats = []
	game_cache = get_all_game_metadata()
	print(f"Prefetched metadata for {len(game_cache)} games")

	for season_id, division, file_path in stats_files:
		try:
			# Extract game ID from filename
			game_id = file_path.stem.split("_")[1]

			game_meta = game_cache.get(game_id)
			if not game_meta:
				print(f"Warning: No game metadata for {game_id}, skipping", file=sys.stderr)
				continue

			home_team_id = game_meta["home_team_id"]
			away_team_id = game_meta["away_team_id"]

			with open(file_path, "r", encoding="utf-8") as f:
				players_data = json.load(f)

			# Load roster mapping for team assignment (fallback)
			roster_map = get_roster_mapping_cached(season_id, division)

			for player_data in players_data:
				if "playerId" not in player_data or "name" not in player_data:
					continue

				player_id = player_data["playerId"]

				# Use tableIndex if available (even=away, odd=home)
				table_idx = player_data.get("tableIndex")
				if table_idx is not None:
					team_id = away_team_id if table_idx % 2 == 0 else home_team_id
				else:
					# Fallback to roster lookup for older data
					team_id = get_player_team(player_id, roster_map, home_team_id, away_team_id)
					if team_id is None:
						player_name = player_data.get("name", "Unknown")
						print(f"Warning: Player {player_id} ({player_name}) not found in roster for game {game_id}, skipping", file=sys.stderr)
						continue

				# Check if goalie stats
				is_goalie_stat = "G Min" in player_data

				if is_goalie_stat:
					stat = {
						"game_id": game_id,
						"player_id": player_id,
						"season_id": season_id,
						"division_id": division,
						"team_id": team_id,
						"jersey_number": player_data.get("jersey"),
						"position": normalize_position(player_data.get("position")),
						"minutes_played": None,
						"goals": 0,
						"assists": 0,
						"points": 0,
						"shots": 0,
						"shots_on_goal": 0,
						"ground_balls": 0,
						"turnovers": 0,
						"caused_turnovers": 0,
						"faceoff_wins": 0,
						"faceoffs_taken": 0,
						# Convert goalie minutes to seconds
						"goalie_minutes": parse_time_to_seconds(player_data.get("G Min")),
						"goals_allowed": safe_int(player_data.get("Goals Allowed")),
						"gaa": safe_float(player_data.get("GAA")),
						"saves": safe_int(player_data.get("Saves")),
						"save_percentage": safe_float(player_data.get("Save Pct")),
					}
				else:
					stat = {
						"game_id": game_id,
						"player_id": player_id,
						"season_id": season_id,
						"division_id": division,
						"team_id": team_id,
						"jersey_number": player_data.get("jersey"),
						"position": normalize_position(player_data.get("position")),
						# Convert minutes to seconds
						"minutes_played": parse_time_to_seconds(player_data.get("Min")),
						"goals": safe_int(player_data.get("Goals")),
						"assists": safe_int(player_data.get("Assists")),
						"points": safe_int(player_data.get("Points")),
						"shots": safe_int(player_data.get("Shots")),
						"shots_on_goal": safe_int(player_data.get("SOG")),
						"ground_balls": safe_int(player_data.get("GB")),
						"turnovers": safe_int(player_data.get("TO")),
						"caused_turnovers": safe_int(player_data.get("CT")),
						"faceoff_wins": safe_int(player_data.get("FO_Won")),
						"faceoffs_taken": safe_int(player_data.get("FOs_Taken")),
						"goalie_minutes": None,
						"goals_allowed": 0,
						"gaa": None,
						"saves": 0,
						"save_percentage": None,
					}

				player_stats.append(stat)

		except Exception as e:
			print(f"Warning: Error processing {file_path}: {e}", file=sys.stderr)
			continue

	return player_stats


def deduplicate_stats(player_stats):
	"""Deduplicate by (game_id, player_id, position)."""
	seen = set()
	deduplicated = []
	duplicates = 0

	for stat in player_stats:
		key = (stat["game_id"], stat["player_id"], stat["position"])
		if key not in seen:
			seen.add(key)
			deduplicated.append(stat)
		else:
			duplicates += 1

	if duplicates > 0:
		print(f"Note: Removed {duplicates} duplicate stats")

	return deduplicated


def build_player_seasons(player_stats):
	"""Build player_seasons records from stats."""
	player_season_attrs = defaultdict(lambda: {"jerseys": [], "positions": []})

	for stat in player_stats:
		key = (stat["player_id"], stat["team_id"], stat["season_id"])
		if stat.get("jersey_number"):
			player_season_attrs[key]["jerseys"].append(stat["jersey_number"])
		if stat.get("position"):
			player_season_attrs[key]["positions"].append(stat["position"])

	player_seasons = []
	for (player_id, team_id, season_id), attrs in player_season_attrs.items():
		jersey = max(set(attrs["jerseys"]), key=attrs["jerseys"].count) if attrs["jerseys"] else "0"
		position = max(set(attrs["positions"]), key=attrs["positions"].count) if attrs["positions"] else None

		player_seasons.append({
			"player_id": player_id,
			"team_id": team_id,
			"season_id": season_id,
			"jersey_number": jersey,
			"primary_position": position,
		})

	return player_seasons


def load_player_stats_to_database(player_stats: list, season_id: str = None, dry_run: bool = False):
	"""Load player stats into PostgreSQL via COPY protocol."""
	player_stats = deduplicate_stats(player_stats)

	if dry_run:
		print(f"DRY RUN: Would load {len(player_stats)} player game stats:")
		for stat in player_stats[:10]:
			print(f"  Game {stat['game_id']}, Player {stat['player_id']}: {stat['goals']}G {stat['assists']}A")
		if len(player_stats) > 10:
			print(f"  ... and {len(player_stats) - 10} more")
		return

	print(f"Loading {len(player_stats)} player game stats to database...", flush=True)

	cols = [
		"game_id", "player_id", "team_id", "season_id", "division_id",
		"jersey_number", "position", "minutes_played",
		"goals", "assists", "points", "shots", "shots_on_goal",
		"ground_balls", "turnovers", "caused_turnovers",
		"faceoff_wins", "faceoffs_taken",
		"goalie_minutes", "goals_allowed", "gaa", "saves", "save_percentage",
	]

	buf = io.StringIO()
	writer = csv.writer(buf)
	for stat in player_stats:
		writer.writerow(["" if stat[c] is None else stat[c] for c in cols])
	buf.seek(0)

	copy_sql = f"COPY player_game_stats ({', '.join(cols)}) FROM STDIN WITH (FORMAT csv, NULL '')"

	conn = get_connection()
	try:
		with conn.cursor() as cur:
			if season_id:
				cur.execute("DELETE FROM player_game_stats WHERE season_id = %s", (season_id,))
			else:
				cur.execute("DELETE FROM player_game_stats")
			cur.copy_expert(copy_sql, buf)
		conn.commit()
	except Exception:
		conn.rollback()
		raise
	finally:
		conn.close()

	print(f"Successfully loaded {len(player_stats)} player game stats")


def load_player_seasons_to_database(player_seasons: list, season_id: str = None, dry_run: bool = False):
	"""Load player_seasons records via COPY protocol."""
	# Dedup by (player_id, season_id, division_id) — unique constraint; keep first (stats.ncaa.org priority)
	seen = set()
	deduped = []
	for ps in player_seasons:
		key = (ps["player_id"], ps["season_id"], ps.get("division_id", 1))
		if key not in seen:
			seen.add(key)
			deduped.append(ps)
	if len(deduped) < len(player_seasons):
		print(f"Note: Removed {len(player_seasons) - len(deduped)} duplicate player-season records")
	player_seasons = deduped

	if dry_run:
		print(f"DRY RUN: Would load {len(player_seasons)} player-season records")
		return

	print(f"Loading {len(player_seasons)} player-season records...", flush=True)

	cols = ["player_id", "team_id", "season_id", "jersey_number", "primary_position"]

	buf = io.StringIO()
	writer = csv.writer(buf)
	for ps in player_seasons:
		writer.writerow(["" if ps[c] is None else ps[c] for c in cols])
	buf.seek(0)

	copy_sql = f"COPY player_seasons ({', '.join(cols)}) FROM STDIN WITH (FORMAT csv, NULL '')"

	conn = get_connection()
	try:
		with conn.cursor() as cur:
			if season_id:
				cur.execute("DELETE FROM player_seasons WHERE season_id = %s", (season_id,))
			else:
				cur.execute("DELETE FROM player_seasons")
			cur.copy_expert(copy_sql, buf)
		conn.commit()
	except Exception:
		conn.rollback()
		raise
	finally:
		conn.close()

	print(f"Successfully loaded {len(player_seasons)} player-season records")


def main():
	parser = argparse.ArgumentParser(description="Load player game stats to PostgreSQL")
	parser.add_argument("--data-dir", default="data", help="Base data directory")
	parser.add_argument("--season", help="Only load from specific season")
	parser.add_argument("--division", type=int, choices=[1, 2, 3], help="Only load from specific division")
	parser.add_argument("--dry-run", action="store_true", help="Show what would be loaded")

	args = parser.parse_args()

	player_stats = extract_player_stats(args.data_dir, season_filter=args.season, division_filter=args.division)

	if args.season:
		covered = {s["game_id"] for s in player_stats}
		ncaa_stats = extract_ncaa_player_stats(args.season, args.division, args.data_dir, skip_game_ids=covered)
		player_stats.extend(ncaa_stats)

	if not player_stats:
		print("No player stats found", file=sys.stderr)
		sys.exit(1)

	print(f"Extracted {len(player_stats)} player game statistics")

	# Summary
	total_goals = sum(s["goals"] for s in player_stats)
	total_assists = sum(s["assists"] for s in player_stats)
	unique_games = len(set(s["game_id"] for s in player_stats))
	unique_players = len(set(s["player_id"] for s in player_stats))

	print(f"Summary: {unique_games} games, {unique_players} players")
	print(f"Total goals: {total_goals}, Total assists: {total_assists}")

	load_player_stats_to_database(player_stats, season_id=args.season, dry_run=args.dry_run)

	# Build and load player_seasons
	player_seasons = build_player_seasons(player_stats)
	print(f"Built {len(player_seasons)} player-season records")
	load_player_seasons_to_database(player_seasons, season_id=args.season, dry_run=args.dry_run)


if __name__ == "__main__":
	main()

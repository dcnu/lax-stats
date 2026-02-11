#!/usr/bin/env python3
"""
Load play-by-play data from scraped files into PostgreSQL.

Processes all game_*_plays.json files and loads individual play events
per game, with time fields converted to seconds and play types classified.

Usage:
	python3 scripts/loading/load_game_plays.py
	python3 scripts/loading/load_game_plays.py --season 2025 --division 1
	python3 scripts/loading/load_game_plays.py --dry-run
"""

import csv
import io
import json
import re
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.db import get_connection, parse_time_to_seconds, execute_query
from utils.path_helpers import get_all_season_dirs
from utils.pbp_parser import (
	parse_event,
	detect_column_swap,
	match_player_to_roster,
	normalize_name,
)


# Map event text keywords to play_types.code values
PLAY_TYPE_KEYWORDS = [
	(re.compile(r"GOAL by", re.IGNORECASE), "goal"),
	(re.compile(r"Assist by", re.IGNORECASE), "assist"),
	(re.compile(r"Shot by.*SAVE", re.IGNORECASE), "shot_on_goal"),
	(re.compile(r"Shot by", re.IGNORECASE), "shot"),
	(re.compile(r"\bSAVE\b"), "save"),
	(re.compile(r"Ground ball pickup", re.IGNORECASE), "ground_ball"),
	(re.compile(r"Turnover by.*caused by", re.IGNORECASE), "caused_turnover"),
	(re.compile(r"Turnover by", re.IGNORECASE), "turnover"),
	(re.compile(r"Faceoff.*won by", re.IGNORECASE), "faceoff_won"),
	(re.compile(r"Penalty on", re.IGNORECASE), "penalty"),
	(re.compile(r"Timeout by|Media timeout", re.IGNORECASE), "timeout"),
	(re.compile(r"at goalie for|substitution", re.IGNORECASE), "substitution"),
	(re.compile(r"Clear attempt.*good", re.IGNORECASE), "clear_success"),
	(re.compile(r"Clear attempt.*failed", re.IGNORECASE), "clear_attempt"),
	(re.compile(r"Clear attempt", re.IGNORECASE), "clear_attempt"),
	(re.compile(r"Extra-man opportunity", re.IGNORECASE), "emo_opportunity"),
	(re.compile(r"Draw control", re.IGNORECASE), "draw_control"),
]

# Valid play_types codes from the DB
VALID_PLAY_TYPES = {
	"goal", "assist", "shot", "shot_on_goal", "save", "ground_ball",
	"turnover", "caused_turnover", "faceoff_won", "faceoff_lost",
	"penalty", "man_up_goal", "man_down_goal", "emo_opportunity",
	"clear_attempt", "clear_success", "ride_attempt", "ride_success",
	"draw_control", "free_position_goal",
}

# Additional non-DB types we generate (will be stored but may not have FK)
EXTRA_TYPES = {"timeout", "substitution"}


def classify_play_type(event_text: str) -> str | None:
	"""Classify event text into a play_type code."""
	if not event_text:
		return None

	# Check for man-up/man-down goals
	if "GOAL by" in event_text:
		if "man-up" in event_text.lower() or "extra-man" in event_text.lower():
			return "man_up_goal"
		if "man-down" in event_text.lower():
			return "man_down_goal"

	for pattern, play_type in PLAY_TYPE_KEYWORDS:
		if pattern.search(event_text):
			return play_type

	# Shot clock violation, etc. — skip unclassified events
	return None


def parse_score(score_str: str) -> tuple[int | None, int | None]:
	"""Parse 'X-Y' score string into (home_score, away_score)."""
	if not score_str or "-" not in score_str:
		return None, None
	try:
		parts = score_str.split("-", 1)
		return int(parts[0]), int(parts[1])
	except (ValueError, IndexError):
		return None, None


def extract_player_name(event_text: str) -> str | None:
	"""Extract primary player name from event text."""
	if not event_text:
		return None

	# Use parse_event to get structured stats — first player found is primary
	stats = parse_event(event_text, "")
	if stats:
		# Return first player name found
		for name in stats:
			return name

	# Fallback: try goalie substitution pattern "Name, First at goalie for TEAM."
	goalie_match = re.match(r"^([^,]+, [A-Z][a-z]+) at goalie", event_text)
	if goalie_match:
		return normalize_name(goalie_match.group(1))

	return None


def extract_secondary_player(event_text: str) -> str | None:
	"""Extract secondary player (assist, caused turnover) from event text."""
	if not event_text:
		return None

	# Assist
	assist_match = re.search(r"Assist by ([^(,\.]+(?:, [^(,\.]+)?)", event_text)
	if assist_match:
		return normalize_name(assist_match.group(1))

	# Caused turnover
	ct_match = re.search(r"caused by ([^)]+)", event_text)
	if ct_match:
		return normalize_name(ct_match.group(1))

	return None


def get_all_game_metadata():
	"""Prefetch all game metadata in a single query."""
	result = execute_query(
		"SELECT id, season_id, home_team_id, away_team_id, home_score, away_score FROM games",
	)
	if not result:
		return {}
	return {str(row["id"]): row for row in result}


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


def extract_game_plays(data_dir: str = "data", season_filter: str = None, division_filter: int = None):
	"""Extract play-by-play data from all plays files."""
	data_path = Path(data_dir)
	if not data_path.exists():
		print(f"Error: Data directory {data_dir} not found", file=sys.stderr)
		sys.exit(1)

	plays_files = []

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
						for f in games_dir.glob("game_*_plays.json"):
							plays_files.append((season_id, division, f))
				except ValueError:
					continue
		else:
			games_dir = season_path / "games"
			if games_dir.exists():
				for f in games_dir.glob("game_*_plays.json"):
					plays_files.append((season_id, division_filter or 1, f))

	if not plays_files:
		print(f"Error: No plays files found", file=sys.stderr)
		sys.exit(1)

	print(f"Processing {len(plays_files)} plays files...")

	all_plays = []
	game_cache = get_all_game_metadata()
	print(f"Prefetched metadata for {len(game_cache)} games")

	skipped_games = 0
	total_events = 0

	for season_id, division, file_path in plays_files:
		try:
			game_id = file_path.stem.split("_")[1]

			game_meta = game_cache.get(game_id)
			if not game_meta:
				print(f"Warning: No game metadata for {game_id}, skipping", file=sys.stderr)
				skipped_games += 1
				continue

			home_team_id = game_meta["home_team_id"]
			away_team_id = game_meta["away_team_id"]
			expected_home_goals = game_meta.get("home_score")
			expected_away_goals = game_meta.get("away_score")

			with open(file_path, "r", encoding="utf-8") as f:
				plays_data = json.load(f)

			if not plays_data:
				continue

			# Detect column swap
			swap_columns = False
			if expected_home_goals is not None and expected_away_goals is not None:
				swap_columns = detect_column_swap(plays_data, expected_home_goals, expected_away_goals)

			# If swapped, swap team assignments for home/away columns
			if swap_columns:
				col_home_team = away_team_id
				col_away_team = home_team_id
			else:
				col_home_team = home_team_id
				col_away_team = away_team_id

			# Load roster for player matching
			roster = load_roster_for_teams(season_id, division, home_team_id, away_team_id)

			play_sequence = 0

			for play in plays_data:
				quarter = play.get("quarter", "")
				time_str = play.get("time", "")
				time_remaining = parse_time_to_seconds(time_str)
				score_str = play.get("score", "")
				home_score, away_score = parse_score(score_str)
				home_event = play.get("home_event", "")
				away_event = play.get("away_event", "")

				# Process home_event
				if home_event and home_event.strip():
					play_type = classify_play_type(home_event)
					if play_type:
						play_sequence += 1
						total_events += 1

						player_name = extract_player_name(home_event)
						player_id = None
						if player_name and roster:
							player_id = match_player_to_roster(player_name, roster)

						secondary_name = extract_secondary_player(home_event)
						secondary_id = None
						if secondary_name and roster:
							secondary_id = match_player_to_roster(secondary_name, roster)

						# Use only valid DB play types
						db_play_type = play_type if play_type in VALID_PLAY_TYPES else None
						if db_play_type is None and play_type in EXTRA_TYPES:
							# Skip non-DB types (timeout, substitution)
							play_sequence -= 1
							total_events -= 1
						else:
							if db_play_type is None:
								db_play_type = "shot"  # fallback

							all_plays.append({
								"game_id": game_id,
								"season_id": season_id,
								"quarter": quarter,
								"time_remaining": time_remaining,
								"play_sequence": play_sequence,
								"play_type": db_play_type,
								"player_id": player_id,
								"player_name": player_name,
								"team_id": col_home_team,
								"secondary_player_id": secondary_id,
								"secondary_player_name": secondary_name,
								"home_score": home_score,
								"away_score": away_score,
								"raw_description": home_event,
							})

				# Process away_event
				if away_event and away_event.strip():
					play_type = classify_play_type(away_event)
					if play_type:
						play_sequence += 1
						total_events += 1

						player_name = extract_player_name(away_event)
						player_id = None
						if player_name and roster:
							player_id = match_player_to_roster(player_name, roster)

						secondary_name = extract_secondary_player(away_event)
						secondary_id = None
						if secondary_name and roster:
							secondary_id = match_player_to_roster(secondary_name, roster)

						db_play_type = play_type if play_type in VALID_PLAY_TYPES else None
						if db_play_type is None and play_type in EXTRA_TYPES:
							play_sequence -= 1
							total_events -= 1
						else:
							if db_play_type is None:
								db_play_type = "shot"

							all_plays.append({
								"game_id": game_id,
								"season_id": season_id,
								"quarter": quarter,
								"time_remaining": time_remaining,
								"play_sequence": play_sequence,
								"play_type": db_play_type,
								"player_id": player_id,
								"player_name": player_name,
								"team_id": col_away_team,
								"secondary_player_id": secondary_id,
								"secondary_player_name": secondary_name,
								"home_score": home_score,
								"away_score": away_score,
								"raw_description": away_event,
							})

		except Exception as e:
			print(f"Warning: Error processing {file_path}: {e}", file=sys.stderr)
			continue

	if skipped_games > 0:
		print(f"Skipped {skipped_games} games (no metadata)")

	return all_plays


def deduplicate_plays(plays: list) -> list:
	"""Deduplicate by (game_id, play_sequence)."""
	seen = set()
	deduplicated = []
	duplicates = 0

	for play in plays:
		key = (play["game_id"], play["play_sequence"])
		if key not in seen:
			seen.add(key)
			deduplicated.append(play)
		else:
			duplicates += 1

	if duplicates > 0:
		print(f"Note: Removed {duplicates} duplicate plays")

	return deduplicated


def load_plays_to_database(plays: list, season_id: str = None, dry_run: bool = False):
	"""Load game plays into PostgreSQL via COPY protocol."""
	plays = deduplicate_plays(plays)

	if dry_run:
		print(f"DRY RUN: Would load {len(plays)} game plays:")
		for play in plays[:10]:
			print(f"  Game {play['game_id']}, Q{play['quarter']} {play['play_type']}: {play['raw_description'][:60]}")
		if len(plays) > 10:
			print(f"  ... and {len(plays) - 10} more")
		return

	print(f"Loading {len(plays)} game plays to database...", flush=True)

	cols = [
		"game_id", "season_id", "quarter", "time_remaining", "play_sequence",
		"play_type", "player_id", "player_name", "team_id",
		"secondary_player_id", "secondary_player_name",
		"home_score", "away_score", "raw_description",
	]

	buf = io.StringIO()
	writer = csv.writer(buf)
	for play in plays:
		writer.writerow(["" if play[c] is None else play[c] for c in cols])
	buf.seek(0)

	copy_sql = f"COPY game_plays ({', '.join(cols)}) FROM STDIN WITH (FORMAT csv, NULL '')"

	conn = get_connection()
	try:
		with conn.cursor() as cur:
			if season_id:
				cur.execute("DELETE FROM game_plays WHERE season_id = %s", (season_id,))
			else:
				cur.execute("DELETE FROM game_plays")
			cur.copy_expert(copy_sql, buf)
		conn.commit()
	except Exception:
		conn.rollback()
		raise
	finally:
		conn.close()

	print(f"Successfully loaded {len(plays)} game plays")


def main():
	parser = argparse.ArgumentParser(description="Load game play-by-play data to PostgreSQL")
	parser.add_argument("--data-dir", default="data", help="Base data directory")
	parser.add_argument("--season", help="Only load from specific season")
	parser.add_argument("--division", type=int, choices=[1, 2, 3], help="Only load from specific division")
	parser.add_argument("--dry-run", action="store_true", help="Show what would be loaded")

	args = parser.parse_args()

	plays = extract_game_plays(args.data_dir, season_filter=args.season, division_filter=args.division)

	if not plays:
		print("No game plays found", file=sys.stderr)
		sys.exit(1)

	print(f"Extracted {len(plays)} game play events")

	# Summary
	unique_games = len(set(p["game_id"] for p in plays))
	play_type_counts = {}
	for p in plays:
		pt = p["play_type"]
		play_type_counts[pt] = play_type_counts.get(pt, 0) + 1

	print(f"Summary: {unique_games} games")
	for pt, count in sorted(play_type_counts.items(), key=lambda x: -x[1]):
		print(f"  {pt}: {count}")

	load_plays_to_database(plays, season_id=args.season, dry_run=args.dry_run)


if __name__ == "__main__":
	main()

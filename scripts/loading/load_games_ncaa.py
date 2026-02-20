#!/usr/bin/env python3
"""
Load ncaa.com game data into PostgreSQL.

Reads game_id_map.json (built by map_game_ids.py) and loads all games —
matched, fuzzy, and unmatched — using lookup_teams for team ID resolution.
Also processes game_ids_ncaa.json directly for any scheduled games not
covered by the map.

Usage:
	python3 scripts/loading/load_games_ncaa.py --season 2026
	python3 scripts/loading/load_games_ncaa.py --season 2026 --dry-run
	python3 scripts/loading/load_games_ncaa.py --season 2026 --confidence exact
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.db import get_cursor, upsert_season
from utils.path_helpers import get_season_ncaa_dir


def safe_int(value, default=None):
	"""Safely convert value to int."""
	if value is None or value == "":
		return default
	try:
		return int(value)
	except (ValueError, TypeError):
		return default


def parse_game_date(date_str: str):
	"""Parse game date from MM/DD/YYYY, YYYY-MM-DD, or 'Month Dth YYYY' formats."""
	if not date_str:
		return None
	for fmt in ["%m/%d/%Y", "%Y-%m-%d"]:
		try:
			return datetime.strptime(date_str, fmt).date()
		except ValueError:
			pass
	m = re.match(r"(\w+)\s+(\d+)(?:st|nd|rd|th)\s+(\d{4})", date_str)
	if m:
		try:
			return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%B %d %Y").date()
		except ValueError:
			pass
	return None


def ensure_season_exists(season_id: str, division_id: int) -> None:
	"""Ensure the season record exists in the database."""
	start_year = int(season_id)
	upsert_season(
		season_id=season_id,
		division_id=division_id,
		start_year=start_year,
		end_year=start_year,
		start_date=datetime(start_year, 2, 1).date(),
		end_date=datetime(start_year, 5, 31).date(),
		is_current=(start_year == datetime.now().year),
	)


def normalize(name: str) -> str:
	"""Normalize a team name for comparison."""
	name = name.lower().strip()
	name = re.sub(r"[^a-z0-9 ]", "", name)
	name = re.sub(r"\s+", " ", name)
	return name


def token_overlap(a: str, b: str) -> float:
	"""Jaccard coefficient between word sets of two strings."""
	ta = set(normalize(a).split())
	tb = set(normalize(b).split())
	if not ta or not tb:
		return 0.0
	return len(ta & tb) / len(ta | tb)


def load_lookup_teams() -> tuple[dict, dict]:
	"""
	Query lookup_teams and build name lookup dicts.

	Returns (by_short, by_name):
	  by_short: {short_name.lower(): team_id}
	  by_name:  {name.lower(): team_id}
	"""
	by_short: dict[str, str] = {}
	by_name: dict[str, str] = {}
	with get_cursor() as cur:
		cur.execute("SELECT id, name, short_name FROM public.lookup_teams")
		for row in cur.fetchall():
			tid = row["id"]
			full = (row["name"] or "").strip()
			short = (row["short_name"] or "").strip()
			if short:
				by_short[normalize(short)] = tid
			if full:
				by_name[normalize(full)] = tid
	return by_short, by_name


def find_team_id(name: str, by_short: dict, by_name: dict) -> str | None:
	"""
	Resolve a team name to its lookup_teams ID.

	Priority: short_name exact → short_name fuzzy (token overlap ≥ 0.5)
	          → full name exact → full name fuzzy.
	"""
	if not name:
		return None
	norm = normalize(name)

	if norm in by_short:
		return by_short[norm]

	best_id: str | None = None
	best_score = 0.0
	for key, tid in by_short.items():
		# token_overlap uses normalize internally; compare normalized tokens
		ta = set(norm.split())
		tb = set(key.split())
		if ta and tb:
			score = len(ta & tb) / len(ta | tb)
			if score > best_score and score >= 0.5:
				best_score = score
				best_id = tid
	if best_id:
		return best_id

	if norm in by_name:
		return by_name[norm]

	for key, tid in by_name.items():
		ta = set(norm.split())
		tb = set(key.split())
		if ta and tb:
			score = len(ta & tb) / len(ta | tb)
			if score > best_score and score >= 0.5:
				best_score = score
				best_id = tid
	return best_id


def _game_from_entry(
	game_id: str,
	ncaa_game_id: str,
	home_name: str,
	away_name: str,
	date_str: str,
	home_score,
	away_score,
	location: str | None,
	attendance,
	season: str,
	division: int,
	by_short: dict,
	by_name: dict,
) -> dict | None:
	"""Build a game dict, returning None if team IDs cannot be resolved."""
	home_team_id = find_team_id(home_name, by_short, by_name)
	away_team_id = find_team_id(away_name, by_short, by_name)
	if not home_team_id or not away_team_id:
		return None
	status = "final" if home_score is not None and away_score is not None else "scheduled"
	return {
		"id": game_id,
		"ncaa_game_id": ncaa_game_id,
		"season_id": season,
		"division_id": division,
		"game_date": parse_game_date(date_str),
		"home_team_id": home_team_id,
		"away_team_id": away_team_id,
		"home_score": safe_int(home_score),
		"away_score": safe_int(away_score),
		"location": location or None,
		"attendance": safe_int(attendance),
		"status": status,
	}


def extract_games(
	season: str,
	division: int,
	confidence_filter: str | None,
	by_short: dict,
	by_name: dict,
) -> list[dict]:
	"""
	Extract loadable games from game_id_map.json (and game_ids_ncaa.json as fallback).

	For matched/fuzzy: game.id = statsGameId, ncaa_game_id = ncaaGameId.
	For unmatched: game.id = ncaaGameId, ncaa_game_id = ncaaGameId.
	Games without an info file are loaded as 'scheduled' using entry metadata.
	"""
	ncaa_dir = get_season_ncaa_dir(season, division)

	map_file = ncaa_dir / "game_id_map.json"
	if not map_file.exists():
		print(f"Error: {map_file} not found. Run map_game_ids.py first.", file=sys.stderr)
		sys.exit(1)
	with open(map_file, "r") as f:
		game_map = json.load(f)

	# Secondary source: game_ids_ncaa.json for games not in the map
	ids_file = ncaa_dir / "game_ids_ncaa.json"
	ncaa_by_id: dict[str, dict] = {}
	if ids_file.exists():
		with open(ids_file, "r") as f:
			for g in json.load(f):
				gid = str(g.get("ncaaGameId", g.get("gameID", "")))
				if gid:
					ncaa_by_id[gid] = g

	games: list[dict] = []
	seen_ncaa_ids: set[str] = set()
	no_teams = 0
	no_info = 0

	for entry in game_map:
		confidence = entry.get("matchConfidence", "")
		# --confidence filters exact vs fuzzy; unmatched games are always included
		if confidence_filter and confidence not in ("unmatched", confidence_filter):
			continue

		ncaa_game_id = str(entry.get("ncaaGameId", ""))
		stats_game_id = str(entry.get("statsGameId") or "")
		if not ncaa_game_id:
			continue
		seen_ncaa_ids.add(ncaa_game_id)

		# Matched games keep their stats.ncaa.org ID; unmatched use ncaa.com ID
		game_id = stats_game_id if stats_game_id else ncaa_game_id

		home_name = entry.get("homeTeam", "")
		away_name = entry.get("awayTeam", "")
		date_str = entry.get("date", "")
		location = None
		attendance = None
		home_score = None
		away_score = None

		info_file = ncaa_dir / f"game_{ncaa_game_id}_info.json"
		if info_file.exists():
			with open(info_file, "r") as f:
				ncaa_info = json.load(f)
			home_name = ncaa_info.get("homeTeam") or home_name
			away_name = ncaa_info.get("awayTeam") or away_name
			date_str = ncaa_info.get("gameDate") or date_str
			location = ncaa_info.get("location") or None
			attendance = ncaa_info.get("attendance")
			home_score = ncaa_info.get("homeScore")
			away_score = ncaa_info.get("awayScore")
		else:
			no_info += 1
			# Fall back to scores from game_ids_ncaa.json
			ncaa_entry = ncaa_by_id.get(ncaa_game_id, {})
			home_score = ncaa_entry.get("homeScore")
			away_score = ncaa_entry.get("awayScore")

		game = _game_from_entry(
			game_id, ncaa_game_id, home_name, away_name, date_str,
			home_score, away_score, location, attendance, season, division,
			by_short, by_name,
		)
		if game is None:
			no_teams += 1
		else:
			games.append(game)

	# Supplemental: scheduled games in game_ids_ncaa.json not in the map
	for ncaa_game_id, g in ncaa_by_id.items():
		if ncaa_game_id in seen_ncaa_ids:
			continue
		home_name = g.get("homeTeam", "")
		away_name = g.get("awayTeam", "")
		if not home_name or not away_name:
			continue
		game = _game_from_entry(
			ncaa_game_id, ncaa_game_id, home_name, away_name,
			g.get("date", ""), g.get("homeScore"), g.get("awayScore"),
			None, None, season, division, by_short, by_name,
		)
		if game is None:
			no_teams += 1
		else:
			games.append(game)

	if no_info:
		print(f"  {no_info} games without info file (scheduled or pending fetch)")
	if no_teams:
		print(f"  {no_teams} games skipped (team name not found in lookup_teams)")

	return games


def load_to_database(games: list[dict], dry_run: bool = False) -> None:
	"""Insert or update games in the PostgreSQL games table."""
	if dry_run:
		final = sum(1 for g in games if g["status"] == "final")
		scheduled = sum(1 for g in games if g["status"] == "scheduled")
		print(f"DRY RUN: Would load {len(games)} games ({final} final, {scheduled} scheduled):")
		for game in games[:10]:
			score = (
				f"{game['home_score']}-{game['away_score']}"
				if game["status"] == "final"
				else game["status"]
			)
			ncaa_tag = (
				f" [ncaa:{game['ncaa_game_id']}]"
				if game["ncaa_game_id"] != game["id"]
				else ""
			)
			print(f"  {game['id']}{ncaa_tag}: {game['home_team_id']} vs {game['away_team_id']} ({score})")
		if len(games) > 10:
			print(f"  ... and {len(games) - 10} more")
		return

	seasons_seen: set[tuple] = set()
	for game in games:
		key = (game["season_id"], game["division_id"])
		if key not in seasons_seen:
			ensure_season_exists(game["season_id"], game["division_id"])
			seasons_seen.add(key)

	query = """
		INSERT INTO games (
			id, season_id, division_id, game_date, home_team_id, away_team_id,
			home_score, away_score, location, attendance, status, ncaa_game_id, updated_at
		)
		VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
		ON CONFLICT (id) DO UPDATE SET
			home_score = COALESCE(EXCLUDED.home_score, games.home_score),
			away_score = COALESCE(EXCLUDED.away_score, games.away_score),
			location = COALESCE(EXCLUDED.location, games.location),
			attendance = COALESCE(EXCLUDED.attendance, games.attendance),
			ncaa_game_id = COALESCE(EXCLUDED.ncaa_game_id, games.ncaa_game_id),
			status = CASE
				WHEN EXCLUDED.status = 'final' THEN 'final'
				WHEN games.status = 'final' THEN 'final'
				ELSE EXCLUDED.status
			END,
			updated_at = NOW()
	"""

	loaded = 0
	with get_cursor() as cursor:
		for game in games:
			cursor.execute(query, (
				game["id"],
				game["season_id"],
				game["division_id"],
				game["game_date"],
				game["home_team_id"],
				game["away_team_id"],
				game["home_score"],
				game["away_score"],
				game["location"],
				game["attendance"],
				game["status"],
				game["ncaa_game_id"],
			))
			loaded += 1

	print(f"Loaded {loaded} games")


def main():
	parser = argparse.ArgumentParser(description="Load ncaa.com game data into PostgreSQL")
	parser.add_argument("--season", default="2026")
	parser.add_argument("--division", type=int, default=1, choices=[1, 2, 3])
	parser.add_argument("--dry-run", action="store_true")
	parser.add_argument(
		"--confidence", choices=["exact", "fuzzy"],
		help="Only load matched games with this confidence (default: all, including unmatched)",
	)
	args = parser.parse_args()

	print("Loading lookup_teams for team name resolution...")
	by_short, by_name = load_lookup_teams()
	print(f"  {len(by_short)} short names, {len(by_name)} full names")

	print(f"Extracting games for {args.season} D{args.division}...")
	games = extract_games(args.season, args.division, args.confidence, by_short, by_name)
	final = sum(1 for g in games if g["status"] == "final")
	scheduled = sum(1 for g in games if g["status"] == "scheduled")
	print(f"Found {len(games)} games ({final} final, {scheduled} scheduled)")

	if not games:
		print("Nothing to load")
		return

	load_to_database(games, args.dry_run)


if __name__ == "__main__":
	main()

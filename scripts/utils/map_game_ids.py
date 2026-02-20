#!/usr/bin/env python3
"""
Cross-reference ncaa.com game IDs with stats.ncaa.org game IDs.

Reads game_ids.json (stats.ncaa.org) and game_ids_ncaa.json (ncaa.com), matches
games by date + team name pair, and outputs a bidirectional map.

Usage:
	python3 scripts/utils/map_game_ids.py --season 2026
	python3 scripts/utils/map_game_ids.py --season 2026 --verbose
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.path_helpers import get_season_raw_dir, get_season_ncaa_dir, get_season_games_dir


def load_config(config_file="config.json") -> dict:
	"""Load configuration from JSON file."""
	config_path = Path(__file__).resolve().parent.parent.parent / config_file
	with open(config_path, "r") as f:
		return json.load(f)


def normalize(name: str) -> str:
	"""Normalize a team name for comparison."""
	name = name.lower().strip()
	name = re.sub(r'[^a-z0-9 ]', '', name)
	name = re.sub(r'\s+', ' ', name)
	return name


def token_overlap(a: str, b: str) -> float:
	"""Jaccard coefficient between word sets of two strings."""
	ta = set(normalize(a).split())
	tb = set(normalize(b).split())
	if not ta or not tb:
		return 0.0
	return len(ta & tb) / len(ta | tb)


def name_matches(a: str, b: str) -> tuple[bool, str]:
	"""
	Check if two team names refer to the same school.
	Returns (matched, confidence) where confidence is 'exact' or 'fuzzy'.
	"""
	if not a or not b:
		return False, ''
	na, nb = normalize(a), normalize(b)
	if na == nb:
		return True, 'exact'
	# One name is a substring of the other (e.g. "Virginia" vs "Virginia Cavaliers")
	if na in nb or nb in na:
		return True, 'exact'
	# Token overlap >= 0.5 (e.g. "UNC" vs "North Carolina" won't match, but "Notre Dame" vs "Notre Dame Fighting Irish" will)
	if token_overlap(a, b) >= 0.5:
		return True, 'fuzzy'
	return False, ''


def build_stats_game_map(season: str, division: int) -> dict[str, dict]:
	"""
	Build map of stats.ncaa.org games keyed by statsGameId.
	Enriches team names from game info files where available.
	"""
	raw_dir = get_season_raw_dir(season, division)
	games_dir = get_season_games_dir(season, division)

	ids_file = raw_dir / "game_ids.json"
	if not ids_file.exists():
		print(f"Warning: {ids_file} not found", file=sys.stderr)
		return {}

	with open(ids_file, "r") as f:
		raw_ids = json.load(f)

	stats_map: dict[str, dict] = {}
	for g in raw_ids:
		gid = str(g.get("gameID", ""))
		if not gid:
			continue
		stats_map[gid] = {
			"statsGameId": gid,
			"date": g.get("date", ""),
			"homeTeam": g.get("homeTeam", ""),
			"awayTeam": g.get("awayTeam", ""),
		}

	# Enrich with game info files (more reliable team names)
	for info_file in games_dir.glob("game_*_info.json"):
		parts = info_file.stem.split("_")
		if len(parts) < 2:
			continue
		gid = parts[1]
		if gid not in stats_map:
			continue
		try:
			with open(info_file, "r") as f:
				info = json.load(f)
			stats_map[gid]["homeTeam"] = info.get("homeTeam") or stats_map[gid]["homeTeam"]
			stats_map[gid]["awayTeam"] = info.get("awayTeam") or stats_map[gid]["awayTeam"]
		except Exception:
			pass

	return stats_map


def build_ncaa_game_list(season: str, division: int) -> list[dict]:
	"""Load ncaa.com game list from game_ids_ncaa.json."""
	ncaa_dir = get_season_ncaa_dir(season, division)
	ids_file = ncaa_dir / "game_ids_ncaa.json"
	if not ids_file.exists():
		print(f"Error: {ids_file} not found. Run get_game_ids_ncaa.py first.", file=sys.stderr)
		sys.exit(1)
	with open(ids_file, "r") as f:
		return json.load(f)


def match_games(
	stats_map: dict[str, dict],
	ncaa_games: list[dict],
	verbose: bool = False,
) -> list[dict]:
	"""Match ncaa.com games to stats.ncaa.org games by date + team name pair."""
	# Group stats games by date for fast lookup
	by_date: dict[str, list[dict]] = {}
	for g in stats_map.values():
		d = g.get("date", "")
		by_date.setdefault(d, []).append(g)

	results: list[dict] = []
	matched_stats_ids: set[str] = set()

	for ncaa_game in ncaa_games:
		gid = str(ncaa_game.get("ncaaGameId", ""))
		date = ncaa_game.get("date", "")
		ncaa_home = ncaa_game.get("homeTeam", "")
		ncaa_away = ncaa_game.get("awayTeam", "")

		candidates = by_date.get(date, [])
		best_match: dict | None = None
		best_confidence = ''

		for stats_game in candidates:
			stats_home = stats_game.get("homeTeam", "")
			stats_away = stats_game.get("awayTeam", "")
			if not stats_home or not stats_away:
				continue

			home_ok, home_conf = name_matches(ncaa_home, stats_home)
			away_ok, away_conf = name_matches(ncaa_away, stats_away)
			if home_ok and away_ok:
				confidence = 'exact' if home_conf == 'exact' and away_conf == 'exact' else 'fuzzy'
				best_match = stats_game
				best_confidence = confidence
				break

			# Also try reversed home/away (convention may differ between sites)
			home_ok2, home_conf2 = name_matches(ncaa_home, stats_away)
			away_ok2, away_conf2 = name_matches(ncaa_away, stats_home)
			if home_ok2 and away_ok2:
				confidence = 'exact' if home_conf2 == 'exact' and away_conf2 == 'exact' else 'fuzzy'
				best_match = stats_game
				best_confidence = confidence
				if verbose:
					print(f"  Note: home/away swapped for {ncaa_away} @ {ncaa_home} on {date}")
				break

		if best_match:
			sid = best_match["statsGameId"]
			matched_stats_ids.add(sid)
			results.append({
				"ncaaGameId": gid,
				"statsGameId": sid,
				"date": date,
				"homeTeam": ncaa_home or best_match.get("homeTeam", ""),
				"awayTeam": ncaa_away or best_match.get("awayTeam", ""),
				"matchConfidence": best_confidence,
			})
			if verbose:
				print(f"  [{best_confidence}] ncaa {gid} <-> stats {sid} | {ncaa_away} @ {ncaa_home} ({date})")
		else:
			results.append({
				"ncaaGameId": gid,
				"statsGameId": None,
				"date": date,
				"homeTeam": ncaa_home,
				"awayTeam": ncaa_away,
				"matchConfidence": "unmatched",
			})
			if verbose:
				print(f"  [unmatched] ncaa {gid} | {ncaa_away} @ {ncaa_home} ({date})")

	# Report stats games with no ncaa.com match
	unmatched_stats = [g for g in stats_map.values() if g["statsGameId"] not in matched_stats_ids]
	if unmatched_stats and verbose:
		print(f"\n  {len(unmatched_stats)} stats.ncaa.org games with no ncaa.com match:")
		for g in unmatched_stats[:10]:
			print(f"    stats {g['statsGameId']} | {g.get('awayTeam','')} @ {g.get('homeTeam','')} ({g.get('date','')})")
		if len(unmatched_stats) > 10:
			print(f"    ... and {len(unmatched_stats) - 10} more")

	return results


def main():
	parser = argparse.ArgumentParser(
		description="Cross-reference ncaa.com and stats.ncaa.org game IDs"
	)
	parser.add_argument("--season", required=True, help="Season year")
	parser.add_argument("--division", type=int, default=1)
	parser.add_argument("--verbose", "-v", action="store_true")
	parser.add_argument("--output", default="game_id_map.json")
	args = parser.parse_args()

	print(f"Loading stats.ncaa.org games for {args.season} D{args.division}...")
	stats_map = build_stats_game_map(args.season, args.division)
	print(f"  {len(stats_map)} games")

	print("Loading ncaa.com games...")
	ncaa_games = build_ncaa_game_list(args.season, args.division)
	print(f"  {len(ncaa_games)} games")

	print("Matching...")
	results = match_games(stats_map, ncaa_games, args.verbose)

	exact = sum(1 for r in results if r["matchConfidence"] == "exact")
	fuzzy = sum(1 for r in results if r["matchConfidence"] == "fuzzy")
	unmatched = sum(1 for r in results if r["matchConfidence"] == "unmatched")
	print(f"\nMatched {exact + fuzzy} ({exact} exact, {fuzzy} fuzzy), {unmatched} unmatched ncaa games")

	ncaa_dir = get_season_ncaa_dir(args.season, args.division)
	output_path = ncaa_dir / args.output
	with open(output_path, "w") as f:
		json.dump(results, f, indent=2)
	print(f"Saved {len(results)} entries to {output_path}")


if __name__ == "__main__":
	main()

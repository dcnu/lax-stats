#!/usr/bin/env python3
"""
Fetch NCAA lacrosse game data using agent-browser + JS DOM extractors.

Reads game IDs from data/{season}/division{n}/raw/game_ids.json, navigates to
each game's pages via agent-browser, runs JS extractors in the browser context,
and saves JSON output to data/{season}/division{n}/games/.

Prerequisite: Launch browser with --remote-debugging-port=9222, then:
	agent-browser connect 9222

Usage:
	python3 scripts/fetching/fetch_games_browser.py --season 2026
	python3 scripts/fetching/fetch_games_browser.py --season 2026 --dry-run
	python3 scripts/fetching/fetch_games_browser.py --season 2026 --division 1
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.path_helpers import get_season_games_dir, get_season_raw_dir
from utils.browser_common import run_ab, eval_js_inline, wait_for_selector, eval_js, parse_eval_json

JS_DIR = Path(__file__).parent.parent / "utils"
JS_GAME_INFO = JS_DIR / "_extract_game_info.js"
JS_PLAYER_STATS = JS_DIR / "_extract_player_stats.js"
JS_PLAYS = JS_DIR / "_extract_plays.js"


def load_game_ids(season: str, division: int) -> list[dict]:
	"""Load game IDs from the raw directory."""
	raw_dir = get_season_raw_dir(season, division)
	ids_file = raw_dir / "game_ids.json"
	if not ids_file.exists():
		print(f"Error: {ids_file} not found", file=sys.stderr)
		sys.exit(1)
	with open(ids_file, "r") as f:
		return json.load(f)


def game_files_exist(game_id: str, games_dir: Path) -> bool:
	"""Check if all 3 output files already exist for a game."""
	suffixes = ["info", "player_stats", "plays"]
	return all((games_dir / f"game_{game_id}_{s}.json").exists() for s in suffixes)


def check_error_flag() -> str | None:
	"""Check if the current page has an NCAA box score error banner."""
	js = (
		"(() => {"
		"  const t = document.body.innerText;"
		"  const i = t.indexOf('box score has errors');"
		"  if (i < 0) return '';"
		"  const start = t.lastIndexOf('This', i);"
		"  const end = t.indexOf('\\n\\n', i);"
		"  return t.substring(start > -1 ? start : i, end > i ? end : i + 300);"
		"})()"
	)
	result = eval_js_inline(js)
	return result if result else None


def fetch_game(game_id: str, games_dir: Path) -> str | None:
	"""Fetch and save all data for a single game. Returns error flag text or None."""
	base_url = "https://stats.ncaa.org/contests"

	# --- Individual stats page ---
	stats_url = f"{base_url}/{game_id}/individual_stats"
	run_ab("open", stats_url)
	if not wait_for_selector('div.table-responsive table'):
		raise ValueError("Timed out waiting for stats table to render")

	# Check for NCAA error flag
	error_flag = check_error_flag()

	# Extract game info
	raw_info = eval_js(JS_GAME_INFO)
	game_info = parse_eval_json(raw_info)
	if isinstance(game_info, dict) and "error" in game_info:
		raise ValueError(f"Game info extraction failed: {game_info['error']}")
	game_info["gameId"] = game_id

	info_path = games_dir / f"game_{game_id}_info.json"
	with open(info_path, "w", encoding="utf-8") as f:
		json.dump(game_info, f, indent=2)

	# Extract player stats
	raw_stats = eval_js(JS_PLAYER_STATS)
	player_stats = parse_eval_json(raw_stats)

	stats_path = games_dir / f"game_{game_id}_player_stats.json"
	with open(stats_path, "w", encoding="utf-8") as f:
		json.dump(player_stats, f, indent=2)

	# Rate limit between navigations
	time.sleep(2)

	# --- Play-by-play page ---
	pbp_url = f"{base_url}/{game_id}/play_by_play"
	run_ab("open", pbp_url)
	if not wait_for_selector('.card.table-responsive'):
		raise ValueError("Timed out waiting for play-by-play to render")

	raw_plays = eval_js(JS_PLAYS)
	plays = parse_eval_json(raw_plays)

	plays_path = games_dir / f"game_{game_id}_plays.json"
	with open(plays_path, "w", encoding="utf-8") as f:
		json.dump(plays, f, indent=2)

	return error_flag


def main():
	parser = argparse.ArgumentParser(
		description="Fetch NCAA lacrosse game data via agent-browser"
	)
	parser.add_argument("--season", default="2026", help="Season year (default: 2026)")
	parser.add_argument(
		"--division", type=int, default=1, choices=[1, 2, 3],
		help="NCAA division (default: 1)"
	)
	parser.add_argument("--dry-run", action="store_true", help="List games without fetching")
	args = parser.parse_args()

	games = load_game_ids(args.season, args.division)
	games_dir = get_season_games_dir(args.season, args.division)

	# Determine which games need fetching
	to_fetch = []
	for g in games:
		gid = str(g["gameID"])
		if not game_files_exist(gid, games_dir):
			to_fetch.append(gid)

	print(f"{len(to_fetch)}/{len(games)} games to fetch for {args.season} D{args.division}")

	if args.dry_run:
		for gid in to_fetch:
			print(f"  would fetch: {gid}")
		return

	if not to_fetch:
		print("Nothing to fetch")
		return

	failed = []
	flagged = []
	for i, gid in enumerate(to_fetch, 1):
		print(f"[{i}/{len(to_fetch)}] game {gid} — fetching...")
		try:
			error_flag = fetch_game(gid, games_dir)
			if error_flag:
				print(f"[{i}/{len(to_fetch)}] game {gid} — done (FLAGGED)")
				info_path = games_dir / f"game_{gid}_info.json"
				with open(info_path) as f:
					info = json.load(f)
				flagged.append({
					"gameID": gid,
					"error": error_flag,
					"awayTeam": info.get("awayTeam", ""),
					"homeTeam": info.get("homeTeam", ""),
					"gameDate": info.get("gameDate", ""),
				})
			else:
				print(f"[{i}/{len(to_fetch)}] game {gid} — done")
		except Exception as e:
			print(f"[{i}/{len(to_fetch)}] game {gid} — FAILED: {e}", file=sys.stderr)
			failed.append({"gameID": gid, "error": str(e)})

		# Rate limit between games
		if i < len(to_fetch):
			time.sleep(2)

	if failed:
		failed_path = games_dir / "failed_games.json"
		with open(failed_path, "w") as f:
			json.dump(failed, f, indent=2)
		print(f"\n{len(failed)} games failed — see {failed_path}")

	if flagged:
		flagged_path = games_dir / "flagged_games.json"
		with open(flagged_path, "w") as f:
			json.dump(flagged, f, indent=2)
		print(f"{len(flagged)} games flagged — see {flagged_path}")

	succeeded = len(to_fetch) - len(failed)
	print(f"\nComplete: {succeeded} fetched, {len(failed)} failed")


if __name__ == "__main__":
	main()

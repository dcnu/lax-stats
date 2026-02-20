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
	python3 scripts/fetching/fetch_games_browser.py --season 2026 --end-date 02/17/2026
	python3 scripts/fetching/fetch_games_browser.py --season 2026 --force-games 6511704,6523037
	python3 scripts/fetching/fetch_games_browser.py --season 2026 --dry-run
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.path_helpers import get_season_games_dir, get_season_raw_dir
from utils.browser_common import run_ab, eval_js_inline, wait_for_selector, eval_js, parse_eval_json

JS_DIR = Path(__file__).parent.parent / "utils"
JS_GAME_INFO = JS_DIR / "_extract_game_info.js"
JS_PLAYER_STATS = JS_DIR / "_extract_player_stats.js"
JS_PLAYS = JS_DIR / "_extract_plays.js"


def load_config(config_file="config.json"):
	"""Load configuration from JSON file."""
	config_path = Path(__file__).resolve().parent.parent.parent / config_file
	with open(config_path, "r") as f:
		return json.load(f)


def load_game_ids(season: str, division: int) -> list[dict]:
	"""Load game IDs from the raw directory."""
	raw_dir = get_season_raw_dir(season, division)
	ids_file = raw_dir / "game_ids.json"
	if not ids_file.exists():
		print(f"Error: {ids_file} not found", file=sys.stderr)
		sys.exit(1)
	with open(ids_file, "r") as f:
		return json.load(f)


def load_failed_ids(games_dir: Path) -> set[str]:
	"""Load game IDs from failed_games.json to skip them."""
	failed_path = games_dir / "failed_games.json"
	if not failed_path.exists():
		return set()
	with open(failed_path, "r") as f:
		return {str(entry["gameID"]) for entry in json.load(f)}


def game_files_exist(game_id: str, games_dir: Path) -> bool:
	"""Check if all 3 output files already exist for a game."""
	suffixes = ["info", "player_stats", "plays"]
	return all((games_dir / f"game_{game_id}_{s}.json").exists() for s in suffixes)


def delete_game_files(game_id: str, games_dir: Path) -> None:
	"""Delete all existing output files for a game."""
	for suffix in ["info", "player_stats", "plays"]:
		path = games_dir / f"game_{game_id}_{suffix}.json"
		if path.exists():
			path.unlink()


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


def fetch_game(game_id: str, games_dir: Path, between_navigations: int) -> str | None:
	"""Fetch and save all data for a single game. Returns error flag text or None."""
	base_url = "https://stats.ncaa.org/contests"

	# --- Individual stats page ---
	stats_url = f"{base_url}/{game_id}/individual_stats"
	run_ab("open", stats_url)
	if not wait_for_selector('div.table-responsive table'):
		raise ValueError("Timed out waiting for stats table to render")

	error_flag = check_error_flag()

	raw_info = eval_js(JS_GAME_INFO)
	game_info = parse_eval_json(raw_info)
	if isinstance(game_info, dict) and "error" in game_info:
		raise ValueError(f"Game info extraction failed: {game_info['error']}")
	game_info["gameId"] = game_id

	info_path = games_dir / f"game_{game_id}_info.json"
	with open(info_path, "w", encoding="utf-8") as f:
		json.dump(game_info, f, indent=2)

	raw_stats = eval_js(JS_PLAYER_STATS)
	player_stats = parse_eval_json(raw_stats)

	stats_path = games_dir / f"game_{game_id}_player_stats.json"
	with open(stats_path, "w", encoding="utf-8") as f:
		json.dump(player_stats, f, indent=2)

	time.sleep(between_navigations)

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


def load_existing_flagged(games_dir: Path) -> list[dict]:
	"""Load existing flagged_games.json entries."""
	flagged_path = games_dir / "flagged_games.json"
	if not flagged_path.exists():
		return []
	with open(flagged_path, "r") as f:
		return json.load(f)


def save_flagged(games_dir: Path, flagged: list[dict]) -> None:
	flagged_path = games_dir / "flagged_games.json"
	with open(flagged_path, "w") as f:
		json.dump(flagged, f, indent=2)


def save_failed(games_dir: Path, failed: list[dict]) -> None:
	failed_path = games_dir / "failed_games.json"
	existing = []
	if failed_path.exists():
		with open(failed_path, "r") as f:
			existing = json.load(f)
	existing_ids = {str(e["gameID"]) for e in existing}
	merged = existing + [e for e in failed if str(e["gameID"]) not in existing_ids]
	with open(failed_path, "w") as f:
		json.dump(merged, f, indent=2)


def main():
	parser = argparse.ArgumentParser(
		description="Fetch NCAA lacrosse game data via agent-browser"
	)
	parser.add_argument("--season", default="2026", help="Season year (default: 2026)")
	parser.add_argument(
		"--division", type=int, default=1, choices=[1, 2, 3],
		help="NCAA division (default: 1)"
	)
	parser.add_argument(
		"--end-date", metavar="MM/DD/YYYY",
		help="Skip games with date after this date"
	)
	parser.add_argument(
		"--force-games", metavar="ID1,ID2,...",
		help="Delete existing files and re-fetch these game IDs"
	)
	parser.add_argument(
		"--batch-size", type=int, default=None,
		help="Override config batch_size"
	)
	parser.add_argument(
		"--batch-delay", type=int, default=None,
		help="Override config batch_delay (seconds)"
	)
	parser.add_argument("--dry-run", action="store_true", help="List games without fetching")
	args = parser.parse_args()

	config = load_config()
	rl = config.get("browser_rate_limiting", {})
	between_navigations = rl.get("between_navigations", 6)
	between_games = rl.get("between_games", 10)
	batch_size = args.batch_size if args.batch_size is not None else rl.get("batch_size", 15)
	batch_delay = args.batch_delay if args.batch_delay is not None else rl.get("batch_delay", 900)

	games = load_game_ids(args.season, args.division)
	games_dir = get_season_games_dir(args.season, args.division)
	failed_ids = load_failed_ids(games_dir)

	end_date = None
	if args.end_date:
		end_date = datetime.strptime(args.end_date, "%m/%d/%Y")

	force_ids: set[str] = set()
	if args.force_games:
		force_ids = {gid.strip() for gid in args.force_games.split(",")}
		for gid in force_ids:
			delete_game_files(gid, games_dir)
		print(f"Force-fetching {len(force_ids)} games: {', '.join(sorted(force_ids))}")

	to_fetch = []
	for g in games:
		gid = str(g["gameID"])
		game_date_str = g.get("date", "")

		if gid in force_ids:
			to_fetch.append(gid)
			continue

		if gid in failed_ids:
			continue

		if end_date and game_date_str:
			try:
				gd = datetime.strptime(game_date_str, "%m/%d/%Y")
				if gd > end_date:
					continue
			except ValueError:
				pass

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
	flagged = load_existing_flagged(games_dir)
	flagged_ids = {str(f["gameID"]) for f in flagged}

	total = len(to_fetch)
	for batch_start in range(0, total, batch_size):
		batch = to_fetch[batch_start:batch_start + batch_size]
		batch_num = batch_start // batch_size + 1
		total_batches = (total + batch_size - 1) // batch_size

		if batch_start > 0:
			print(f"\nBatch {batch_num}/{total_batches} — waiting {batch_delay}s before next batch...")
			time.sleep(batch_delay)

		print(f"\nBatch {batch_num}/{total_batches} ({len(batch)} games)")

		for j, gid in enumerate(batch, 1):
			overall = batch_start + j
			print(f"[{overall}/{total}] game {gid} — fetching...")
			try:
				error_flag = fetch_game(gid, games_dir, between_navigations)
				if error_flag:
					print(f"[{overall}/{total}] game {gid} — done (FLAGGED)")
					info_path = games_dir / f"game_{gid}_info.json"
					with open(info_path) as f:
						info = json.load(f)
					if gid not in flagged_ids:
						flagged.append({
							"gameID": gid,
							"error": error_flag,
							"awayTeam": info.get("awayTeam", ""),
							"homeTeam": info.get("homeTeam", ""),
							"gameDate": info.get("gameDate", ""),
						})
						flagged_ids.add(gid)
					else:
						# Update existing entry
						for entry in flagged:
							if str(entry["gameID"]) == gid:
								entry["error"] = error_flag
								break
				else:
					print(f"[{overall}/{total}] game {gid} — done")
					# Remove from flagged if error was corrected
					if gid in flagged_ids:
						flagged = [f for f in flagged if str(f["gameID"]) != gid]
						flagged_ids.discard(gid)
						print(f"[{overall}/{total}] game {gid} — removed from flagged (error corrected)")
			except Exception as e:
				print(f"[{overall}/{total}] game {gid} — FAILED: {e}", file=sys.stderr)
				failed.append({"gameID": gid, "error": str(e)})

			if j < len(batch):
				time.sleep(between_games)

	if failed:
		save_failed(games_dir, failed)
		failed_path = games_dir / "failed_games.json"
		print(f"\n{len(failed)} games failed — see {failed_path}")

	save_flagged(games_dir, flagged)
	if flagged:
		flagged_path = games_dir / "flagged_games.json"
		print(f"{len(flagged)} games flagged — see {flagged_path}")

	succeeded = total - len(failed)
	print(f"\nComplete: {succeeded} fetched, {len(failed)} failed")


if __name__ == "__main__":
	main()

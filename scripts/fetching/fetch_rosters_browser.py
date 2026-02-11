#!/usr/bin/env python3
"""
Fetch NCAA lacrosse team rosters using agent-browser + JS DOM extractor.

Discovers team IDs from game_info.json files, navigates to each team's roster
page via agent-browser, runs JS extractor, and saves JSON output.

Prerequisite: Launch browser with --remote-debugging-port=9222, then:
	agent-browser connect 9222

Usage:
	python3 scripts/fetching/fetch_rosters_browser.py --season 2026
	python3 scripts/fetching/fetch_rosters_browser.py --season 2026 --dry-run
	python3 scripts/fetching/fetch_rosters_browser.py --season 2026 --division 1
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.path_helpers import get_season_games_dir, get_season_raw_dir
from utils.browser_common import run_ab, wait_for_selector, eval_js, parse_eval_json

JS_DIR = Path(__file__).parent.parent / "utils"
JS_ROSTER = JS_DIR / "_extract_roster.js"


def discover_team_ids(season: str, division: int) -> dict[str, str]:
	"""Discover unique team IDs from game_info.json files.

	Returns:
		Dict mapping teamId -> teamName
	"""
	games_dir = get_season_games_dir(season, division)
	teams = {}

	for info_file in games_dir.glob("game_*_info.json"):
		try:
			with open(info_file, "r", encoding="utf-8") as f:
				info = json.load(f)

			for prefix in ("home", "away"):
				team_id = info.get(f"{prefix}TeamId")
				team_name = info.get(f"{prefix}Team")
				if team_id and team_id not in teams:
					teams[team_id] = team_name or team_id
		except Exception as e:
			print(f"Warning: Error reading {info_file}: {e}", file=sys.stderr)
			continue

	return teams


def get_rosters_dir(season: str, division: int) -> Path:
	"""Get path to rosters directory for a season and division."""
	path = Path("data") / season / f"division{division}" / "rosters"
	path.mkdir(parents=True, exist_ok=True)
	return path


def roster_file_exists(team_id: str, rosters_dir: Path) -> bool:
	"""Check if a roster file already exists for a team."""
	return (rosters_dir / f"team_{team_id}_roster.json").exists()


def fetch_roster(team_id: str, rosters_dir: Path) -> list:
	"""Fetch and save roster for a single team. Returns player list."""
	url = f"https://stats.ncaa.org/teams/{team_id}/roster"
	run_ab("open", url)

	selector = "table#rosters_form_players_16980_data_table"
	if not wait_for_selector(selector, timeout=15.0):
		raise ValueError(f"Timed out waiting for roster table on team {team_id}")

	raw = eval_js(JS_ROSTER)
	data = parse_eval_json(raw)

	if isinstance(data, dict) and "error" in data:
		raise ValueError(f"Roster extraction failed: {data['error']}")

	roster_path = rosters_dir / f"team_{team_id}_roster.json"
	with open(roster_path, "w", encoding="utf-8") as f:
		json.dump(data, f, indent=2)

	return data


def aggregate_rosters(season: str, division: int, teams: dict[str, str]) -> None:
	"""Aggregate per-team roster files into rosters.json."""
	rosters_dir = get_rosters_dir(season, division)
	raw_dir = get_season_raw_dir(season, division)
	aggregated = []

	for team_id, team_name in sorted(teams.items()):
		roster_file = rosters_dir / f"team_{team_id}_roster.json"
		if not roster_file.exists():
			print(f"Warning: No roster file for team {team_id} ({team_name})", file=sys.stderr)
			continue

		with open(roster_file, "r", encoding="utf-8") as f:
			players = json.load(f)

		team_entry = {
			"teamID": team_id,
			"players": []
		}

		for p in players:
			jersey = p.get("jersey", "")
			try:
				roster_number = int(jersey)
			except (ValueError, TypeError):
				roster_number = 0

			team_entry["players"].append({
				"playerID": str(p["playerId"]),
				"name": p.get("name", ""),
				"teamID": team_id,
				"rosterNumber": roster_number,
				"year": p.get("classYear", ""),
				"classYear": p.get("classYear", ""),
				"position": p.get("position", ""),
				"hometown": p.get("hometown", ""),
				"highSchool": p.get("highSchool", ""),
				"gamesPlayed": p.get("gamesPlayed", 0),
				"gamesStarted": p.get("gamesStarted", 0),
			})

		aggregated.append(team_entry)

	rosters_path = raw_dir / "rosters.json"
	with open(rosters_path, "w", encoding="utf-8") as f:
		json.dump(aggregated, f, indent=2)

	total_players = sum(len(t["players"]) for t in aggregated)
	print(f"Aggregated {total_players} players from {len(aggregated)} teams into {rosters_path}")


def main():
	parser = argparse.ArgumentParser(
		description="Fetch NCAA lacrosse team rosters via agent-browser"
	)
	parser.add_argument("--season", default="2026", help="Season year (default: 2026)")
	parser.add_argument(
		"--division", type=int, default=1, choices=[1, 2, 3],
		help="NCAA division (default: 1)"
	)
	parser.add_argument("--dry-run", action="store_true", help="List teams without fetching")
	args = parser.parse_args()

	teams = discover_team_ids(args.season, args.division)
	rosters_dir = get_rosters_dir(args.season, args.division)

	# Determine which teams need fetching
	to_fetch = {
		tid: name for tid, name in teams.items()
		if not roster_file_exists(tid, rosters_dir)
	}

	print(f"{len(to_fetch)}/{len(teams)} team rosters to fetch for {args.season} D{args.division}")

	if args.dry_run:
		for tid, name in sorted(to_fetch.items(), key=lambda x: x[1]):
			print(f"  would fetch: {tid} ({name})")
		return

	if not to_fetch:
		print("Nothing to fetch, aggregating existing rosters...")
		aggregate_rosters(args.season, args.division, teams)
		return

	failed = []
	for i, (tid, name) in enumerate(sorted(to_fetch.items(), key=lambda x: x[1]), 1):
		print(f"[{i}/{len(to_fetch)}] team {tid} ({name}) — fetching...")
		try:
			players = fetch_roster(tid, rosters_dir)
			print(f"[{i}/{len(to_fetch)}] team {tid} ({name}) — {len(players)} players")
		except Exception as e:
			print(f"[{i}/{len(to_fetch)}] team {tid} ({name}) — FAILED: {e}", file=sys.stderr)
			failed.append({"teamID": tid, "teamName": name, "error": str(e)})

		# Rate limit between teams
		if i < len(to_fetch):
			time.sleep(2)

	if failed:
		failed_path = rosters_dir / "failed_rosters.json"
		with open(failed_path, "w") as f:
			json.dump(failed, f, indent=2)
		print(f"\n{len(failed)} teams failed — see {failed_path}")

	succeeded = len(to_fetch) - len(failed)
	print(f"\nComplete: {succeeded} fetched, {len(failed)} failed")

	# Aggregate all rosters into rosters.json
	aggregate_rosters(args.season, args.division, teams)


if __name__ == "__main__":
	main()

#!/usr/bin/env python3
"""
Roster coverage audit for NCAA player stats files.

For each D1 team in the target season, checks whether player stats in
game_*_player_stats.json files can be resolved to known player IDs.
Collects unique (name, jersey) pairs for unresolved players and outputs
a missing_roster_report.json listing teams and their coverage gaps.

Does NOT create synthetic player IDs — surfaces gaps for manual resolution
or future API enrichment.

Usage:
	python3 scripts/fetching/fetch_rosters_ncaa.py --season 2026
	python3 scripts/fetching/fetch_rosters_ncaa.py --season 2026 --division 1
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.db import execute_query
from utils.path_helpers import get_season_ncaa_dir
from utils.pbp_parser import match_player_to_roster
from transform.player_stats import normalize_player_stats


def load_roster_json(season_id: str, division: int, base_dir: str = "data") -> dict[str, list]:
	"""
	Load rosters.json into {teamID: [playerID, ...]} mapping.

	Returns a dict keyed by teamID string.
	"""
	raw_path = Path(base_dir) / season_id / f"division{division}" / "raw" / "rosters.json"
	if not raw_path.exists():
		return {}

	with open(raw_path, "r", encoding="utf-8") as f:
		rosters = json.load(f)

	result = {}
	for team in rosters:
		team_id = str(team.get("teamID", ""))
		players = []
		for player in team.get("players", []):
			pid = player.get("playerID")
			if pid:
				try:
					players.append({
						"id": int(pid),
						"name": player.get("name", ""),
					})
				except (ValueError, TypeError):
					continue
		if team_id:
			result[team_id] = players
	return result


def build_roster_lookup(players: list) -> dict:
	"""Build {playerID: {name, teamID}} for match_player_to_roster compatibility."""
	return {p["id"]: {"name": p["name"], "teamID": ""} for p in players}


def audit_season(season_id: str, division: int, base_dir: str = "data") -> dict:
	"""
	Audit player stat coverage for all teams in the season.

	Returns a dict structured as:
	{
	  team_id: {
	    team_name: str,
	    has_roster_file: bool,
	    games_checked: int,
	    total_player_entries: int,
	    resolved: int,
	    unresolved: int,
	    unresolved_players: [{name, jersey, game_ids}]
	  }
	}
	"""
	ncaa_dir = get_season_ncaa_dir(season_id, division, base_dir)
	roster_json = load_roster_json(season_id, division, base_dir)

	# Get all teams in this season with their names
	teams = execute_query(
		"SELECT team_id, team_name FROM team_seasons WHERE season_id = %s ORDER BY team_name",
		(season_id,),
	)
	if not teams:
		print(f"No team_seasons entries for season {season_id}", file=sys.stderr)
		return {}

	# Get all final games with ncaa stats files for this season
	stats_files = {f.stem.split("_")[1]: f for f in ncaa_dir.glob("game_*_player_stats.json")}
	if not stats_files:
		print(f"No ncaa player stats files found in {ncaa_dir}", file=sys.stderr)
		return {}

	game_rows = execute_query(
		"""SELECT id, ncaa_game_id, home_team_id, away_team_id
		FROM games
		WHERE season_id = %s AND status = 'final' AND ncaa_game_id = ANY(%s)""",
		(season_id, list(stats_files.keys())),
	)
	if not game_rows:
		print("No final games with stats files found", file=sys.stderr)
		return {}

	# Build team_id → [game_rows] index
	team_games: dict[str, list] = defaultdict(list)
	for row in game_rows:
		team_games[row["home_team_id"]].append(row)
		team_games[row["away_team_id"]].append(row)

	# Build slug → [team_ids] bridge from lookup_teams
	slug_bridge: dict[str, list[str]] = defaultdict(list)
	slug_rows = execute_query("SELECT id, slug FROM lookup_teams WHERE slug IS NOT NULL")
	if slug_rows:
		for r in slug_rows:
			slug_bridge[r["slug"]].append(r["id"])

	report = {}

	for team_row in teams:
		team_id = team_row["team_id"]
		team_name = team_row["team_name"]

		# Find roster data: try direct, then slug bridge
		roster_players = roster_json.get(team_id)
		has_roster_file = roster_players is not None

		if not has_roster_file:
			# Try slug bridge
			slug_rows2 = execute_query(
				"SELECT slug FROM lookup_teams WHERE id = %s", (team_id,)
			)
			if slug_rows2 and slug_rows2[0]["slug"]:
				slug = slug_rows2[0]["slug"]
				alt_ids = [aid for aid in slug_bridge.get(slug, []) if aid != team_id]
				for alt_id in alt_ids:
					if alt_id in roster_json:
						roster_players = roster_json[alt_id]
						break

		roster_lookup = build_roster_lookup(roster_players) if roster_players else {}

		games_for_team = team_games.get(team_id, [])
		games_checked = 0
		total_entries = 0
		resolved = 0
		unresolved_map: dict[str, dict] = {}  # name → {jersey, game_ids}

		for game in games_for_team:
			ncaa_id = str(game["ncaa_game_id"])
			stats_file = stats_files.get(ncaa_id)
			if not stats_file:
				continue

			games_checked += 1
			try:
				with open(stats_file, "r", encoding="utf-8") as f:
					data = json.load(f)
			except Exception:
				continue

			is_home = game["home_team_id"] == team_id

			for cs in normalize_player_stats(data, source="ncaa_com"):
				if cs.side == "home" and not is_home:
					continue
				if cs.side == "away" and is_home:
					continue
				if not cs.name:
					continue

				total_entries += 1
				player_id = match_player_to_roster(cs.name, roster_lookup) if roster_lookup else None

				if player_id is not None:
					resolved += 1
				else:
					key = cs.name.strip()
					if key not in unresolved_map:
						unresolved_map[key] = {"name": key, "jersey": cs.jersey_number, "game_ids": []}
					unresolved_map[key]["game_ids"].append(str(game["id"]))

		unresolved = len(unresolved_map)
		report[team_id] = {
			"team_name": team_name,
			"has_roster_file": has_roster_file,
			"games_checked": games_checked,
			"total_player_entries": total_entries,
			"resolved": resolved,
			"unresolved": unresolved,
			"unresolved_players": list(unresolved_map.values()),
		}

		status = "OK" if unresolved == 0 else f"MISSING {unresolved}"
		print(f"  {team_name:<35} games={games_checked:3d}  resolved={resolved:4d}  unresolved={unresolved:4d}  [{status}]")

	return report


def main():
	parser = argparse.ArgumentParser(description="Audit roster coverage for NCAA player stats")
	parser.add_argument("--season", default="2026")
	parser.add_argument("--division", type=int, default=1, choices=[1, 2, 3])
	parser.add_argument("--data-dir", default="data")
	parser.add_argument("--output", help="Output JSON path (default: ncaa dir/missing_roster_report.json)")
	args = parser.parse_args()

	print(f"Auditing roster coverage for {args.season} D{args.division}...")
	report = audit_season(args.season, args.division, args.data_dir)

	if not report:
		sys.exit(1)

	# Summary
	total_teams = len(report)
	no_roster = sum(1 for v in report.values() if not v["has_roster_file"])
	has_gaps = sum(1 for v in report.values() if v["unresolved"] > 0)
	print(f"\nSummary: {total_teams} teams, {no_roster} without roster file, {has_gaps} with unresolved players")

	# Write report
	ncaa_dir = get_season_ncaa_dir(args.season, args.division, args.data_dir)
	out_path = Path(args.output) if args.output else ncaa_dir / "missing_roster_report.json"
	with open(out_path, "w", encoding="utf-8") as f:
		json.dump(report, f, indent=2, default=str)
	print(f"Report written to {out_path}")


if __name__ == "__main__":
	main()

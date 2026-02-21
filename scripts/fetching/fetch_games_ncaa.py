#!/usr/bin/env python3
"""
Fetch NCAA game center data (box scores, play-by-play) via sdataprod.ncaa.com GraphQL API.

No browser required — uses persisted GraphQL GET queries directly.

Reads game IDs from data/{season}/division{n}/ncaa/game_ids_ncaa.json and saves
three JSON files per game to the same directory.

Usage:
	python3 scripts/fetching/fetch_games_ncaa.py --season 2026
	python3 scripts/fetching/fetch_games_ncaa.py --season 2026 --end-date 02/17/2026
	python3 scripts/fetching/fetch_games_ncaa.py --season 2026 --force-games ID1,ID2
	python3 scripts/fetching/fetch_games_ncaa.py --season 2026 --dry-run
"""

import argparse
import datetime
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.path_helpers import get_season_ncaa_dir

API_BASE = "https://sdataprod.ncaa.com/"
HEADERS = {
	"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
	"Referer": "https://www.ncaa.com/",
	"Accept": "*/*",
}
BOXSCORE_HASH = "dfd0e926e92e81c2917b8f4ae564fbdcd5c69cd0441a2a8095b6b09e4cee7c36"
PBP_HASH = "57f922d56d60d88326b62202b3d88e8cd3cfb6687931bc0b5b3dfab089b84faa"
GAME_INFO_HASH = "98558d123db05e23bd2999e409ab91245217ed00bed3a154ef6e3a0940b03daa"

MONTH_NAMES = [
	"", "January", "February", "March", "April", "May", "June",
	"July", "August", "September", "October", "November", "December",
]


def load_config(config_file: str = "config.json") -> dict:
	"""Load configuration from JSON file."""
	config_path = Path(__file__).resolve().parent.parent.parent / config_file
	with open(config_path, "r") as f:
		return json.load(f)


def gql_get(operation: str, sha256_hash: str, variables: dict, timeout: int = 30) -> dict:
	"""Execute a persisted GraphQL GET query against sdataprod.ncaa.com."""
	ext = json.dumps(
		{"persistedQuery": {"version": 1, "sha256Hash": sha256_hash}},
		separators=(",", ":"),
	)
	var = json.dumps(variables, separators=(",", ":"))
	url = API_BASE + "?" + urllib.parse.urlencode(
		{"meta": operation, "extensions": ext, "variables": var},
		quote_via=urllib.parse.quote,
	)
	req = urllib.request.Request(url, headers=HEADERS)
	try:
		with urllib.request.urlopen(req, timeout=timeout) as resp:
			return json.loads(resp.read().decode("utf-8"))
	except urllib.error.HTTPError as e:
		raise RuntimeError(f"HTTP {e.code}: {e.reason}")
	except Exception as e:
		raise RuntimeError(f"Request failed: {e}")


def ordinal_suffix(day: int) -> str:
	"""Return ordinal suffix for a day number."""
	if 11 <= day <= 13:
		return "th"
	return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def epoch_to_game_date(epoch: int | None) -> str:
	"""Convert Unix epoch to 'Month Dth YYYY' format using UTC date."""
	if not epoch:
		return ""
	dt = datetime.datetime.fromtimestamp(epoch, tz=ZoneInfo("America/New_York"))
	suffix = ordinal_suffix(dt.day)
	return f"{MONTH_NAMES[dt.month]} {dt.day}{suffix} {dt.year}"


def safe_str(value) -> str:
	"""Convert value to string, '' for None."""
	return "" if value is None else str(value)


def safe_int_str(value) -> str:
	"""Convert numeric value to string, '0' for None/invalid."""
	if value is None:
		return "0"
	try:
		return str(int(value))
	except (ValueError, TypeError):
		return "0"


def load_game_ids(season: str, division: int) -> list[dict]:
	"""Load game IDs from the ncaa directory."""
	ncaa_dir = get_season_ncaa_dir(season, division)
	ids_file = ncaa_dir / "game_ids_ncaa.json"
	if not ids_file.exists():
		print(f"Error: {ids_file} not found. Run get_game_ids_ncaa.py first.", file=sys.stderr)
		sys.exit(1)
	with open(ids_file, "r") as f:
		return json.load(f)


def game_files_exist(game_id: str, ncaa_dir: Path) -> bool:
	"""Check if all 3 output files exist for a game."""
	return all(
		(ncaa_dir / f"game_{game_id}_{s}.json").exists()
		for s in ["info", "player_stats", "plays"]
	)


def game_info_exists(game_id: str, ncaa_dir: Path) -> bool:
	"""Check if the info file exists for a game (used for scheduled-only fetches)."""
	return (ncaa_dir / f"game_{game_id}_info.json").exists()


def fetch_game_info_only(game_id: str, ncaa_dir: Path) -> None:
	"""Fetch and save only the game_info file (for scheduled/pre-status games)."""
	info = fetch_game_info(game_id)
	with open(ncaa_dir / f"game_{game_id}_info.json", "w", encoding="utf-8") as f:
		json.dump(info, f, indent=2)


def delete_game_files(game_id: str, ncaa_dir: Path) -> None:
	"""Delete existing output files for a game."""
	for suffix in ["info", "player_stats", "plays"]:
		path = ncaa_dir / f"game_{game_id}_{suffix}.json"
		if path.exists():
			path.unlink()


def load_failed_ids(ncaa_dir: Path) -> set[str]:
	"""Load previously failed game IDs."""
	failed_path = ncaa_dir / "failed_games.json"
	if not failed_path.exists():
		return set()
	with open(failed_path, "r") as f:
		return {str(entry["gameID"]) for entry in json.load(f)}


def fetch_game_info(game_id: str) -> dict:
	"""
	Fetch game metadata (date, location, teams, score).

	Returns dict with ncaaGameId, homeTeam, awayTeam, homeScore, awayScore,
	location ('Venue, City, ST'), and gameDate ('Month Dth YYYY').
	"""
	data = gql_get(
		"GetGamecenterGameById_web",
		GAME_INFO_HASH,
		{"id": game_id, "week": None, "staticTestEnv": None},
	)
	contests = ((data.get("data") or {}).get("contests")) or []
	contest = contests[0] if contests else {}

	teams = contest.get("teams") or []
	home_team = next((t for t in teams if t.get("isHome")), None)
	away_team = next((t for t in teams if not t.get("isHome")), None)

	loc = contest.get("location") or {}
	venue_parts = [loc.get("venue"), loc.get("city"), loc.get("stateUsps")]
	location = ", ".join(p for p in venue_parts if p)

	return {
		"ncaaGameId": game_id,
		"awayTeam": away_team.get("nameShort", "") if away_team else "",
		"awayScore": away_team.get("score") if away_team else None,
		"homeTeam": home_team.get("nameShort", "") if home_team else "",
		"homeScore": home_team.get("score") if home_team else None,
		"location": location,
		"gameDate": epoch_to_game_date(contest.get("startTimeEpoch")),
	}


def map_player(p: dict) -> dict:
	"""Map a playerStats entry to the standard output format."""
	first = p.get("firstName") or ""
	last = p.get("lastName") or ""
	name = f"{first} {last}".strip().upper()
	return {
		"NO": safe_str(p.get("number") or ""),
		"Name": name,
		"POS": safe_str(p.get("position") or ""),
		"G": safe_int_str(p.get("goals")),
		"A": safe_int_str(p.get("assists")),
		"SH": safe_int_str(p.get("shots")),
		"SOG": safe_int_str(p.get("shotsOnGoal")),
		"GB": safe_int_str(p.get("groundBalls")),
	}


def map_goalie(p: dict) -> dict:
	"""Map a goalie playerStats entry to the standard output format."""
	first = p.get("firstName") or ""
	last = p.get("lastName") or ""
	name = f"{first} {last}".strip().upper()
	goalie = p.get("goalie") or {}
	return {
		"NO": safe_str(p.get("number") or ""),
		"Name": name,
		"POS": safe_str(p.get("position") or "GK"),
		"GA": safe_int_str(goalie.get("goalsAllowed") if isinstance(goalie, dict) else None),
		"Saves": safe_int_str(goalie.get("saves") if isinstance(goalie, dict) else None),
	}


def fetch_boxscore(game_id: str) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
	"""
	Fetch box score for a game.

	Returns (away_players, away_goalies, home_players, home_goalies).
	"""
	data = gql_get(
		"NCAA_GetGamecenterBoxscoreLacrosseById_web",
		BOXSCORE_HASH,
		{"contestId": game_id, "staticTestEnv": None},
	)
	bs = (data.get("data") or {}).get("boxscore") or {}

	# Build teamId → isHome map from bs.teams
	team_home_map: dict[str, bool] = {}
	for t in (bs.get("teams") or []):
		team_home_map[str(t.get("teamId", ""))] = bool(t.get("isHome"))

	away_players: list[dict] = []
	away_goalies: list[dict] = []
	home_players: list[dict] = []
	home_goalies: list[dict] = []

	for tb in (bs.get("teamBoxscore") or []):
		is_home = team_home_map.get(str(tb.get("teamId", "")), False)
		players: list[dict] = []
		goalies: list[dict] = []

		for p in (tb.get("playerStats") or []):
			if p.get("goalie"):
				goalies.append(map_goalie(p))
			else:
				players.append(map_player(p))

		if is_home:
			home_players = players
			home_goalies = goalies
		else:
			away_players = players
			away_goalies = goalies

	return away_players, away_goalies, home_players, home_goalies


def fetch_pbp(game_id: str) -> list[dict]:
	"""
	Fetch play-by-play for a game.

	Returns a list of play dicts: {quarter, time, score, home_event, away_event}.
	Play text is placed in home_event or away_event based on which team the play
	belongs to; score holds the running 'visitorScore-homeScore' string on scored plays.
	"""
	data = gql_get(
		"NCAA_GetGamecenterPbpGenericById_web",
		PBP_HASH,
		{"contestId": game_id, "staticTestEnv": None},
	)
	pbp = (data.get("data") or {}).get("playbyplay") or {}

	# Build teamId → isHome map
	team_home_map: dict[str, bool] = {}
	for t in (pbp.get("teams") or []):
		team_home_map[str(t.get("teamId", ""))] = bool(t.get("isHome"))

	plays: list[dict] = []

	for period in (pbp.get("periods") or []):
		quarter = period.get("periodNumber") or 1

		for entry in (period.get("playbyplayStats") or []):
			clock = entry.get("clock") or ""
			entry_team_id = str(entry.get("teamId") or "")
			is_home = team_home_map.get(entry_team_id)

			for play in (entry.get("plays") or []):
				play_text = play.get("playText") or ""
				play_clock = play.get("clock") or clock

				home_score = play.get("homeScore")
				visitor_score = play.get("visitorScore")
				score_str = (
					f"{visitor_score}-{home_score}"
					if home_score is not None and visitor_score is not None
					else ""
				)

				home_event = ""
				away_event = ""
				if is_home is True:
					home_event = play_text
				elif is_home is False:
					away_event = play_text
				else:
					home_event = play_text

				plays.append({
					"quarter": quarter,
					"time": play_clock,
					"score": score_str,
					"home_event": home_event,
					"away_event": away_event,
				})

	return plays


def fetch_game(game_id: str, ncaa_dir: Path, between_requests: float) -> None:
	"""Fetch and save all data files for a single game."""
	info = fetch_game_info(game_id)
	time.sleep(between_requests)

	away_players, away_goalies, home_players, home_goalies = fetch_boxscore(game_id)
	player_stats = {
		"away": {"players": away_players, "goalies": away_goalies},
		"home": {"players": home_players, "goalies": home_goalies},
	}
	time.sleep(between_requests)

	plays = fetch_pbp(game_id)

	with open(ncaa_dir / f"game_{game_id}_info.json", "w", encoding="utf-8") as f:
		json.dump(info, f, indent=2)
	with open(ncaa_dir / f"game_{game_id}_player_stats.json", "w", encoding="utf-8") as f:
		json.dump(player_stats, f, indent=2)
	with open(ncaa_dir / f"game_{game_id}_plays.json", "w", encoding="utf-8") as f:
		json.dump(plays, f, indent=2)


def save_failed(ncaa_dir: Path, failed: list[dict]) -> None:
	"""Append new failures to failed_games.json."""
	failed_path = ncaa_dir / "failed_games.json"
	existing: list[dict] = []
	if failed_path.exists():
		with open(failed_path, "r") as f:
			existing = json.load(f)
	existing_ids = {str(e["gameID"]) for e in existing}
	merged = existing + [e for e in failed if str(e["gameID"]) not in existing_ids]
	with open(failed_path, "w") as f:
		json.dump(merged, f, indent=2)


def main() -> None:
	parser = argparse.ArgumentParser(description="Fetch NCAA game data via GraphQL API")
	parser.add_argument("--season", default="2026", help="Season year (default: 2026)")
	parser.add_argument("--division", type=int, default=1, choices=[1, 2, 3])
	parser.add_argument("--end-date", metavar="MM/DD/YYYY", help="Skip games after this date")
	parser.add_argument(
		"--force-games", metavar="ID1,ID2,...",
		help="Delete existing files and re-fetch these game IDs",
	)
	parser.add_argument("--dry-run", action="store_true", help="List games without fetching")
	parser.add_argument(
		"--include-scheduled", action="store_true",
		help="Also fetch game_info for non-final games (status != 'final')",
	)
	args = parser.parse_args()

	config = load_config()
	rl = config.get("browser_rate_limiting", {})
	between_games = rl.get("between_games", 1)

	games = load_game_ids(args.season, args.division)
	ncaa_dir = get_season_ncaa_dir(args.season, args.division)
	failed_ids = load_failed_ids(ncaa_dir)

	end_date = None
	if args.end_date:
		end_date = datetime.datetime.strptime(args.end_date, "%m/%d/%Y")

	force_ids: set[str] = set()
	if args.force_games:
		force_ids = {gid.strip() for gid in args.force_games.split(",")}
		for gid in force_ids:
			delete_game_files(gid, ncaa_dir)
		print(f"Force-fetching {len(force_ids)} games: {', '.join(sorted(force_ids))}")

	to_fetch: list[str] = []
	to_fetch_info_only: list[str] = []
	for g in games:
		gid = str(g.get("ncaaGameId", g.get("gameID", "")))
		if not gid:
			continue
		game_date_str = g.get("date", "")
		is_final = g.get("status", "") == "final"

		if gid in force_ids:
			to_fetch.append(gid)
			continue
		if gid in failed_ids:
			continue
		if end_date and game_date_str:
			try:
				if datetime.datetime.strptime(game_date_str, "%m/%d/%Y") > end_date:
					continue
			except ValueError:
				pass
		if is_final:
			if not game_files_exist(gid, ncaa_dir):
				to_fetch.append(gid)
		elif args.include_scheduled and not game_info_exists(gid, ncaa_dir):
			to_fetch_info_only.append(gid)

	total_queued = len(to_fetch) + len(to_fetch_info_only)
	print(f"{total_queued}/{len(games)} games to fetch for {args.season} D{args.division}"
		  f" ({len(to_fetch)} full, {len(to_fetch_info_only)} info-only)")

	if args.dry_run:
		for gid in to_fetch:
			print(f"  would fetch (full): {gid}")
		for gid in to_fetch_info_only:
			print(f"  would fetch (info-only): {gid}")
		return

	if not to_fetch and not to_fetch_info_only:
		print("Nothing to fetch")
		return

	failed: list[dict] = []
	all_jobs = [(gid, False) for gid in to_fetch] + [(gid, True) for gid in to_fetch_info_only]
	total = len(all_jobs)
	for i, (gid, info_only) in enumerate(all_jobs, 1):
		label = "info-only" if info_only else "full"
		print(f"[{i}/{total}] game {gid} — fetching ({label})...")
		try:
			if info_only:
				fetch_game_info_only(gid, ncaa_dir)
			else:
				fetch_game(gid, ncaa_dir, between_requests=0.5)
			print(f"[{i}/{total}] game {gid} — done")
		except Exception as e:
			print(f"[{i}/{total}] game {gid} — FAILED: {e}", file=sys.stderr)
			failed.append({"gameID": gid, "error": str(e)})

		if i < total:
			time.sleep(between_games)

	if failed:
		save_failed(ncaa_dir, failed)
		print(f"\n{len(failed)} games failed — see {ncaa_dir / 'failed_games.json'}")

	succeeded = total - len(failed)
	print(f"\nComplete: {succeeded} fetched, {len(failed)} failed")


if __name__ == "__main__":
	main()

#!/usr/bin/env python3
"""
Discover game IDs from NCAA scoreboard via sdataprod.ncaa.com GraphQL API.

No browser required — uses persisted GraphQL GET queries directly.

Usage:
	python3 scripts/utils/get_game_ids_ncaa.py --season 2026
	python3 scripts/utils/get_game_ids_ncaa.py --season 2026 --start-date 02/07/2026 --end-date 02/07/2026
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.path_helpers import get_season_ncaa_dir

API_BASE = "https://sdataprod.ncaa.com/"
SCOREBOARD_HASH = "7287cda610a9326931931080cb3a604828febe6fe3c9016a7e4a36db99efdb7c"
HEADERS = {
	"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
	"Referer": "https://www.ncaa.com/",
	"Accept": "*/*",
}


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


def to_score(value) -> int | None:
	"""Safely convert score value to int."""
	if value is None:
		return None
	try:
		return int(value)
	except (ValueError, TypeError):
		return None


def fetch_games_for_date(date_str: str, season_year: int, division: int) -> list[dict]:
	"""Fetch game summaries for a single date from the NCAA scoreboard API."""
	variables = {
		"sportCode": "MLA",
		"division": division,
		"seasonYear": season_year,
		"contestDate": date_str,
		"week": None,
	}
	try:
		data = gql_get("GetContests_web", SCOREBOARD_HASH, variables)
	except RuntimeError as e:
		print(f"  Warning: API error on {date_str}: {e}")
		return []

	contests = ((data.get("data") or {}).get("contests")) or []
	games = []
	for contest in contests:
		contest_id = str(contest.get("contestId", ""))
		if not contest_id:
			continue

		teams = contest.get("teams") or []
		home_team = next((t for t in teams if t.get("isHome")), None)
		away_team = next((t for t in teams if not t.get("isHome")), None)
		if not home_team or not away_team:
			continue

		games.append({
			"ncaaGameId": contest_id,
			"date": date_str,
			"homeTeam": home_team.get("nameShort", ""),
			"awayTeam": away_team.get("nameShort", ""),
			"homeScore": to_score(home_team.get("score")),
			"awayScore": to_score(away_team.get("score")),
			"status": contest.get("statusCodeDisplay", ""),
		})
	return games


def main() -> None:
	parser = argparse.ArgumentParser(description="Discover NCAA game IDs via GraphQL API")
	parser.add_argument("--season", required=True, help="Season year (e.g. 2026)")
	parser.add_argument("--division", type=int, default=1, help="Division (default: 1)")
	parser.add_argument("--start-date", metavar="MM/DD/YYYY", help="Start date")
	parser.add_argument("--end-date", metavar="MM/DD/YYYY", help="End date")
	parser.add_argument("--output", default="game_ids_ncaa.json", help="Output filename")
	args = parser.parse_args()

	config = load_config()
	date_ranges = config.get("date_ranges", {})
	start_str = args.start_date or date_ranges.get("start_date", "01/15/2026")
	end_str = args.end_date or date_ranges.get("end_date", "06/01/2026")
	start = datetime.strptime(start_str, "%m/%d/%Y")
	end = datetime.strptime(end_str, "%m/%d/%Y")

	# NCAA convention: seasonYear = year the academic season starts (e.g. 2025 for 2025-26)
	season_year = int(args.season) - 1

	all_games: list[dict] = []
	seen_ids: set[str] = set()
	daily_counts: list[dict] = []

	date = start
	while date <= end:
		date_str = date.strftime("%m/%d/%Y")
		games = fetch_games_for_date(date_str, season_year, args.division)

		new_count = 0
		for g in games:
			gid = g.get("ncaaGameId", "")
			if gid and gid not in seen_ids:
				seen_ids.add(gid)
				all_games.append(g)
				new_count += 1

		daily_counts.append({"date": date_str, "game_count": new_count})
		print(f"{new_count} games on {date_str}")
		date += timedelta(days=1)

	seen_final: dict[str, dict] = {}
	for g in all_games:
		gid = g.get("ncaaGameId", "")
		if gid and gid not in seen_final:
			seen_final[gid] = g
	all_games = list(seen_final.values())

	ncaa_dir = get_season_ncaa_dir(args.season, args.division)
	output_path = ncaa_dir / args.output
	with open(output_path, "w") as f:
		json.dump(all_games, f, indent=2)

	counts_path = ncaa_dir / args.output.replace(".json", "_daily_counts.json")
	with open(counts_path, "w") as f:
		json.dump(daily_counts, f, indent=2)

	print(f"\nSaved {len(all_games)} unique games to {output_path}")


if __name__ == "__main__":
	main()

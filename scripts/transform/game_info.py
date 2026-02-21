import datetime
import re
from .canonical import CanonicalGame

MONTH_NAMES = {
	"january": 1, "february": 2, "march": 3, "april": 4,
	"may": 5, "june": 6, "july": 7, "august": 8,
	"september": 9, "october": 10, "november": 11, "december": 12,
}


def _parse_date(date_str: str) -> datetime.date | None:
	"""Parse MM/DD/YYYY, YYYY-MM-DD, or 'Month Dth YYYY' formats."""
	if not date_str:
		return None
	for fmt in ["%m/%d/%Y", "%Y-%m-%d"]:
		try:
			return datetime.datetime.strptime(date_str, fmt).date()
		except ValueError:
			pass
	m = re.match(r"(\w+)\s+(\d+)(?:st|nd|rd|th)\s+(\d{4})", date_str)
	if m:
		month_num = MONTH_NAMES.get(m.group(1).lower())
		if month_num:
			try:
				return datetime.date(int(m.group(3)), month_num, int(m.group(2)))
			except ValueError:
				pass
	return None


def normalize_game_info(raw: dict, source: str, contest_date: str | None = None) -> CanonicalGame:
	"""Normalize raw game info to CanonicalGame.

	For ncaa_com: prefers contest_date (scoreboard MM/DD/YYYY) over raw gameDate.
	For stats_ncaa: reads gameDate or date field directly.
	"""
	if source == "ncaa_com":
		date_str = contest_date or raw.get("gameDate") or ""
		home_score = raw.get("homeScore")
		away_score = raw.get("awayScore")
		home_name = raw.get("homeTeam", "")
		away_name = raw.get("awayTeam", "")
	else:
		date_str = raw.get("gameDate") or raw.get("date") or ""
		home_score = raw.get("homeScore")
		away_score = raw.get("awayScore")
		home_name = raw.get("homeTeam", "")
		away_name = raw.get("awayTeam", "")

	try:
		home_int = int(home_score) if home_score is not None else None
	except (ValueError, TypeError):
		home_int = None
	try:
		away_int = int(away_score) if away_score is not None else None
	except (ValueError, TypeError):
		away_int = None

	return CanonicalGame(
		ncaa_game_id=str(raw.get("ncaaGameId", "")),
		game_date=_parse_date(date_str),
		home_team_name=home_name,
		away_team_name=away_name,
		home_score=home_int,
		away_score=away_int,
		location=raw.get("location") or None,
		source=source,
	)

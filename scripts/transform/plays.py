from .canonical import CanonicalPlay


def _parse_quarter(quarter_raw) -> int:
	if quarter_raw == "OT":
		return 5
	if isinstance(quarter_raw, str) and quarter_raw.endswith("OT"):
		try:
			return 4 + int(quarter_raw[:-2])
		except ValueError:
			return 5
	try:
		return int(quarter_raw) if quarter_raw else 0
	except (ValueError, TypeError):
		return 0


def _parse_time(time_str: str) -> int:
	if not time_str:
		return 0
	s = time_str.strip()
	if ":" in s:
		parts = s.split(":", 1)
		try:
			return int(parts[0]) * 60 + int(parts[1])
		except (ValueError, IndexError):
			return 0
	try:
		return int(s)
	except (ValueError, TypeError):
		return 0


def normalize_plays(raw: list[dict], source: str) -> list[CanonicalPlay]:
	"""Normalize raw play-by-play data to list of CanonicalPlay.

	Both ncaa_com and stats_ncaa share the same row structure:
	{quarter, time, score, home_event, away_event}
	Artifact rows (all fields "0" or empty) are skipped.
	"""
	plays: list[CanonicalPlay] = []
	for play in raw:
		home_event = play.get("home_event", "")
		score_field = play.get("score", "")
		away_event = play.get("away_event", "")
		# Skip artifact rows
		if (home_event in ("0", "") and score_field in ("0", "")
				and away_event in ("0", "")):
			continue
		quarter = _parse_quarter(play.get("quarter", ""))
		time_remaining = _parse_time(play.get("time", ""))
		plays.append(CanonicalPlay(
			quarter=quarter,
			time_remaining=time_remaining,
			home_event=home_event,
			away_event=away_event,
			score_str=score_field,
			raw_source=play,
		))
	return plays

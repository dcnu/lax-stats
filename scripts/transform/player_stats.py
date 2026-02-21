from .canonical import CanonicalPlayerStat


def _safe_int(value, default: int = 0) -> int:
	if value is None or value == "":
		return default
	try:
		return int(value)
	except (ValueError, TypeError):
		return default


def _parse_minutes(value) -> int | None:
	"""Convert MM:SS or integer seconds to int seconds."""
	if value is None or value == "":
		return None
	s = str(value).strip()
	if ":" in s:
		parts = s.split(":", 1)
		try:
			return int(parts[0]) * 60 + int(parts[1])
		except (ValueError, IndexError):
			return None
	try:
		return int(s)
	except (ValueError, TypeError):
		return None


def normalize_player_stats(raw: dict, source: str) -> list[CanonicalPlayerStat]:
	"""Normalize raw player stats to list of CanonicalPlayerStat.

	ncaa_com: raw has away/home keys with players[] and goalies[] lists.
	stats_ncaa: raw is a flat list with tableIndex field.
	"""
	stats: list[CanonicalPlayerStat] = []

	if source == "ncaa_com":
		for side in ("away", "home"):
			side_data = raw.get(side, {})
			for p in side_data.get("players", []):
				name = p.get("Name", "").strip().title()
				if not name:
					continue
				goals = _safe_int(p.get("G"))
				assists = _safe_int(p.get("A"))
				stats.append(CanonicalPlayerStat(
					name=name,
					jersey_number=str(p.get("NO", "")) or None,
					position=p.get("POS") or None,
					side=side,
					is_goalie=False,
					goals=goals,
					assists=assists,
					shots=_safe_int(p.get("SH")),
					shots_on_goal=_safe_int(p.get("SOG")),
					ground_balls=_safe_int(p.get("GB")),
					turnovers=0,
					caused_turnovers=0,
					faceoff_wins=0,
					faceoffs_taken=0,
					minutes_played=None,
					goalie_minutes=None,
					goals_allowed=0,
					saves=0,
				))
			for g in side_data.get("goalies", []):
				name = (g.get("Name") or g.get("Goalies") or "").strip().title()
				if not name:
					continue
				stats.append(CanonicalPlayerStat(
					name=name,
					jersey_number=str(g.get("NO", "")) or None,
					position=g.get("POS") or None,
					side=side,
					is_goalie=True,
					goals=0,
					assists=0,
					shots=0,
					shots_on_goal=0,
					ground_balls=0,
					turnovers=0,
					caused_turnovers=0,
					faceoff_wins=0,
					faceoffs_taken=0,
					minutes_played=None,
					goalie_minutes=_parse_minutes(g.get("MIN")),
					goals_allowed=_safe_int(g.get("GA")),
					saves=_safe_int(g.get("SAVES") or g.get("Saves")),
				))
	else:
		# stats_ncaa: flat list with tableIndex (even=away, odd=home)
		if isinstance(raw, list):
			entries = raw
		else:
			entries = []
		for p in entries:
			if "playerId" not in p or "name" not in p:
				continue
			table_idx = p.get("tableIndex")
			side = "away" if table_idx is not None and table_idx % 2 == 0 else "home"
			is_goalie = "G Min" in p
			name = p.get("name", "").strip()
			if not name:
				continue
			if is_goalie:
				stats.append(CanonicalPlayerStat(
					name=name,
					jersey_number=str(p.get("jersey", "")) or None,
					position=p.get("position") or None,
					side=side,
					is_goalie=True,
					goals=0, assists=0, shots=0, shots_on_goal=0,
					ground_balls=0, turnovers=0, caused_turnovers=0,
					faceoff_wins=0, faceoffs_taken=0,
					minutes_played=None,
					goalie_minutes=_parse_minutes(p.get("G Min")),
					goals_allowed=_safe_int(p.get("Goals Allowed")),
					saves=_safe_int(p.get("Saves")),
				))
			else:
				goals = _safe_int(p.get("Goals"))
				assists = _safe_int(p.get("Assists"))
				stats.append(CanonicalPlayerStat(
					name=name,
					jersey_number=str(p.get("jersey", "")) or None,
					position=p.get("position") or None,
					side=side,
					is_goalie=False,
					goals=goals,
					assists=assists,
					shots=_safe_int(p.get("Shots")),
					shots_on_goal=_safe_int(p.get("SOG")),
					ground_balls=_safe_int(p.get("GB")),
					turnovers=_safe_int(p.get("TO")),
					caused_turnovers=_safe_int(p.get("CT")),
					faceoff_wins=_safe_int(p.get("FO_Won")),
					faceoffs_taken=_safe_int(p.get("FOs_Taken")),
					minutes_played=_parse_minutes(p.get("Min")),
					goalie_minutes=None,
					goals_allowed=0,
					saves=0,
				))
	return stats

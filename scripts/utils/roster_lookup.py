#!/usr/bin/env python3
"""
Roster lookup utilities for player-team assignment.

Provides player → team mapping from roster files, which is the source of truth
for determining which team a player belongs to in game statistics.

The roster file structure is:
[
  {
    "teamID": "593904",
    "players": [
      { "playerID": "8764306", "name": "Jacob Arato", "teamID": "593904", ... }
    ]
  },
  ...
]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.path_helpers import get_season_raw_dir


def load_roster_mapping(season_id: str, division: int, base_dir: str = "data") -> dict[int, str]:
	"""
	Load playerID → teamID mapping from roster file.

	Args:
		season_id: Season ID (year as string)
		division: NCAA division (1, 2, or 3)
		base_dir: Base data directory

	Returns:
		Dictionary mapping playerID (int) to teamID (str)
	"""
	raw_dir = get_season_raw_dir(season_id, division, base_dir)
	roster_path = raw_dir / "rosters.json"

	if not roster_path.exists():
		print(f"Warning: Roster file not found at {roster_path}", file=sys.stderr)
		return {}

	with open(roster_path, "r", encoding="utf-8") as f:
		rosters = json.load(f)

	mapping = {}
	for team in rosters:
		team_id = str(team.get("teamID", ""))
		players = team.get("players", [])

		for player in players:
			player_id = player.get("playerID")
			if player_id:
				# Convert to int for consistent lookup
				try:
					mapping[int(player_id)] = team_id
				except (ValueError, TypeError):
					continue

	return mapping


def get_player_team(
	player_id: int,
	roster_map: dict[int, str],
	home_team_id: str,
	away_team_id: str,
) -> str | None:
	"""
	Determine which team (home or away) a player belongs to for a game.

	Args:
		player_id: Player ID to look up
		roster_map: playerID → teamID mapping from load_roster_mapping()
		home_team_id: Home team ID for the game
		away_team_id: Away team ID for the game

	Returns:
		team_id if player is on home or away team, None if not found
	"""
	team_id = roster_map.get(player_id)

	if team_id is None:
		return None

	if team_id == home_team_id:
		return home_team_id
	elif team_id == away_team_id:
		return away_team_id
	else:
		# Player exists in roster but not on either team in this game
		return None


# Cache for roster mappings to avoid re-reading files
_roster_cache: dict[tuple[str, int], dict[int, str]] = {}


def get_roster_mapping_cached(season_id: str, division: int, base_dir: str = "data") -> dict[int, str]:
	"""
	Get roster mapping with caching.

	Args:
		season_id: Season ID (year as string)
		division: NCAA division (1, 2, or 3)
		base_dir: Base data directory

	Returns:
		Dictionary mapping playerID (int) to teamID (str)
	"""
	cache_key = (season_id, division)

	if cache_key not in _roster_cache:
		_roster_cache[cache_key] = load_roster_mapping(season_id, division, base_dir)

	return _roster_cache[cache_key]


def clear_roster_cache():
	"""Clear the roster mapping cache."""
	_roster_cache.clear()

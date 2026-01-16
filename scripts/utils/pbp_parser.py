#!/usr/bin/env python3
"""
Play-by-play parser for extracting player statistics.

Parses game_*_plays.json files to extract goals, assists, saves,
ground balls, turnovers, caused turnovers, and faceoff wins.

Used for QC validation and filling missing player_stats data.
"""

import re
from collections import defaultdict


# Regex patterns for stat extraction
# Names can be "First Last" or "Last, First" format
# Patterns capture up to the next keyword/delimiter
PATTERNS = {
	# GOAL by BRY Jack Lonsinger (FIRST GOAL), goal number 18 for season.
	# GOAL by BING Wilson, Flynn, Assist by Sharkey, Nolan.
	# Capture name until (, Assist | ( | , goal | .)
	"goal": re.compile(r"GOAL by (\w+) ([^(]+?)(?:, Assist|\(|, goal|\.)"),
	"assist": re.compile(r"Assist by ([^(,\.]+(?:, [^(,\.]+)?)"),

	# Shot by BING Girolamo, Andrew, SAVE Scott Einarson
	# Shot by BING Ferris, Liam WIDE.
	# Capture name until (, SAVE | WIDE | HIGH | BLOCKED | .)
	"shot": re.compile(r"Shot by (\w+) ([^,]+(?:, [A-Z][a-z]+)?)(?:,? (?:SAVE|WIDE|HIGH|BLOCKED)|\.)"),
	"save": re.compile(r"SAVE ([A-Z][a-z]+(?: [A-Z][a-z]+)+)"),

	# Ground ball pickup by BING Sharkey, Nolan.
	"ground_ball": re.compile(r"Ground ball pickup by (\w+) ([^.]+(?:, [A-Z][a-z]+)?)\."),

	# Turnover by BRY Zac Amend.
	# Turnover by BING Wilson, Flynn (caused by Drew Lucas).
	"turnover": re.compile(r"Turnover by (\w+) ([^(.]+(?:, [A-Z][a-z]+)?)(?:\(|\.|\s*$)"),
	"caused_turnover": re.compile(r"caused by ([^)]+)"),

	# Faceoff Wilson, Flynn vs Jj Murphy won by BING
	"faceoff_won": re.compile(r"won by (\w+)"),
	"faceoff_players": re.compile(r"Faceoff ([^v]+) vs ([^w]+) won"),
}


def normalize_name(name: str) -> str:
	"""Normalize player name for matching."""
	name = name.strip()
	# Remove trailing periods
	name = name.rstrip(".")
	# Handle "Last, First" format -> "First Last"
	if ", " in name:
		parts = name.split(", ", 1)
		name = f"{parts[1]} {parts[0]}"
	return name.strip()


def parse_event(event_text: str, team_abbrev: str) -> dict:
	"""
	Parse a single play-by-play event and extract stats.

	Args:
		event_text: The event description text
		team_abbrev: Team abbreviation (e.g., 'BRY', 'BING')

	Returns:
		Dict of {player_name: {stat_type: count}}
	"""
	stats = defaultdict(lambda: defaultdict(int))

	if not event_text:
		return stats

	# Goals
	goal_match = PATTERNS["goal"].search(event_text)
	if goal_match:
		team, player = goal_match.groups()
		player = normalize_name(player)
		stats[player]["goals"] += 1
		stats[player]["team"] = team

		# Check for assist
		assist_match = PATTERNS["assist"].search(event_text)
		if assist_match:
			assister = normalize_name(assist_match.group(1))
			stats[assister]["assists"] += 1
			stats[assister]["team"] = team

	# Shots and saves
	shot_match = PATTERNS["shot"].search(event_text)
	if shot_match:
		team, player = shot_match.groups()
		player = normalize_name(player)
		stats[player]["shots"] += 1
		stats[player]["team"] = team

		# Check for save (shot on goal)
		save_match = PATTERNS["save"].search(event_text)
		if save_match:
			stats[player]["shots_on_goal"] += 1
			goalie = normalize_name(save_match.group(1))
			stats[goalie]["saves"] += 1
			# Goalie is on opposite team
		elif "WIDE" not in event_text and "HIGH" not in event_text and "BLOCKED" not in event_text:
			# If not saved and not wide/high/blocked, it's a goal (but goal is separate event)
			pass

	# Ground balls
	gb_match = PATTERNS["ground_ball"].search(event_text)
	if gb_match:
		team, player = gb_match.groups()
		player = normalize_name(player)
		stats[player]["ground_balls"] += 1
		stats[player]["team"] = team

	# Turnovers
	to_match = PATTERNS["turnover"].search(event_text)
	if to_match:
		team, player = to_match.groups()
		player = normalize_name(player)
		stats[player]["turnovers"] += 1
		stats[player]["team"] = team

		# Caused turnover
		ct_match = PATTERNS["caused_turnover"].search(event_text)
		if ct_match:
			defender = normalize_name(ct_match.group(1))
			stats[defender]["caused_turnovers"] += 1
			# Defender is on opposite team

	# Faceoffs
	if "Faceoff" in event_text and "won by" in event_text:
		fo_won_match = PATTERNS["faceoff_won"].search(event_text)
		fo_players_match = PATTERNS["faceoff_players"].search(event_text)
		if fo_won_match and fo_players_match:
			winning_team = fo_won_match.group(1)
			player1 = normalize_name(fo_players_match.group(1))
			player2 = normalize_name(fo_players_match.group(2))

			# Both players took the faceoff
			stats[player1]["faceoffs_taken"] += 1
			stats[player2]["faceoffs_taken"] += 1

			# Winner gets the win
			# We need to determine which player won based on team
			# This requires context from the event (home_event vs away_event)
			stats[player1]["faceoff_team_context"] = "first"
			stats[player2]["faceoff_team_context"] = "second"
			stats[player1]["faceoff_winning_team"] = winning_team
			stats[player2]["faceoff_winning_team"] = winning_team

	return stats


def detect_column_swap(plays_data: list, expected_home_goals: int, expected_away_goals: int) -> bool:
	"""
	Detect if PBP columns are swapped compared to game info.

	Some NCAA games have home_event/away_event columns reversed.
	Compare goal counts to expected final score to detect this.

	Returns True if columns appear to be swapped.
	"""
	home_col_goals = sum(1 for p in plays_data if "GOAL by" in p.get("home_event", ""))
	away_col_goals = sum(1 for p in plays_data if "GOAL by" in p.get("away_event", ""))

	# Check if swapped matches better
	normal_diff = abs(home_col_goals - expected_home_goals) + abs(away_col_goals - expected_away_goals)
	swapped_diff = abs(home_col_goals - expected_away_goals) + abs(away_col_goals - expected_home_goals)

	return swapped_diff < normal_diff


def parse_plays(plays_data: list, home_team_id: str, away_team_id: str,
				expected_home_goals: int = None, expected_away_goals: int = None) -> dict:
	"""
	Extract player stats from play-by-play events.

	Args:
		plays_data: List of play events from game_*_plays.json
		home_team_id: Home team ID (for assigning team_id to players)
		away_team_id: Away team ID
		expected_home_goals: Expected home team goals (for column swap detection)
		expected_away_goals: Expected away team goals (for column swap detection)

	Returns:
		Dict of {(player_name, team_id): {stat_type: count}}
	"""
	# Detect if columns are swapped
	swap_columns = False
	if expected_home_goals is not None and expected_away_goals is not None:
		swap_columns = detect_column_swap(plays_data, expected_home_goals, expected_away_goals)
		if swap_columns:
			# Swap the team IDs to match the actual column content
			home_team_id, away_team_id = away_team_id, home_team_id

	player_stats = defaultdict(lambda: {
		"goals": 0,
		"assists": 0,
		"shots": 0,
		"shots_on_goal": 0,
		"ground_balls": 0,
		"turnovers": 0,
		"caused_turnovers": 0,
		"faceoff_wins": 0,
		"faceoffs_taken": 0,
		"saves": 0,
	})

	for play in plays_data:
		home_event = play.get("home_event", "")
		away_event = play.get("away_event", "")

		# Process home column events (maps to home_team_id after any swap)
		if home_event:
			event_stats = parse_event(home_event, "HOME")
			for player, stats in event_stats.items():
				team_id = home_team_id

				# Special case: saves - goalie is on opposite team
				if "saves" in stats and stats["saves"] > 0 and "goals" not in stats:
					if "Shot by" in home_event:
						team_id = away_team_id

				key = (player, team_id)
				for stat_type, value in stats.items():
					if stat_type not in ("team", "faceoff_team_context", "faceoff_winning_team"):
						player_stats[key][stat_type] += value

		# Process away column events (maps to away_team_id after any swap)
		if away_event:
			event_stats = parse_event(away_event, "AWAY")
			for player, stats in event_stats.items():
				team_id = away_team_id

				# Special case: saves - goalie is on opposite team
				if "saves" in stats and stats["saves"] > 0 and "goals" not in stats:
					if "Shot by" in away_event:
						team_id = home_team_id

				key = (player, team_id)
				for stat_type, value in stats.items():
					if stat_type not in ("team", "faceoff_team_context", "faceoff_winning_team"):
						player_stats[key][stat_type] += value

	return dict(player_stats)


def get_goals_from_plays(plays_data: list) -> tuple[int, int]:
	"""
	Count total goals for home and away teams from play-by-play.

	Args:
		plays_data: List of play events

	Returns:
		Tuple of (home_goals, away_goals)
	"""
	home_goals = 0
	away_goals = 0

	for play in plays_data:
		home_event = play.get("home_event", "")
		away_event = play.get("away_event", "")

		if "GOAL by" in home_event:
			home_goals += 1
		if "GOAL by" in away_event:
			away_goals += 1

	return home_goals, away_goals


def match_player_to_roster(name: str, roster: dict[int, dict]) -> int | None:
	"""
	Match a play-by-play player name to a roster playerID.

	Args:
		name: Player name from play-by-play (e.g., "Jack Lonsinger")
		roster: Dict of {playerID: {name, teamID, ...}}

	Returns:
		playerID if matched, None otherwise
	"""
	name_lower = name.lower().strip()

	for player_id, player_data in roster.items():
		roster_name = player_data.get("name", "").lower()

		# Exact match
		if name_lower == roster_name:
			return player_id

		# Handle "First Last" vs "Last, First"
		name_parts = name_lower.split()
		roster_parts = roster_name.split()

		if len(name_parts) >= 2 and len(roster_parts) >= 2:
			# Try "First Last" == "First Last"
			if name_parts == roster_parts:
				return player_id

			# Try reversed order
			if name_parts[0] == roster_parts[-1] and name_parts[-1] == roster_parts[0]:
				return player_id

			# Try last name match with first name initial
			if name_parts[-1] == roster_parts[-1]:
				if name_parts[0][0] == roster_parts[0][0]:
					return player_id

			# Fuzzy match: check if last names are similar (handle typos)
			# e.g., "Rusell" vs "Russell"
			if len(name_parts[-1]) >= 4 and len(roster_parts[-1]) >= 4:
				# Check if last names share first 3 chars and first name initial matches
				if name_parts[-1][:3] == roster_parts[-1][:3]:
					if name_parts[0][0] == roster_parts[0][0]:
						# Additional check: similar length (within 2 chars)
						if abs(len(name_parts[-1]) - len(roster_parts[-1])) <= 2:
							return player_id

	# Second pass: try single-name matching (just last name)
	if len(name_lower.split()) == 1:
		for player_id, player_data in roster.items():
			roster_name = player_data.get("name", "").lower()
			roster_parts = roster_name.split()
			if roster_parts and name_lower == roster_parts[-1]:
				return player_id

	return None

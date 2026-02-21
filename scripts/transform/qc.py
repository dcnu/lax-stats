import datetime
from .canonical import CanonicalGame, CanonicalPlayerStat, CanonicalPlay, QCReport

SEASON_START_MONTH = 1  # January
SEASON_END_MONTH = 6    # June


def validate_game_package(
	game: CanonicalGame,
	stats: list[CanonicalPlayerStat],
	plays: list[CanonicalPlay],
	season_year: int,
	seen_keys: set[tuple],
) -> QCReport:
	"""Validate a game package and return a QCReport.

	seen_keys: mutable set of (date, home_team, away_team) tuples for dedup detection.
	Errors block loading; warnings are logged only.
	"""
	report = QCReport()

	# Error: missing team names
	if not game.home_team_name:
		report.errors.append("Missing home team name")
	if not game.away_team_name:
		report.errors.append("Missing away team name")

	# Error: box score goals vs game score mismatch
	if game.home_score is not None and stats:
		home_goals = sum(s.goals for s in stats if s.side == "home" and not s.is_goalie)
		away_goals = sum(s.goals for s in stats if s.side == "away" and not s.is_goalie)
		if home_goals != game.home_score:
			report.errors.append(
				f"Home score mismatch: game={game.home_score}, box={home_goals}"
			)
		if game.away_score is not None and away_goals != game.away_score:
			report.errors.append(
				f"Away score mismatch: game={game.away_score}, box={away_goals}"
			)

	# Warning: game_date is None
	if game.game_date is None:
		report.warnings.append("game_date is None (epoch conversion failed or missing)")

	# Warning: date out of season range
	if game.game_date is not None:
		if not (
			game.game_date.year == season_year
			and SEASON_START_MONTH <= game.game_date.month <= SEASON_END_MONTH
		):
			report.warnings.append(
				f"game_date {game.game_date} outside expected season range "
				f"(Jan–Jun {season_year})"
			)

	# Warning: blank player names > 15%
	if stats:
		blank = sum(1 for s in stats if not s.name)
		if blank / len(stats) > 0.15:
			report.warnings.append(
				f"Blank player names: {blank}/{len(stats)} ({blank/len(stats):.0%})"
			)

	# Warning: duplicate game key
	if game.game_date and game.home_team_name and game.away_team_name:
		key = (str(game.game_date), game.home_team_name.lower(), game.away_team_name.lower())
		if key in seen_keys:
			report.warnings.append(
				f"Duplicate game key: {key}"
			)
		else:
			seen_keys.add(key)

	# Warning: PBP final score mismatch
	if plays and game.home_score is not None and game.away_score is not None:
		last_score = ""
		for p in reversed(plays):
			if p.score_str and p.score_str not in ("0", ""):
				last_score = p.score_str
				break
		if last_score:
			# score_str is "away-home" format from ncaa.com
			parts = last_score.split("-", 1)
			if len(parts) == 2:
				try:
					pbp_away, pbp_home = int(parts[0]), int(parts[1])
					if pbp_home != game.home_score or pbp_away != game.away_score:
						report.warnings.append(
							f"PBP final score {last_score} != game score "
							f"{game.away_score}-{game.home_score}"
						)
				except ValueError:
					pass

	return report

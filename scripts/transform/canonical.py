import datetime
from dataclasses import dataclass, field


@dataclass
class CanonicalGame:
	ncaa_game_id: str
	game_date: datetime.date | None
	home_team_name: str
	away_team_name: str
	home_score: int | None
	away_score: int | None
	location: str | None
	source: str  # "ncaa_com" | "stats_ncaa"


@dataclass
class CanonicalPlayerStat:
	name: str
	jersey_number: str | None
	position: str | None
	side: str  # "home" | "away"
	is_goalie: bool
	goals: int
	assists: int
	shots: int
	shots_on_goal: int
	ground_balls: int
	turnovers: int
	caused_turnovers: int
	faceoff_wins: int
	faceoffs_taken: int
	minutes_played: int | None
	goalie_minutes: int | None
	goals_allowed: int
	saves: int


@dataclass
class CanonicalPlay:
	quarter: int
	time_remaining: int
	home_event: str
	away_event: str
	score_str: str
	raw_source: dict


@dataclass
class QCReport:
	errors: list[str] = field(default_factory=list)
	warnings: list[str] = field(default_factory=list)

	@property
	def ok(self) -> bool:
		return len(self.errors) == 0

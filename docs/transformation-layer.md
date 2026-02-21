# Transformation Layer

Source-agnostic normalization between fetching and loading. Each source (ncaa.com, stats.ncaa.org) produces different JSON shapes; the transform layer converts them into canonical dataclasses before database loading.

## Module Map

```
scripts/transform/
├── __init__.py        # Re-exports all public names
├── canonical.py       # Dataclass definitions
├── game_info.py       # normalize_game_info(raw, source, contest_date?) → CanonicalGame
├── player_stats.py    # normalize_player_stats(raw, source) → list[CanonicalPlayerStat]
├── plays.py           # normalize_plays(raw, source) → list[CanonicalPlay]
└── qc.py              # validate_game_package(game, stats, plays) → QCReport
```

## Canonical Types

### CanonicalGame

```python
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
```

### CanonicalPlayerStat

```python
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
```

### CanonicalPlay

```python
@dataclass
class CanonicalPlay:
	quarter: int
	time_remaining: int | None
	home_event: str
	away_event: str
	score_str: str
	raw_source: dict
```

### QCReport

```python
@dataclass
class QCReport:
	errors: list[str]
	warnings: list[str]

	@property
	def ok(self) -> bool:
		return len(self.errors) == 0
```

## Adding a New Source

1. Add a source identifier string (e.g. `"new_source"`).
2. In each `normalize_*` function, add an `elif source == "new_source"` branch that maps the raw JSON fields to the canonical dataclass.
3. Add source-specific QC checks in `qc.py` if needed.
4. The loader scripts (`scripts/loading/`) import from `scripts.transform` — no changes needed there as long as the canonical types are returned.

## Integration

Loaders already have `sys.path.insert(0, ...)` pointing at `scripts/`. Import from the transform package:

```python
from transform import normalize_game_info, CanonicalGame
```

The transform layer does not touch the database. It only converts raw JSON dicts into typed dataclasses that loaders consume.

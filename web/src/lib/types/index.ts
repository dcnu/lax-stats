export interface Season {
	id: string;
	division_id: number;
	is_current: boolean;
}

export interface Team {
	team_id: string;
	team_name: string;
	slug: string;
	logo_url: string | null;
	conference: string | null;
	wins: number;
	losses: number;
	games_played: number;
}

export interface TeamDetail {
	team_id: string;
	team_name: string;
	slug: string;
	logo_url: string | null;
	conference: string | null;
	season_id: string;
}

export interface Game {
	id: string;
	season_id: string;
	game_date: string;
	home_team_id: string;
	home_team_name: string;
	home_team_slug: string | null;
	away_team_id: string;
	away_team_name: string;
	away_team_slug: string | null;
	home_score: number | null;
	away_score: number | null;
	winning_team_id: string | null;
	losing_team_id: string | null;
	location: string | null;
	attendance: number | null;
	status: string;
	home_team_wins: number | null;
	home_team_losses: number | null;
	away_team_wins: number | null;
	away_team_losses: number | null;
}

export interface PlayerGameStats {
	id: string;
	game_id: string;
	season_id: string;
	team_id: string;
	player_id: number;
	player_name: string | null;
	team_name: string | null;
	opponent_id: string | null;
	jersey_number: number | null;
	position: string | null;
	minutes_played: number | null;
	goals: number;
	assists: number;
	points: number;
	shots: number;
	shots_on_goal: number;
	ground_balls: number;
	turnovers: number;
	caused_turnovers: number;
	faceoff_wins: number;
	faceoffs_taken: number;
	goalie_minutes: number | null;
	goals_allowed: number;
	saves: number;
	save_percentage: number | null;
	gaa: number | null;
	[key: string]: unknown;
}

export interface GamePlay {
	id: string;
	game_id: string;
	season_id: string;
	quarter: number;
	time_remaining: number;
	play_sequence: number;
	play_type: string;
	play_type_name?: string;
	category?: string;
	player_id: number | null;
	player_name: string | null;
	team_id: string | null;
	secondary_player_id: number | null;
	secondary_player_name: string | null;
	home_score: number | null;
	away_score: number | null;
	raw_description: string | null;
}

export interface PlayerSeasonStats {
	id: string;
	player_id: number;
	team_id: string;
	season_id: string;
	player_name: string | null;
	team_name: string | null;
	primary_position: string | null;
	games_played: number;
	goals: number;
	assists: number;
	points: number;
	shots: number;
	shots_on_goal: number;
	ground_balls: number;
	turnovers: number;
	caused_turnovers: number;
	faceoff_wins: number;
	faceoffs_taken: number;
	minutes_played: number;
	goalie_minutes: number;
	goals_allowed: number;
	saves: number;
	points_per_game: number | null;
	goals_per_game: number | null;
	shooting_pct: number | null;
	faceoff_pct: number | null;
	save_pct: number | null;
	[key: string]: unknown;
}

export interface Player {
	id: number;
	name: string;
	team_id: string | null;
	jersey_number: number | null;
	primary_position: string | null;
	hometown: string | null;
	high_school: string | null;
	season_count: number;
	first_season: string | null;
	last_season: string | null;
}

export interface PlayerSeason {
	id: string;
	player_id: number;
	team_id: string;
	season_id: string;
	jersey_number: number;
	primary_position: string | null;
	class_year: string | null;
}

export interface Ranking {
	id: string;
	team_id: string;
	season_id: string;
	division_id: number;
	team_name?: string;
	wins: number;
	losses: number;
	wp: number | null;
	owp: number | null;
	oowp: number | null;
	rpi: number | null;
	massey: number | null;
	massey_recency: number | null;
	projected_rpi_flat: number | null;
	projected_rpi_flat_low: number | null;
	projected_rpi_flat_high: number | null;
	projected_rpi_seeded: number | null;
	projected_rpi_seeded_low: number | null;
	projected_rpi_seeded_high: number | null;
	[key: string]: unknown;
}

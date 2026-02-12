import { NextResponse } from "next/server";
import { getSql, getCurrentSeason } from "@/lib/db";

interface ScorerRow {
	player_id: number;
	player_name: string;
	team_id: string;
	team_name: string;
	season_id: string;
	games_played: number;
	goals: number;
	assists: number;
	points: number;
	shots: number;
	shots_on_goal: number;
	ground_balls: number;
	turnovers: number;
	caused_turnovers: number;
	points_per_game: string;
}

export async function GET(request: Request) {
	const { searchParams } = new URL(request.url);
	const seasonId = searchParams.get("seasonId") || await getCurrentSeason();
	const limit = parseInt(searchParams.get("limit") || "50");

	try {
		const result = await getSql()<ScorerRow[]>`
			SELECT
				player_id,
				player_name,
				team_id,
				team_name,
				season_id,
				games_played,
				goals,
				assists,
				points,
				shots,
				shots_on_goal,
				ground_balls,
				turnovers,
				caused_turnovers,
				points_per_game
			FROM player_season_stats
			WHERE season_id = ${seasonId}
				AND player_name IS NOT NULL
			ORDER BY points DESC
			LIMIT ${limit}
		`;

		const data = result.map((row) => ({
			player_id: Number(row.player_id),
			player_name: row.player_name,
			team_id: row.team_id,
			team_name: row.team_name,
			season_id: row.season_id,
			games_played: Number(row.games_played),
			total_goals: Number(row.goals),
			total_assists: Number(row.assists),
			total_points: Number(row.points),
			total_shots: Number(row.shots),
			total_shots_on_goal: Number(row.shots_on_goal),
			total_ground_balls: Number(row.ground_balls),
			total_turnovers: Number(row.turnovers),
			total_caused_turnovers: Number(row.caused_turnovers),
			points_per_game: Number(row.points_per_game) || 0,
		}));

		return NextResponse.json(data);
	} catch (error) {
		console.error("Error fetching top scorers:", error);
		return NextResponse.json(
			{ message: "Failed to fetch top scorers" },
			{ status: 500 },
		);
	}
}

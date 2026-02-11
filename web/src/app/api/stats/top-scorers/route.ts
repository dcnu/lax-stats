import { NextResponse } from "next/server";
import { getSql, getCurrentSeason } from "@/lib/db";

interface ScorerRow {
	player_id: number;
	player_name: string;
	team_id: string;
	team_name: string;
	season_id: string;
	games_played: number;
	total_goals: number;
	total_assists: number;
	total_points: number;
	total_shots: number;
	total_shots_on_goal: number;
	total_ground_balls: number;
	total_turnovers: number;
	total_caused_turnovers: number;
}

export async function GET(request: Request) {
	const { searchParams } = new URL(request.url);
	const seasonId = searchParams.get("seasonId") || await getCurrentSeason();
	const limit = parseInt(searchParams.get("limit") || "50");

	try {
		const result = await getSql()<ScorerRow[]>`
			SELECT
				pgs.player_id,
				pgs.player_name,
				pgs.team_id,
				pgs.team_name,
				pgs.season_id,
				COUNT(DISTINCT pgs.game_id) as games_played,
				SUM(pgs.goals) as total_goals,
				SUM(pgs.assists) as total_assists,
				SUM(pgs.points) as total_points,
				SUM(pgs.shots) as total_shots,
				SUM(pgs.shots_on_goal) as total_shots_on_goal,
				SUM(pgs.ground_balls) as total_ground_balls,
				SUM(pgs.turnovers) as total_turnovers,
				SUM(pgs.caused_turnovers) as total_caused_turnovers
			FROM player_game_stats pgs
			WHERE pgs.season_id = ${seasonId}
				AND pgs.player_name IS NOT NULL
			GROUP BY pgs.player_id, pgs.player_name, pgs.team_id, pgs.team_name, pgs.season_id
			ORDER BY total_points DESC
			LIMIT ${limit}
		`;

		const data = result.map((row) => ({
			player_id: Number(row.player_id),
			player_name: row.player_name,
			team_id: row.team_id,
			team_name: row.team_name,
			season_id: row.season_id,
			games_played: Number(row.games_played),
			total_goals: Number(row.total_goals),
			total_assists: Number(row.total_assists),
			total_points: Number(row.total_points),
			total_shots: Number(row.total_shots),
			total_shots_on_goal: Number(row.total_shots_on_goal),
			total_ground_balls: Number(row.total_ground_balls),
			total_turnovers: Number(row.total_turnovers),
			total_caused_turnovers: Number(row.total_caused_turnovers),
			points_per_game:
				Number(row.games_played) > 0
					? Math.round((Number(row.total_points) / Number(row.games_played)) * 100) / 100
					: 0,
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

import { NextResponse } from "next/server";
import { getSql, getCurrentSeason } from "@/lib/db";

interface StandingsRow {
	team_id: string;
	team_name: string;
	wins: number;
	losses: number;
	ties: number;
	games_played: number;
	goals_for: number;
	goals_against: number;
	goal_diff: number;
	win_pct: string;
}

export async function GET(request: Request) {
	const { searchParams } = new URL(request.url);
	const seasonId = searchParams.get("seasonId") || await getCurrentSeason();

	try {
		const standings = await getSql()<StandingsRow[]>`
			SELECT
				team_id,
				team_name,
				wins,
				losses,
				ties,
				games_played,
				goals_for,
				goals_against,
				goal_diff,
				win_pct
			FROM team_season_stats
			WHERE season_id = ${seasonId} AND games_played > 0
			ORDER BY wins DESC
		`;

		const data = standings.map((row) => ({
			team_name: row.team_name,
			wins: Number(row.wins),
			losses: Number(row.losses),
			games_played: Number(row.games_played),
			win_pct: Number(row.win_pct) > 0
				? Number(row.win_pct).toFixed(3)
				: ".000",
			goals_for: Number(row.goals_for),
			goals_against: Number(row.goals_against),
			goal_diff: Number(row.goal_diff),
		}));

		return NextResponse.json(data);
	} catch (error) {
		console.error("Error fetching team standings:", error);
		return NextResponse.json(
			{ message: "Failed to fetch team standings" },
			{ status: 500 },
		);
	}
}

import { NextResponse } from "next/server";
import { getSql, getCurrentSeason } from "@/lib/db";

interface StandingsRow {
	team_id: string;
	team_name: string;
	wins: number;
	losses: number;
	goals_for: number;
	goals_against: number;
}

export async function GET(request: Request) {
	const { searchParams } = new URL(request.url);
	const seasonId = searchParams.get("seasonId") || await getCurrentSeason();

	try {
		const standings = await getSql()<StandingsRow[]>`
			WITH team_stats AS (
				SELECT
					home_team_id as team_id,
					COUNT(*) FILTER (WHERE home_score > away_score) as wins,
					COUNT(*) FILTER (WHERE home_score < away_score) as losses,
					SUM(home_score) as goals_for,
					SUM(away_score) as goals_against
				FROM games
				WHERE season_id = ${seasonId} AND status = 'final'
				GROUP BY home_team_id

				UNION ALL

				SELECT
					away_team_id as team_id,
					COUNT(*) FILTER (WHERE away_score > home_score) as wins,
					COUNT(*) FILTER (WHERE away_score < home_score) as losses,
					SUM(away_score) as goals_for,
					SUM(home_score) as goals_against
				FROM games
				WHERE season_id = ${seasonId} AND status = 'final'
				GROUP BY away_team_id
			)
			SELECT
				t.id as team_id,
				t.name as team_name,
				COALESCE(SUM(ts.wins), 0) as wins,
				COALESCE(SUM(ts.losses), 0) as losses,
				COALESCE(SUM(ts.goals_for), 0) as goals_for,
				COALESCE(SUM(ts.goals_against), 0) as goals_against
			FROM lookup_teams t
			LEFT JOIN team_stats ts ON t.id = ts.team_id
			GROUP BY t.id, t.name
			HAVING SUM(ts.wins) + SUM(ts.losses) > 0
			ORDER BY COALESCE(SUM(ts.wins), 0) DESC
		`;

		const data = standings.map((row) => {
			const wins = Number(row.wins);
			const losses = Number(row.losses);
			const gamesPlayed = wins + losses;
			const goalsFor = Number(row.goals_for);
			const goalsAgainst = Number(row.goals_against);

			return {
				team_name: row.team_name,
				wins,
				losses,
				games_played: gamesPlayed,
				win_pct: gamesPlayed > 0 ? (wins / gamesPlayed).toFixed(3) : ".000",
				goals_for: goalsFor,
				goals_against: goalsAgainst,
				goal_diff: goalsFor - goalsAgainst,
			};
		});

		return NextResponse.json(data);
	} catch (error) {
		console.error("Error fetching team standings:", error);
		return NextResponse.json(
			{ message: "Failed to fetch team standings" },
			{ status: 500 },
		);
	}
}

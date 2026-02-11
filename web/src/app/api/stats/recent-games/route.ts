import { NextResponse } from "next/server";
import { getSupabase, getCurrentSeason } from "@/lib/db";

export async function GET(request: Request) {
	const { searchParams } = new URL(request.url);
	const seasonId = searchParams.get("seasonId") || await getCurrentSeason();
	const limit = parseInt(searchParams.get("limit") || "30");

	const { data, error } = await getSupabase()
		.from("games")
		.select(
			"id, game_date, home_score, away_score, home_team_name, away_team_name, location, attendance",
		)
		.eq("season_id", seasonId)
		.eq("status", "final")
		.order("game_date", { ascending: false })
		.limit(limit);

	if (error) {
		console.error("Error fetching recent games:", error);
		return NextResponse.json(
			{ message: "Failed to fetch recent games" },
			{ status: 500 },
		);
	}

	const result = data.map((game) => ({
		id: game.id,
		date: game.game_date,
		home_team: game.home_team_name,
		home_score: game.home_score,
		away_team: game.away_team_name,
		away_score: game.away_score,
		location: game.location,
		attendance: game.attendance,
	}));

	return NextResponse.json(result);
}

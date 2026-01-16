import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export async function GET(request: Request) {
	const { searchParams } = new URL(request.url);
	const seasonId = searchParams.get("seasonId") || "2025";
	const limit = parseInt(searchParams.get("limit") || "30");

	try {
		const games = await prisma.game.findMany({
			where: {
				seasonId,
				status: "final",
			},
			include: {
				homeTeam: { select: { name: true } },
				awayTeam: { select: { name: true } },
			},
			orderBy: { gameDate: "desc" },
			take: limit,
		});

		const data = games.map((game: typeof games[number]) => ({
			id: game.id,
			date: game.gameDate.toISOString().split("T")[0],
			home_team: game.homeTeam.name,
			home_score: game.homeScore,
			away_team: game.awayTeam.name,
			away_score: game.awayScore,
			location: game.location,
			attendance: game.attendance,
		}));

		return NextResponse.json(data);
	} catch (error) {
		console.error("Error fetching recent games:", error);
		return NextResponse.json(
			{ message: "Failed to fetch recent games" },
			{ status: 500 }
		);
	}
}

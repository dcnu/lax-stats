import { NextRequest, NextResponse } from "next/server";
import { getSql } from "@/lib/db";

export async function GET(request: NextRequest) {
	const q = request.nextUrl.searchParams.get("q")?.trim();
	if (!q || q.length < 2) {
		return NextResponse.json({ players: [], teams: [] });
	}

	const sql = getSql();
	const pattern = `%${q}%`;

	const [players, teams] = await Promise.all([
		sql`
			SELECT DISTINCT ON (player_id, season_id)
				player_id, player_name, team_name, season_id
			FROM player_season_stats
			WHERE player_name ILIKE ${pattern}
			ORDER BY player_id, season_id DESC
			LIMIT 10
		`,
		sql`
			SELECT DISTINCT ON (team_id, season_id)
				team_id, team_name, season_id
			FROM team_seasons
			WHERE team_name ILIKE ${pattern}
			ORDER BY team_id, season_id DESC
			LIMIT 10
		`,
	]);

	return NextResponse.json({ players, teams });
}

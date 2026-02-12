import { getSql } from "@/lib/db";
import type { Ranking } from "@/lib/types";

export async function getRankings(
	seasonId: string,
	divisionId: number = 1,
): Promise<Ranking[]> {
	const sql = getSql();
	const rows = await sql`
		SELECT
			tsr.*,
			lt.name AS team_name
		FROM team_season_rankings tsr
		JOIN lookup_teams lt ON lt.id = tsr.team_id
		WHERE tsr.season_id = ${seasonId}
			AND tsr.division_id = ${divisionId}
		ORDER BY tsr.rpi DESC NULLS LAST
	`;
	return rows as unknown as Ranking[];
}

import { getSql } from "@/lib/db";
import type { Player, PlayerSeasonStats, PlayerGameStats } from "@/lib/types";

export async function getPlayerLeaderboard(
	seasonId: string,
): Promise<PlayerSeasonStats[]> {
	const sql = getSql();
	const rows = await sql`
		SELECT *
		FROM player_season_stats
		WHERE season_id = ${seasonId}
		ORDER BY points DESC
	`;
	return rows as unknown as PlayerSeasonStats[];
}

export async function getPlayerDetail(
	playerId: number,
): Promise<Player | null> {
	const sql = getSql();
	const rows = await sql`
		SELECT *
		FROM players
		WHERE id = ${playerId}
		LIMIT 1
	`;
	return (rows[0] as unknown as Player) || null;
}

export async function getPlayerSeasonStats(
	playerId: number,
): Promise<PlayerSeasonStats[]> {
	const sql = getSql();
	const rows = await sql`
		SELECT *
		FROM player_season_stats
		WHERE player_id = ${playerId}
		ORDER BY season_id DESC
	`;
	return rows as unknown as PlayerSeasonStats[];
}

export async function getPlayerGameLog(
	playerId: number,
	seasonId: string,
): Promise<(PlayerGameStats & { game_date: string; opponent_name: string })[]> {
	const sql = getSql();
	const rows = await sql`
		SELECT
			pgs.*,
			g.game_date,
			CASE
				WHEN pgs.team_id = g.home_team_id THEN g.away_team_name
				ELSE g.home_team_name
			END AS opponent_name
		FROM player_game_stats pgs
		JOIN games g ON g.id = pgs.game_id
		WHERE pgs.player_id = ${playerId} AND pgs.season_id = ${seasonId}
		ORDER BY g.game_date DESC
	`;
	return rows as unknown as (PlayerGameStats & { game_date: string; opponent_name: string })[];
}

import { getSql } from "@/lib/db";
import type { Game, PlayerGameStats, GamePlay } from "@/lib/types";

export async function getGamesForSeason(
	seasonId: string,
): Promise<Game[]> {
	const sql = getSql();
	const rows = await sql`
		SELECT *
		FROM games
		WHERE season_id = ${seasonId} AND status = 'final'
		ORDER BY game_date DESC
	`;
	return rows as unknown as Game[];
}

export async function getGameDetail(
	gameId: string,
): Promise<Game | null> {
	const sql = getSql();
	const rows = await sql`
		SELECT *
		FROM games
		WHERE id = ${gameId}
		LIMIT 1
	`;
	return (rows[0] as unknown as Game) || null;
}

export async function getGameBoxScore(
	gameId: string,
): Promise<PlayerGameStats[]> {
	const sql = getSql();
	const rows = await sql`
		SELECT *
		FROM player_game_stats
		WHERE game_id = ${gameId}
		ORDER BY team_id, position, points DESC
	`;
	return rows as unknown as PlayerGameStats[];
}

export async function getGamePlays(
	gameId: string,
	seasonId: string,
): Promise<GamePlay[]> {
	const sql = getSql();
	const rows = await sql`
		SELECT
			gp.*,
			lpt.name AS play_type_name,
			lpt.category
		FROM game_plays gp
		JOIN lookup_play_types lpt ON lpt.code = gp.play_type
		WHERE gp.game_id = ${gameId} AND gp.season_id = ${seasonId}
		ORDER BY gp.play_sequence
	`;
	return rows as unknown as GamePlay[];
}

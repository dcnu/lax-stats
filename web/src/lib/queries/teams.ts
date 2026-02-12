import { getSql } from "@/lib/db";
import type { Team, TeamDetail, Game, PlayerSeason, PlayerSeasonStats } from "@/lib/types";

export async function getTeamsForSeason(
	seasonId: string,
): Promise<Team[]> {
	const sql = getSql();
	const rows = await sql`
		SELECT
			ts.team_id,
			ts.team_name,
			ts.logo_url,
			ts.conference,
			COALESCE(tss.wins, 0) AS wins,
			COALESCE(tss.losses, 0) AS losses,
			COALESCE(tss.games_played, 0) AS games_played
		FROM team_seasons ts
		LEFT JOIN team_season_stats tss
			ON ts.team_id = tss.team_id AND ts.season_id = tss.season_id
		WHERE ts.season_id = ${seasonId}
		ORDER BY ts.team_name
	`;
	return rows as unknown as Team[];
}

export async function getTeamDetail(
	teamId: string,
	seasonId: string,
): Promise<TeamDetail | null> {
	const sql = getSql();
	const rows = await sql`
		SELECT team_id, team_name, logo_url, conference, season_id
		FROM team_seasons
		WHERE team_id = ${teamId} AND season_id = ${seasonId}
		LIMIT 1
	`;
	return (rows[0] as unknown as TeamDetail) || null;
}

export async function getTeamSchedule(
	teamId: string,
	seasonId: string,
): Promise<Game[]> {
	const sql = getSql();
	const rows = await sql`
		SELECT *
		FROM games
		WHERE (home_team_id = ${teamId} OR away_team_id = ${teamId})
			AND season_id = ${seasonId}
		ORDER BY game_date ASC
	`;
	return rows as unknown as Game[];
}

export async function getTeamRoster(
	teamId: string,
	seasonId: string,
): Promise<(PlayerSeason & { name: string; hometown: string | null; high_school: string | null })[]> {
	const sql = getSql();
	const rows = await sql`
		SELECT
			ps.*,
			p.name,
			p.hometown,
			p.high_school
		FROM player_seasons ps
		JOIN players p ON p.id = ps.player_id
		WHERE ps.team_id = ${teamId} AND ps.season_id = ${seasonId}
		ORDER BY ps.jersey_number
	`;
	return rows as unknown as (PlayerSeason & { name: string; hometown: string | null; high_school: string | null })[];
}

export async function getTeamPlayerStats(
	teamId: string,
	seasonId: string,
): Promise<PlayerSeasonStats[]> {
	const sql = getSql();
	const rows = await sql`
		SELECT *
		FROM player_season_stats
		WHERE team_id = ${teamId} AND season_id = ${seasonId}
		ORDER BY points DESC
	`;
	return rows as unknown as PlayerSeasonStats[];
}

export async function getTeamStats(
	teamId: string,
	seasonId: string,
) {
	const sql = getSql();
	const rows = await sql`
		SELECT *
		FROM team_season_stats
		WHERE team_id = ${teamId} AND season_id = ${seasonId}
		LIMIT 1
	`;
	return rows[0] || null;
}

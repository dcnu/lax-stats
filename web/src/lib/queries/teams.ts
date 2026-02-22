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
			lt.slug,
			COALESCE(tss.wins, 0) AS wins,
			COALESCE(tss.losses, 0) AS losses,
			COALESCE(tss.games_played, 0) AS games_played
		FROM team_seasons ts
		JOIN lookup_teams lt ON lt.id = ts.team_id
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
		SELECT ts.team_id, ts.team_name, ts.logo_url, ts.conference, ts.season_id, lt.slug
		FROM team_seasons ts
		JOIN lookup_teams lt ON lt.id = ts.team_id
		WHERE ts.team_id = ${teamId} AND ts.season_id = ${seasonId}
		LIMIT 1
	`;
	return (rows[0] as unknown as TeamDetail) || null;
}

export async function resolveTeamId(
	slugOrId: string,
	seasonId: string,
): Promise<string | null> {
	const sql = getSql();
	// Try slug lookup first
	const bySlug = await sql`
		SELECT ts.team_id
		FROM team_seasons ts
		JOIN lookup_teams lt ON lt.id = ts.team_id
		WHERE lt.slug = ${slugOrId} AND ts.season_id = ${seasonId}
		LIMIT 1
	`;
	if (bySlug[0]?.team_id) return bySlug[0].team_id as string;
	// Fall back: treat as direct team_id (legacy numeric links)
	const byId = await sql`
		SELECT team_id FROM team_seasons
		WHERE team_id = ${slugOrId} AND season_id = ${seasonId}
		LIMIT 1
	`;
	return (byId[0]?.team_id as string) ?? null;
}

export async function getTeamSchedule(
	teamId: string,
	seasonId: string,
): Promise<Game[]> {
	const sql = getSql();
	const rows = await sql`
		SELECT g.*,
			ht.slug AS home_team_slug,
			at.slug AS away_team_slug
		FROM games g
		JOIN lookup_teams ht ON ht.id = g.home_team_id
		JOIN lookup_teams at ON at.id = g.away_team_id
		WHERE (g.home_team_id = ${teamId} OR g.away_team_id = ${teamId})
			AND g.season_id = ${seasonId}
			AND g.id = (
				SELECT MIN(g2.id) FROM games g2
				WHERE g2.ncaa_game_id = g.ncaa_game_id
			)
		ORDER BY g.game_date ASC
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
		SELECT pss.*, ps.jersey_number
		FROM player_season_stats pss
		LEFT JOIN player_seasons ps
			ON pss.player_id = ps.player_id
			AND pss.team_id = ps.team_id
			AND pss.season_id = ps.season_id
		WHERE pss.team_id = ${teamId} AND pss.season_id = ${seasonId}
		ORDER BY pss.points DESC
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

import { getSql } from "@/lib/db";
import type { Season } from "@/lib/types";

export async function getSeasons(): Promise<Season[]> {
	const sql = getSql();
	const rows = await sql`
		SELECT id, division_id, is_current
		FROM lookup_seasons
		ORDER BY id DESC
	`;
	return rows as unknown as Season[];
}

export async function getCurrentSeasonId(): Promise<string> {
	const sql = getSql();
	const rows = await sql`
		SELECT id FROM lookup_seasons WHERE is_current = true LIMIT 1
	`;
	return rows[0]?.id || "2025";
}

export async function resolveSeasonId(
	seasonParam: string | null,
): Promise<string> {
	if (seasonParam) return seasonParam;
	return getCurrentSeasonId();
}

export async function resolveDivisionId(
	divisionParam: string | null,
): Promise<number> {
	if (divisionParam) return parseInt(divisionParam, 10);
	return 1;
}

import { getSupabase } from "@/lib/db";
import type { Season } from "@/lib/types";

function hasSupabaseEnv(): boolean {
	return !!(
		process.env.NEXT_PUBLIC_SUPABASE_URL &&
		process.env.SUPABASE_SERVICE_ROLE_KEY
	);
}

export async function getSeasons(): Promise<Season[]> {
	if (!hasSupabaseEnv()) return [];
	const supabase = getSupabase();
	const { data } = await supabase
		.from("lookup_seasons")
		.select("id, division_id, is_current")
		.order("id", { ascending: false });
	return (data ?? []) as Season[];
}

export async function getCurrentSeasonId(): Promise<string> {
	if (!hasSupabaseEnv()) return "2025";
	const supabase = getSupabase();
	const { data } = await supabase
		.from("lookup_seasons")
		.select("id")
		.eq("is_current", true)
		.limit(1)
		.single();
	return data?.id || "2025";
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

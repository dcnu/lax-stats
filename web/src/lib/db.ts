import { createClient, SupabaseClient } from "@supabase/supabase-js";
import postgres, { Sql } from "postgres";

let _supabase: SupabaseClient | null = null;
let _sql: Sql | null = null;

export function getSupabase(): SupabaseClient {
	if (!_supabase) {
		_supabase = createClient(
			process.env.NEXT_PUBLIC_SUPABASE_URL!,
			process.env.SUPABASE_SERVICE_ROLE_KEY!,
		);
	}
	return _supabase;
}

export function getSql(): Sql {
	if (!_sql) {
		_sql = postgres(process.env.DIRECT_URL!);
	}
	return _sql;
}

export async function getCurrentSeason(): Promise<string> {
	const supabase = getSupabase();
	const { data } = await supabase.from("lookup_seasons").select("id").eq("is_current", true).single();
	return data?.id || "2025";
}

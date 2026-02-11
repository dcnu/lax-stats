import { NextResponse } from "next/server";
import { getSupabase } from "@/lib/db";

export async function GET() {
	const { data, error } = await getSupabase()
		.from("lookup_seasons")
		.select("id, is_current")
		.order("id", { ascending: false });

	if (error) {
		console.error("Error fetching seasons:", error);
		return NextResponse.json(
			{ message: "Failed to fetch seasons" },
			{ status: 500 },
		);
	}

	return NextResponse.json(data);
}

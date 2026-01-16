import { NextResponse } from "next/server";
import {
	generateAndExecuteQuery,
	executeDirectQuery,
} from "@/lib/llm/query-generator";

export async function POST(request: Request) {
	try {
		const body = await request.json();
		const { query, sql, seasonId, divisionId } = body;

		// If raw SQL is provided, execute it directly
		if (sql && typeof sql === "string") {
			const result = await executeDirectQuery(sql);

			if (result.error) {
				return NextResponse.json(
					{ message: result.error, sql: result.sql },
					{ status: 400 }
				);
			}

			return NextResponse.json(result);
		}

		// Otherwise, use natural language query
		if (!query || typeof query !== "string") {
			return NextResponse.json(
				{ message: "Query is required" },
				{ status: 400 }
			);
		}

		const result = await generateAndExecuteQuery(
			query,
			seasonId || "2025",
			divisionId || 1
		);

		if (result.error) {
			return NextResponse.json(
				{ message: result.error, sql: result.sql },
				{ status: 400 }
			);
		}

		return NextResponse.json(result);
	} catch (error) {
		console.error("Query error:", error);
		return NextResponse.json(
			{ message: "An error occurred processing your query" },
			{ status: 500 }
		);
	}
}

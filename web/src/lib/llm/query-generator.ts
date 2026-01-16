import Anthropic from "@anthropic-ai/sdk";
import { prisma } from "@/lib/db";
import { SYSTEM_PROMPT } from "./schema-context";

export interface QueryResult {
	data: Record<string, unknown>[];
	sql: string;
	columns: string[];
	rowCount: number;
	error?: string;
}

function sanitizeQuery(sql: string): string {
	// Remove markdown code blocks if present
	let cleaned = sql.replace(/```sql\n?/gi, "").replace(/```\n?/gi, "");

	// Remove any leading/trailing whitespace
	cleaned = cleaned.trim();

	// Remove semicolon at the end if present (Prisma handles this)
	cleaned = cleaned.replace(/;\s*$/, "");

	return cleaned;
}

function isReadOnlyQuery(sql: string): boolean {
	const normalized = sql.toUpperCase().trim();

	// Only allow SELECT queries
	if (!normalized.startsWith("SELECT")) {
		return false;
	}

	// Disallow dangerous keywords
	const forbidden = [
		"INSERT",
		"UPDATE",
		"DELETE",
		"DROP",
		"CREATE",
		"ALTER",
		"TRUNCATE",
		"GRANT",
		"REVOKE",
		"EXECUTE",
	];

	for (const keyword of forbidden) {
		if (normalized.includes(keyword)) {
			return false;
		}
	}

	return true;
}

export async function generateAndExecuteQuery(
	userQuery: string,
	seasonId: string = "2025",
	divisionId: number = 1
): Promise<QueryResult> {
	const anthropic = new Anthropic();

	// Generate SQL from natural language
	const response = await anthropic.messages.create({
		model: "claude-sonnet-4-20250514",
		max_tokens: 1024,
		system: SYSTEM_PROMPT,
		messages: [
			{
				role: "user",
				content: `Generate a PostgreSQL query for: "${userQuery}"
Context: Season ${seasonId}, Division ${divisionId}`,
			},
		],
	});

	// Extract SQL from response
	const textBlock = response.content.find((block) => block.type === "text");
	if (!textBlock || textBlock.type !== "text") {
		return {
			data: [],
			sql: "",
			columns: [],
			rowCount: 0,
			error: "Failed to generate SQL query",
		};
	}

	const sql = sanitizeQuery(textBlock.text);

	// Validate query is read-only
	if (!isReadOnlyQuery(sql)) {
		return {
			data: [],
			sql,
			columns: [],
			rowCount: 0,
			error: "Only SELECT queries are allowed",
		};
	}

	try {
		// Execute the query
		const result = await prisma.$queryRawUnsafe<Record<string, unknown>[]>(sql);

		// Extract column names from first row
		const columns = result.length > 0 ? Object.keys(result[0]) : [];

		return {
			data: result,
			sql,
			columns,
			rowCount: result.length,
		};
	} catch (error) {
		const errorMessage =
			error instanceof Error ? error.message : "Query execution failed";
		return {
			data: [],
			sql,
			columns: [],
			rowCount: 0,
			error: errorMessage,
		};
	}
}

export async function executeDirectQuery(sql: string): Promise<QueryResult> {
	const cleanedSql = sanitizeQuery(sql);

	if (!isReadOnlyQuery(cleanedSql)) {
		return {
			data: [],
			sql: cleanedSql,
			columns: [],
			rowCount: 0,
			error: "Only SELECT queries are allowed",
		};
	}

	try {
		const result = await prisma.$queryRawUnsafe<Record<string, unknown>[]>(
			cleanedSql
		);
		const columns = result.length > 0 ? Object.keys(result[0]) : [];

		return {
			data: result,
			sql: cleanedSql,
			columns,
			rowCount: result.length,
		};
	} catch (error) {
		const errorMessage =
			error instanceof Error ? error.message : "Query execution failed";
		return {
			data: [],
			sql: cleanedSql,
			columns: [],
			rowCount: 0,
			error: errorMessage,
		};
	}
}

import "dotenv/config";
import { PrismaClient } from "../src/generated/prisma/client.js";

const prisma = new PrismaClient();

async function main() {
	// Seed divisions
	await prisma.division.upsert({
		where: { id: 1 },
		update: {},
		create: { id: 1, name: "Division I", abbreviation: "D1" },
	});
	await prisma.division.upsert({
		where: { id: 2 },
		update: {},
		create: { id: 2, name: "Division II", abbreviation: "D2" },
	});
	await prisma.division.upsert({
		where: { id: 3 },
		update: {},
		create: { id: 3, name: "Division III", abbreviation: "D3" },
	});

	// Seed positions
	const positions = [
		{ code: "A", name: "Attack", category: "offense" },
		{ code: "ATT", name: "Attack", category: "offense" },
		{ code: "M", name: "Midfield", category: "midfield" },
		{ code: "D", name: "Defense", category: "defense" },
		{ code: "G", name: "Goalie", category: "goalie" },
		{ code: "GK", name: "Goalie", category: "goalie" },
		{ code: "FO", name: "Faceoff Specialist", category: "specialist" },
		{ code: "LSM", name: "Long Stick Midfield", category: "defense" },
		{ code: "SSDM", name: "Short Stick Defensive Midfield", category: "defense" },
	];

	for (const pos of positions) {
		await prisma.position.upsert({
			where: { code: pos.code },
			update: {},
			create: pos,
		});
	}

	// Seed play types
	const playTypes = [
		{ code: "GOAL", name: "Goal", category: "scoring" },
		{ code: "ASSIST", name: "Assist", category: "scoring" },
		{ code: "SHOT", name: "Shot", category: "shooting" },
		{ code: "SHOT_SAVED", name: "Shot Saved", category: "shooting" },
		{ code: "SHOT_WIDE", name: "Shot Wide", category: "shooting" },
		{ code: "SHOT_HIGH", name: "Shot High", category: "shooting" },
		{ code: "SAVE", name: "Save", category: "goalie" },
		{ code: "FACEOFF_WON", name: "Faceoff Won", category: "faceoff" },
		{ code: "FACEOFF_LOST", name: "Faceoff Lost", category: "faceoff" },
		{ code: "GROUND_BALL", name: "Ground Ball", category: "possession" },
		{ code: "TURNOVER", name: "Turnover", category: "possession" },
		{ code: "CAUSED_TURNOVER", name: "Caused Turnover", category: "possession" },
		{ code: "CLEAR_GOOD", name: "Clear Good", category: "possession" },
		{ code: "CLEAR_FAILED", name: "Clear Failed", category: "possession" },
		{ code: "PENALTY", name: "Penalty", category: "penalty" },
		{ code: "GOALIE_IN", name: "Goalie In", category: "substitution" },
		{ code: "TIMEOUT", name: "Timeout", category: "game_event" },
		{ code: "PERIOD_START", name: "Period Start", category: "game_event" },
		{ code: "PERIOD_END", name: "Period End", category: "game_event" },
		{ code: "UNKNOWN", name: "Unknown", category: "other" },
	];

	for (const pt of playTypes) {
		await prisma.playType.upsert({
			where: { code: pt.code },
			update: {},
			create: pt,
		});
	}

	// Seed 2025 season
	await prisma.season.upsert({
		where: { id: "2025" },
		update: {},
		create: {
			id: "2025",
			divisionId: 1,
			startYear: 2025,
			endYear: 2025,
			startDate: new Date("2025-02-01"),
			endDate: new Date("2025-05-26"),
			isCurrent: true,
		},
	});

	console.log("Seed data inserted successfully");
}

main()
	.catch((e) => {
		console.error(e);
		process.exit(1);
	})
	.finally(async () => {
		await prisma.$disconnect();
	});

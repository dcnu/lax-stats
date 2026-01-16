import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export async function GET() {
	try {
		const seasons = await prisma.season.findMany({
			select: { id: true },
			orderBy: { id: "desc" },
		});

		return NextResponse.json(seasons);
	} catch (error) {
		console.error("Error fetching seasons:", error);
		return NextResponse.json(
			{ message: "Failed to fetch seasons" },
			{ status: 500 }
		);
	}
}

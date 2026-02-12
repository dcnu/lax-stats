import type { Metadata } from "next";
import { searchParamsCache } from "@/lib/search-params";
import { resolveSeasonId } from "@/lib/queries/seasons";
import { getPlayerLeaderboard } from "@/lib/queries/players";
import { PlayersTable } from "./players-table";

export const metadata: Metadata = {
	title: "Players | Lacrosse Stats",
};

export default async function PlayersPage({
	searchParams,
}: {
	searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
	const params = searchParamsCache.parse(await searchParams);
	const seasonId = await resolveSeasonId(params.season);
	const players = await getPlayerLeaderboard(seasonId);

	return (
		<div className="space-y-6">
			<h1 className="text-2xl font-bold">Players</h1>
			<PlayersTable players={players} />
		</div>
	);
}

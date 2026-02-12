import { searchParamsCache } from "@/lib/search-params";
import { resolveSeasonId } from "@/lib/queries/seasons";
import { getGamesForSeason } from "@/lib/queries/games";
import { GamesTable } from "./games-table";

export default async function GamesPage({
	searchParams,
}: {
	searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
	const params = searchParamsCache.parse(await searchParams);
	const seasonId = await resolveSeasonId(params.season);
	const games = await getGamesForSeason(seasonId);

	return (
		<div className="space-y-6">
			<h1 className="text-3xl font-bold">Games</h1>
			<GamesTable games={games} />
		</div>
	);
}

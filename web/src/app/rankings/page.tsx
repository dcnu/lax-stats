import { searchParamsCache } from "@/lib/search-params";
import { resolveSeasonId, resolveDivisionId } from "@/lib/queries/seasons";
import { getRankings } from "@/lib/queries/rankings";
import { RankingsTable } from "./rankings-table";

export default async function RankingsPage({
	searchParams,
}: {
	searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
	const params = searchParamsCache.parse(await searchParams);
	const seasonId = await resolveSeasonId(params.season);
	const divisionId = await resolveDivisionId(params.division);
	const rankings = await getRankings(seasonId, divisionId);

	return (
		<div className="space-y-6">
			<h1 className="text-2xl font-bold">Rankings</h1>
			<RankingsTable rankings={rankings} />
		</div>
	);
}

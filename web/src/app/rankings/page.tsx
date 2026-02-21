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
			<div className="space-y-1">
				<h1 className="text-2xl font-bold">Rankings</h1>
				<p className="text-sm text-muted-foreground">
					Recalculated weekly, every Monday at 12:00&nbsp;am&nbsp;PT.
					Game results, box scores, and player stats on all other pages
					update as soon as data is available.
				</p>
			</div>
			<RankingsTable rankings={rankings} />
		</div>
	);
}

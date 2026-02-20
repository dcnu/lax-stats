import { searchParamsCache } from "@/lib/search-params";
import { resolveSeasonId } from "@/lib/queries/seasons";
import { getTeamsForSeason } from "@/lib/queries/teams";
import { TeamsView } from "./teams-view";

export default async function TeamsPage({
	searchParams,
}: {
	searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
	const params = searchParamsCache.parse(await searchParams);
	const seasonId = await resolveSeasonId(params.season);
	const teams = await getTeamsForSeason(seasonId);

	return (
		<div>
			<h1 className="text-2xl font-bold mb-6">Teams</h1>
			<TeamsView teams={teams} />
		</div>
	);
}

import { searchParamsCache } from "@/lib/search-params";
import { resolveSeasonId } from "@/lib/queries/seasons";
import { getTeamsForSeason } from "@/lib/queries/teams";
import { formatRecord } from "@/lib/format";
import { TeamLink } from "@/components/entity-link";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

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
			<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
				{teams.map((team) => (
					<TeamLink key={team.team_id} teamId={team.team_id} className="block">
						<Card className="h-full transition-colors hover:bg-muted/50">
							<CardHeader>
								<CardTitle>{team.team_name}</CardTitle>
								<CardDescription>
									{team.games_played > 0
										? formatRecord(team.wins, team.losses)
										: "No games played"}
								</CardDescription>
							</CardHeader>
						</Card>
					</TeamLink>
				))}
			</div>
		</div>
	);
}

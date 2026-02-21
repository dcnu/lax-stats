import { notFound } from "next/navigation";
import { searchParamsCache } from "@/lib/search-params";
import { resolveSeasonId } from "@/lib/queries/seasons";
import {
	resolveTeamId,
	getTeamDetail,
	getTeamSchedule,
	getTeamRoster,
	getTeamPlayerStats,
	getTeamStats,
} from "@/lib/queries/teams";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { TeamHeader } from "./_components/team-header";
import { TeamDetailTabs } from "./_components/team-detail-tabs";

export default async function TeamDetailPage({
	params,
	searchParams,
}: {
	params: Promise<{ teamSlug: string }>;
	searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
	const { teamSlug } = await params;
	const sp = searchParamsCache.parse(await searchParams);
	const seasonId = await resolveSeasonId(sp.season);

	const teamId = await resolveTeamId(teamSlug, seasonId);
	if (!teamId) notFound();

	const [team, games, roster, playerStats, teamStats] = await Promise.all([
		getTeamDetail(teamId, seasonId),
		getTeamSchedule(teamId, seasonId),
		getTeamRoster(teamId, seasonId),
		getTeamPlayerStats(teamId, seasonId),
		getTeamStats(teamId, seasonId),
	]);

	if (!team) notFound();

	const wins = teamStats?.wins ?? 0;
	const losses = teamStats?.losses ?? 0;

	return (
		<div>
			<Breadcrumbs
				items={[
					{ label: "Teams", href: "/teams" },
					{ label: team.team_name },
				]}
			/>
			<TeamHeader teamName={team.team_name} wins={wins} losses={losses} />
			<TeamDetailTabs
				games={games}
				roster={roster}
				stats={playerStats}
				teamId={teamId}
			/>
		</div>
	);
}

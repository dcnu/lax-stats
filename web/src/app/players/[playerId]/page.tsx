import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { searchParamsCache } from "@/lib/search-params";
import { resolveSeasonId } from "@/lib/queries/seasons";
import {
	getPlayerDetail,
	getPlayerSeasonStats,
	getPlayerGameLog,
} from "@/lib/queries/players";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { PlayerHeader } from "./_components/player-header";
import { PlayerSeasonStatsTable } from "./_components/player-season-stats";
import { PlayerGameLog } from "./_components/player-game-log";

export async function generateMetadata({
	params,
}: {
	params: Promise<{ playerId: string }>;
}): Promise<Metadata> {
	const { playerId } = await params;
	const player = await getPlayerDetail(parseInt(playerId, 10));
	return {
		title: player
			? `${player.name} | Lacrosse Stats`
			: "Player Not Found | Lacrosse Stats",
	};
}

export default async function PlayerDetailPage({
	params,
	searchParams,
}: {
	params: Promise<{ playerId: string }>;
	searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
	const { playerId } = await params;
	const parsedParams = searchParamsCache.parse(await searchParams);
	const seasonId = await resolveSeasonId(parsedParams.season);
	const id = parseInt(playerId, 10);

	const [player, seasonStats, gameLog] = await Promise.all([
		getPlayerDetail(id),
		getPlayerSeasonStats(id),
		getPlayerGameLog(id, seasonId),
	]);

	if (!player) notFound();

	return (
		<div className="space-y-6">
			<Breadcrumbs
				items={[
					{ label: "Players", href: "/players" },
					{ label: player.name },
				]}
			/>
			<PlayerHeader player={player} />
			<PlayerSeasonStatsTable stats={seasonStats} />
			<PlayerGameLog games={gameLog} />
		</div>
	);
}

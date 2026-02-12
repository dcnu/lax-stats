import { notFound } from "next/navigation";
import { getGameDetail, getGameBoxScore, getGamePlays } from "@/lib/queries/games";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { GameHeader } from "./_components/game-header";
import { GameDetailTabs } from "./_components/game-detail-tabs";

export default async function GameDetailPage({
	params,
}: {
	params: Promise<{ gameId: string }>;
}) {
	const { gameId } = await params;
	const game = await getGameDetail(gameId);
	if (!game) notFound();

	const [boxScore, plays] = await Promise.all([
		getGameBoxScore(gameId),
		getGamePlays(gameId, game.season_id),
	]);

	return (
		<div className="space-y-6">
			<Breadcrumbs
				items={[
					{ label: "Games", href: "/games" },
					{ label: `${game.away_team_name} @ ${game.home_team_name}` },
				]}
			/>
			<GameHeader game={game} />
			<GameDetailTabs
				game={game}
				boxScore={boxScore}
				plays={plays}
			/>
		</div>
	);
}

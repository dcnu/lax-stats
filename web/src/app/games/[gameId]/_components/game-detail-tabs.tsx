"use client";

import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { BoxScore } from "./box-score";
import { PlayByPlay } from "./play-by-play";
import { TeamComparison } from "./team-comparison";
import type { Game, PlayerGameStats, GamePlay } from "@/lib/types";

export function GameDetailTabs({
	game,
	boxScore,
	plays,
}: {
	game: Game;
	boxScore: PlayerGameStats[];
	plays: GamePlay[];
}) {
	return (
		<Tabs defaultValue="box-score">
			<TabsList>
				<TabsTrigger value="box-score">Box Score</TabsTrigger>
				<TabsTrigger value="play-by-play">Play-by-Play</TabsTrigger>
				<TabsTrigger value="comparison">Comparison</TabsTrigger>
			</TabsList>
			<TabsContent value="box-score">
				<BoxScore game={game} players={boxScore} />
			</TabsContent>
			<TabsContent value="play-by-play">
				<PlayByPlay game={game} plays={plays} />
			</TabsContent>
			<TabsContent value="comparison">
				<TeamComparison game={game} players={boxScore} />
			</TabsContent>
		</Tabs>
	);
}

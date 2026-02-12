"use client";

import type { Game, PlayerSeason, PlayerSeasonStats } from "@/lib/types";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TeamSchedule } from "./team-schedule";
import { TeamRoster } from "./team-roster";
import { TeamStats } from "./team-stats";

type RosterPlayer = PlayerSeason & {
	name: string;
	hometown: string | null;
	high_school: string | null;
};

export function TeamDetailTabs({
	games,
	roster,
	stats,
	teamId,
}: {
	games: Game[];
	roster: RosterPlayer[];
	stats: PlayerSeasonStats[];
	teamId: string;
}) {
	return (
		<Tabs defaultValue="schedule">
			<TabsList>
				<TabsTrigger value="schedule">Schedule</TabsTrigger>
				<TabsTrigger value="roster">Roster</TabsTrigger>
				<TabsTrigger value="stats">Stats</TabsTrigger>
			</TabsList>
			<TabsContent value="schedule">
				<TeamSchedule games={games} teamId={teamId} />
			</TabsContent>
			<TabsContent value="roster">
				<TeamRoster roster={roster} />
			</TabsContent>
			<TabsContent value="stats">
				<TeamStats stats={stats} />
			</TabsContent>
		</Tabs>
	);
}

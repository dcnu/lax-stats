"use client";

import type { PlayerSeasonStats } from "@/lib/types";
import { formatPct } from "@/lib/format";
import { TeamLink } from "@/components/entity-link";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";

export function PlayerSeasonStatsTable({
	stats,
}: {
	stats: PlayerSeasonStats[];
}) {
	const hasGoalieStats = stats.some((s) => s.goalie_minutes > 0);

	return (
		<div className="space-y-2">
			<h2 className="text-lg font-semibold">Season Stats</h2>
			<div className="rounded-md border">
				<Table>
					<TableHeader>
						<TableRow>
							<TableHead>Season</TableHead>
							<TableHead>Team</TableHead>
							<TableHead className="text-right">GP</TableHead>
							<TableHead className="text-right">G</TableHead>
							<TableHead className="text-right">A</TableHead>
							<TableHead className="text-right">Pts</TableHead>
							<TableHead className="text-right">Shots</TableHead>
							<TableHead className="text-right">SOG</TableHead>
							<TableHead className="text-right">GB</TableHead>
							<TableHead className="text-right">TO</TableHead>
							<TableHead className="text-right">CT</TableHead>
							{hasGoalieStats && (
								<>
									<TableHead className="text-right">GA</TableHead>
									<TableHead className="text-right">Saves</TableHead>
									<TableHead className="text-right">Save%</TableHead>
								</>
							)}
						</TableRow>
					</TableHeader>
					<TableBody>
						{stats.map((s) => (
							<TableRow key={s.id}>
								<TableCell>{s.season_id}</TableCell>
								<TableCell>
									{s.team_id ? (
										<TeamLink teamSlug={s.team_slug as string} teamId={s.team_id}>
											{s.team_name ?? s.team_id}
										</TeamLink>
									) : (
										"-"
									)}
								</TableCell>
								<TableCell className="text-right">{s.games_played}</TableCell>
								<TableCell className="text-right">{s.goals}</TableCell>
								<TableCell className="text-right">{s.assists}</TableCell>
								<TableCell className="text-right">{s.points}</TableCell>
								<TableCell className="text-right">{s.shots}</TableCell>
								<TableCell className="text-right">{s.shots_on_goal}</TableCell>
								<TableCell className="text-right">{s.ground_balls}</TableCell>
								<TableCell className="text-right">{s.turnovers}</TableCell>
								<TableCell className="text-right">{s.caused_turnovers}</TableCell>
								{hasGoalieStats && (
									<>
										<TableCell className="text-right">{s.goals_allowed}</TableCell>
										<TableCell className="text-right">{s.saves}</TableCell>
										<TableCell className="text-right">{formatPct(s.save_pct)}</TableCell>
									</>
								)}
							</TableRow>
						))}
						{stats.length === 0 && (
							<TableRow>
								<TableCell
									colSpan={hasGoalieStats ? 14 : 11}
									className="h-24 text-center"
								>
									No season stats available.
								</TableCell>
							</TableRow>
						)}
					</TableBody>
				</Table>
			</div>
		</div>
	);
}

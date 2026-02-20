"use client";

import type { Game } from "@/lib/types";
import { formatGameDate, formatRecord } from "@/lib/format";
import { GameLink, TeamLink } from "@/components/entity-link";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";

export function TeamSchedule({
	games,
	teamId,
}: {
	games: Game[];
	teamId: string;
}) {
	if (games.length === 0) {
		return <p className="text-muted-foreground">No games scheduled.</p>;
	}

	return (
		<div className="rounded-md border">
			<Table>
				<TableHeader>
					<TableRow>
						<TableHead>Date</TableHead>
						<TableHead>Opponent</TableHead>
						<TableHead>Result</TableHead>
						<TableHead>Record</TableHead>
						<TableHead>Location</TableHead>
					</TableRow>
				</TableHeader>
				<TableBody>
					{games.map((game) => {
						const isHome = game.home_team_id === teamId;
						const opponentId = isHome ? game.away_team_id : game.home_team_id;
						const opponentName = isHome ? game.away_team_name : game.home_team_name;
						const teamScore = isHome ? game.home_score : game.away_score;
						const opponentScore = isHome ? game.away_score : game.home_score;
						const isWin = game.winning_team_id === teamId;
						const isLoss = game.losing_team_id === teamId;
						const isCompleted = game.status === "final";
						const teamWins = isHome ? game.home_team_wins : game.away_team_wins;
						const teamLosses = isHome ? game.home_team_losses : game.away_team_losses;

						return (
							<TableRow key={game.id}>
								<TableCell>{formatGameDate(game.game_date)}</TableCell>
								<TableCell>
									<span className="text-muted-foreground mr-1">
										{isHome ? "vs" : "@"}
									</span>
									<TeamLink teamId={opponentId}>{opponentName}</TeamLink>
								</TableCell>
								<TableCell>
									{isCompleted && teamScore !== null && opponentScore !== null ? (
										<GameLink gameId={game.id} className="flex items-center gap-2">
											<Badge
												variant={isWin ? "default" : isLoss ? "destructive" : "secondary"}
												className={cn("w-5 text-center", isWin && "bg-emerald-600 text-white")}
											>
												{isWin ? "W" : isLoss ? "L" : "T"}
											</Badge>
											<span>
												{teamScore}-{opponentScore}
											</span>
										</GameLink>
									) : (
										<span className="text-muted-foreground">-</span>
									)}
								</TableCell>
								<TableCell>
									{isCompleted && teamWins !== null && teamLosses !== null
										? formatRecord(teamWins, teamLosses)
										: "-"}
								</TableCell>
								<TableCell className="text-muted-foreground">
									{game.location || "-"}
								</TableCell>
							</TableRow>
						);
					})}
				</TableBody>
			</Table>
		</div>
	);
}

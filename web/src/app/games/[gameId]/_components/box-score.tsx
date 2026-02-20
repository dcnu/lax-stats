"use client";

import { useState, useMemo } from "react";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { PlayerLink, TeamLink } from "@/components/entity-link";
import { formatTime, formatPct } from "@/lib/format";
import type { Game, PlayerGameStats } from "@/lib/types";

type SortMode = "points" | "name" | "jersey";

function hasAnyStats(p: PlayerGameStats): boolean {
	return (
		p.goals !== 0 ||
		p.assists !== 0 ||
		p.points !== 0 ||
		p.shots !== 0 ||
		p.shots_on_goal !== 0 ||
		p.ground_balls !== 0 ||
		p.turnovers !== 0 ||
		p.caused_turnovers !== 0 ||
		p.faceoff_wins !== 0 ||
		p.faceoffs_taken !== 0
	);
}

function getLastName(name: string | null): string {
	if (!name) return "";
	const parts = name.split(" ");
	return parts[parts.length - 1].toLowerCase();
}

function sortPlayers(players: PlayerGameStats[], mode: SortMode): PlayerGameStats[] {
	return [...players].sort((a, b) => {
		switch (mode) {
			case "points":
				return b.points - a.points;
			case "name":
				return getLastName(a.player_name).localeCompare(getLastName(b.player_name));
			case "jersey": {
				const aNum = a.jersey_number ?? Infinity;
				const bNum = b.jersey_number ?? Infinity;
				return aNum - bNum;
			}
		}
	});
}

function FieldPlayersTable({ players }: { players: PlayerGameStats[] }) {
	const [sortBy, setSortBy] = useState<SortMode>("points");
	const filtered = players.filter(hasAnyStats);
	const sorted = sortPlayers(filtered, sortBy);

	return (
		<div className="space-y-2">
			<div className="flex items-center gap-2">
				<span className="text-sm text-muted-foreground">Sort:</span>
				<Button
					variant={sortBy === "points" ? "secondary" : "ghost"}
					size="sm"
					onClick={() => setSortBy("points")}
				>
					Points
				</Button>
				<Button
					variant={sortBy === "name" ? "secondary" : "ghost"}
					size="sm"
					onClick={() => setSortBy("name")}
				>
					Name
				</Button>
				<Button
					variant={sortBy === "jersey" ? "secondary" : "ghost"}
					size="sm"
					onClick={() => setSortBy("jersey")}
				>
					Jersey
				</Button>
			</div>
		<div className="rounded-md border">
			<Table>
				<TableHeader>
					<TableRow>
						<TableHead className="w-8">#</TableHead>
						<TableHead>Player</TableHead>
						<TableHead className="text-right">G</TableHead>
						<TableHead className="text-right">A</TableHead>
						<TableHead className="text-right">Pts</TableHead>
						<TableHead className="text-right">Shots</TableHead>
						<TableHead className="text-right">SOG</TableHead>
						<TableHead className="text-right">GB</TableHead>
						<TableHead className="text-right">TO</TableHead>
						<TableHead className="text-right">CT</TableHead>
						<TableHead className="text-right">FO W/L</TableHead>
					</TableRow>
				</TableHeader>
				<TableBody>
					{sorted.map((p) => (
						<TableRow key={p.id}>
							<TableCell className="text-muted-foreground">{p.jersey_number ?? "-"}</TableCell>
							<TableCell>
								<PlayerLink playerId={p.player_id}>
									{p.player_name ?? "Unknown"}
								</PlayerLink>
							</TableCell>
							<TableCell className="text-right">{p.goals}</TableCell>
							<TableCell className="text-right">{p.assists}</TableCell>
							<TableCell className="text-right font-medium">{p.points}</TableCell>
							<TableCell className="text-right">{p.shots}</TableCell>
							<TableCell className="text-right">{p.shots_on_goal}</TableCell>
							<TableCell className="text-right">{p.ground_balls}</TableCell>
							<TableCell className="text-right">{p.turnovers}</TableCell>
							<TableCell className="text-right">{p.caused_turnovers}</TableCell>
							<TableCell className="text-right">
								{p.faceoffs_taken > 0 ? `${p.faceoff_wins}/${p.faceoffs_taken}` : "-"}
							</TableCell>
						</TableRow>
					))}
				</TableBody>
			</Table>
		</div>
		</div>
	);
}

function GoaliesTable({ goalies }: { goalies: PlayerGameStats[] }) {
	const sorted = [...goalies].sort(
		(a, b) => (b.goalie_minutes ?? 0) - (a.goalie_minutes ?? 0),
	);

	if (sorted.length === 0) return null;

	return (
		<div className="rounded-md border">
			<Table>
				<TableHeader>
					<TableRow>
						<TableHead className="w-8">#</TableHead>
						<TableHead>Goalie</TableHead>
						<TableHead className="text-right">GA</TableHead>
						<TableHead className="text-right">Saves</TableHead>
						<TableHead className="text-right">Save%</TableHead>
						<TableHead className="text-right">Min</TableHead>
					</TableRow>
				</TableHeader>
				<TableBody>
					{sorted.map((g) => (
						<TableRow key={g.id}>
							<TableCell className="text-muted-foreground">{g.jersey_number ?? "-"}</TableCell>
							<TableCell>
								<PlayerLink playerId={g.player_id}>
									{g.player_name ?? "Unknown"}
								</PlayerLink>
							</TableCell>
							<TableCell className="text-right">{g.goals_allowed}</TableCell>
							<TableCell className="text-right">{g.saves}</TableCell>
							<TableCell className="text-right">{formatPct(g.save_percentage)}</TableCell>
							<TableCell className="text-right">{formatTime(g.goalie_minutes)}</TableCell>
						</TableRow>
					))}
				</TableBody>
			</Table>
		</div>
	);
}

export function BoxScore({
	game,
	players,
}: {
	game: Game;
	players: PlayerGameStats[];
}) {
	const { awayField, awayGoalies, homeField, homeGoalies } = useMemo(() => {
		const away = players.filter((p) => p.team_id === game.away_team_id);
		const home = players.filter((p) => p.team_id === game.home_team_id);

		const isGoalie = (p: PlayerGameStats) =>
			p.position === "G" || (p.goalie_minutes != null && p.goalie_minutes > 0);

		return {
			awayField: away.filter((p) => !isGoalie(p)),
			awayGoalies: away.filter(isGoalie),
			homeField: home.filter((p) => !isGoalie(p)),
			homeGoalies: home.filter(isGoalie),
		};
	}, [players, game.away_team_id, game.home_team_id]);

	return (
		<div className="space-y-8 pt-4">
			<div className="space-y-3">
				<h3 className="text-lg font-semibold">
					<TeamLink teamId={game.away_team_id}>{game.away_team_name}</TeamLink>
				</h3>
				<FieldPlayersTable players={awayField} />
				<GoaliesTable goalies={awayGoalies} />
			</div>
			<div className="space-y-3">
				<h3 className="text-lg font-semibold">
					<TeamLink teamId={game.home_team_id}>{game.home_team_name}</TeamLink>
				</h3>
				<FieldPlayersTable players={homeField} />
				<GoaliesTable goalies={homeGoalies} />
			</div>
		</div>
	);
}

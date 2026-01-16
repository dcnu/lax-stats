"use client";

import { useQuery } from "@tanstack/react-query";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { FilterableTable } from "@/components/filterable-table";
import { useSeasonStore } from "@/lib/stores/season-store";
import { Trophy, Calendar, Medal } from "lucide-react";

type TopScorer = {
	player_id: number;
	player_name: string;
	team_id: string;
	team_name: string;
	season_id: string;
	games_played: number;
	total_goals: number;
	total_assists: number;
	total_points: number;
	total_shots: number;
	total_shots_on_goal: number;
	total_ground_balls: number;
	total_turnovers: number;
	total_caused_turnovers: number;
	points_per_game: number;
	[key: string]: unknown;
};

type RecentGame = {
	id: string;
	date: string;
	home_team: string;
	home_score: number;
	away_team: string;
	away_score: number;
	location: string;
	attendance: number | null;
	[key: string]: unknown;
};

type TeamStanding = {
	team_name: string;
	wins: number;
	losses: number;
	games_played: number;
	win_pct: string;
	goals_for: number;
	goals_against: number;
	goal_diff: number;
	[key: string]: unknown;
};

async function fetchTopScorers(seasonId: string): Promise<TopScorer[]> {
	const response = await fetch(`/api/stats/top-scorers?seasonId=${seasonId}&limit=50`);
	if (!response.ok) throw new Error("Failed to fetch top scorers");
	return response.json();
}

async function fetchRecentGames(seasonId: string): Promise<RecentGame[]> {
	const response = await fetch(`/api/stats/recent-games?seasonId=${seasonId}&limit=30`);
	if (!response.ok) throw new Error("Failed to fetch recent games");
	return response.json();
}

async function fetchTeamStandings(seasonId: string): Promise<TeamStanding[]> {
	const response = await fetch(`/api/stats/team-standings?seasonId=${seasonId}`);
	if (!response.ok) throw new Error("Failed to fetch team standings");
	return response.json();
}

const scorerColumns = [
	{ key: "player_name", label: "Player", filterable: true },
	{ key: "team_name", label: "Team", filterable: true },
	{ key: "games_played", label: "GP", filterable: false },
	{ key: "total_goals", label: "Goals", filterable: false },
	{ key: "total_assists", label: "Assists", filterable: false },
	{ key: "total_points", label: "Points", filterable: false },
	{ key: "points_per_game", label: "PPG", filterable: false },
	{ key: "total_shots", label: "Shots", filterable: false },
	{ key: "total_ground_balls", label: "GB", filterable: false },
];

const gameColumns = [
	{ key: "date", label: "Date", filterable: false },
	{ key: "home_team", label: "Home", filterable: true },
	{ key: "home_score", label: "Score", filterable: false },
	{ key: "away_team", label: "Away", filterable: true },
	{ key: "away_score", label: "Score", filterable: false },
	{ key: "location", label: "Location", filterable: true },
];

const standingColumns = [
	{ key: "team_name", label: "Team", filterable: true },
	{ key: "wins", label: "W", filterable: false },
	{ key: "losses", label: "L", filterable: false },
	{ key: "win_pct", label: "PCT", filterable: false },
	{ key: "goals_for", label: "GF", filterable: false },
	{ key: "goals_against", label: "GA", filterable: false },
	{ key: "goal_diff", label: "+/-", filterable: false },
];

function LoadingSkeleton() {
	return (
		<div className="space-y-4">
			<Skeleton className="h-10 w-full" />
			<Skeleton className="h-64 w-full" />
		</div>
	);
}

export function DataPreview() {
	const { selectedSeason } = useSeasonStore();
	const seasonId = selectedSeason || "2025";

	const scorersQuery = useQuery({
		queryKey: ["top-scorers", seasonId],
		queryFn: () => fetchTopScorers(seasonId),
		staleTime: 5 * 60 * 1000,
	});

	const gamesQuery = useQuery({
		queryKey: ["recent-games", seasonId],
		queryFn: () => fetchRecentGames(seasonId),
		staleTime: 5 * 60 * 1000,
	});

	const standingsQuery = useQuery({
		queryKey: ["team-standings", seasonId],
		queryFn: () => fetchTeamStandings(seasonId),
		staleTime: 5 * 60 * 1000,
	});

	return (
		<div className="space-y-4">
			<div className="flex items-center justify-between">
				<h3 className="text-lg font-semibold">Explore Data</h3>
				<p className="text-sm text-muted-foreground">
					{seasonId} Season
				</p>
			</div>

			<Tabs defaultValue="scorers" className="w-full">
				<TabsList className="grid w-full grid-cols-3">
					<TabsTrigger value="scorers" className="gap-2">
						<Trophy className="h-4 w-4" />
						Top Scorers
					</TabsTrigger>
					<TabsTrigger value="games" className="gap-2">
						<Calendar className="h-4 w-4" />
						Recent Games
					</TabsTrigger>
					<TabsTrigger value="standings" className="gap-2">
						<Medal className="h-4 w-4" />
						Standings
					</TabsTrigger>
				</TabsList>

				<TabsContent value="scorers" className="mt-4">
					{scorersQuery.isLoading && <LoadingSkeleton />}
					{scorersQuery.isError && (
						<Alert variant="destructive">
							<AlertDescription>{scorersQuery.error.message}</AlertDescription>
						</Alert>
					)}
					{scorersQuery.isSuccess && (
						<FilterableTable
							data={scorersQuery.data}
							columns={scorerColumns}
							defaultSort={{ key: "total_points", desc: true }}
						/>
					)}
				</TabsContent>

				<TabsContent value="games" className="mt-4">
					{gamesQuery.isLoading && <LoadingSkeleton />}
					{gamesQuery.isError && (
						<Alert variant="destructive">
							<AlertDescription>{gamesQuery.error.message}</AlertDescription>
						</Alert>
					)}
					{gamesQuery.isSuccess && (
						<FilterableTable
							data={gamesQuery.data}
							columns={gameColumns}
							defaultSort={{ key: "date", desc: true }}
						/>
					)}
				</TabsContent>

				<TabsContent value="standings" className="mt-4">
					{standingsQuery.isLoading && <LoadingSkeleton />}
					{standingsQuery.isError && (
						<Alert variant="destructive">
							<AlertDescription>{standingsQuery.error.message}</AlertDescription>
						</Alert>
					)}
					{standingsQuery.isSuccess && (
						<FilterableTable
							data={standingsQuery.data}
							columns={standingColumns}
							defaultSort={{ key: "win_pct", desc: true }}
						/>
					)}
				</TabsContent>
			</Tabs>
		</div>
	);
}

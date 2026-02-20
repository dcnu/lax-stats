"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { TeamLink } from "@/components/entity-link";
import { formatRecord } from "@/lib/format";
import type { Team } from "@/lib/types";

export function TeamsView({ teams }: { teams: Team[] }) {
	return (
		<Tabs defaultValue="table">
			<TabsList>
				<TabsTrigger value="table">Table</TabsTrigger>
				<TabsTrigger value="cards">Cards</TabsTrigger>
			</TabsList>
			<TabsContent value="table">
				<div className="rounded-md border">
					<Table>
						<TableHeader>
							<TableRow>
								<TableHead>Team</TableHead>
								<TableHead className="text-right">Record</TableHead>
								<TableHead className="text-right">GP</TableHead>
							</TableRow>
						</TableHeader>
						<TableBody>
							{teams.map((team) => (
								<TableRow key={team.team_id}>
									<TableCell>
										<TeamLink teamId={team.team_id}>
											{team.team_name}
										</TeamLink>
									</TableCell>
									<TableCell className="text-right">
										{team.games_played > 0
											? formatRecord(team.wins, team.losses)
											: "-"}
									</TableCell>
									<TableCell className="text-right">
										{team.games_played}
									</TableCell>
								</TableRow>
							))}
						</TableBody>
					</Table>
				</div>
			</TabsContent>
			<TabsContent value="cards">
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
			</TabsContent>
		</Tabs>
	);
}

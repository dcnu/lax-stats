"use client";

import { useState, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { PlayerLink } from "@/components/entity-link";
import { formatTime } from "@/lib/format";
import type { Game, GamePlay } from "@/lib/types";

const QUARTER_LABELS: Record<number, string> = {
	1: "Q1",
	2: "Q2",
	3: "Q3",
	4: "Q4",
};

function getQuarterLabel(q: number): string {
	return QUARTER_LABELS[q] ?? "OT";
}

const CATEGORY_FILTERS = ["All", "Scoring", "Penalty", "Faceoff", "Shot", "Turnover"] as const;

export function PlayByPlay({
	game,
	plays,
}: {
	game: Game;
	plays: GamePlay[];
}) {
	const [quarterFilter, setQuarterFilter] = useState<string>("All");
	const [categoryFilter, setCategoryFilter] = useState<string>("All");

	const quarters = useMemo(() => {
		const set = new Set(plays.map((p) => p.quarter));
		return Array.from(set).sort((a, b) => a - b);
	}, [plays]);

	const quarterButtons = useMemo(() => {
		return ["All", ...quarters.map((q) => getQuarterLabel(q))];
	}, [quarters]);

	const filtered = useMemo(() => {
		return plays.filter((p) => {
			if (quarterFilter !== "All") {
				const label = getQuarterLabel(p.quarter);
				if (label !== quarterFilter) return false;
			}
			if (categoryFilter !== "All") {
				if (!p.category || p.category.toLowerCase() !== categoryFilter.toLowerCase()) {
					return false;
				}
			}
			return true;
		});
	}, [plays, quarterFilter, categoryFilter]);

	const grouped = useMemo(() => {
		const groups: { quarter: number; label: string; plays: GamePlay[] }[] = [];
		let currentQuarter: number | null = null;

		for (const play of filtered) {
			if (play.quarter !== currentQuarter) {
				currentQuarter = play.quarter;
				groups.push({
					quarter: play.quarter,
					label: getQuarterLabel(play.quarter),
					plays: [],
				});
			}
			groups[groups.length - 1].plays.push(play);
		}
		return groups;
	}, [filtered]);

	if (plays.length === 0) {
		return (
			<div className="py-8 text-center text-muted-foreground">
				No play-by-play data available for this game.
			</div>
		);
	}

	return (
		<div className="space-y-4 pt-4">
			<div className="flex flex-wrap gap-2">
				<div className="flex gap-1">
					{quarterButtons.map((label) => (
						<Button
							key={label}
							variant={quarterFilter === label ? "default" : "outline"}
							size="sm"
							onClick={() => setQuarterFilter(label)}
						>
							{label}
						</Button>
					))}
				</div>
				<div className="flex gap-1">
					{CATEGORY_FILTERS.map((cat) => (
						<Button
							key={cat}
							variant={categoryFilter === cat ? "default" : "outline"}
							size="sm"
							onClick={() => setCategoryFilter(cat)}
						>
							{cat}
						</Button>
					))}
				</div>
			</div>

			<div className="space-y-6">
				{grouped.map((group) => (
					<div key={group.quarter}>
						<h3 className="text-sm font-semibold text-muted-foreground mb-2 uppercase tracking-wide">
							{group.label}
						</h3>
						<div className="space-y-1">
							{group.plays.map((play) => (
								<PlayRow key={play.id} play={play} game={game} />
							))}
						</div>
					</div>
				))}
			</div>

			{filtered.length === 0 && (
				<div className="py-8 text-center text-muted-foreground">
					No plays match the selected filters.
				</div>
			)}
		</div>
	);
}

function PlayRow({ play, game }: { play: GamePlay; game: Game }) {
	const isHome = play.team_id === game.home_team_id;
	const teamName = isHome ? game.home_team_name : game.away_team_name;
	const scoreDisplay =
		play.home_score !== null && play.away_score !== null
			? `${play.away_score}-${play.home_score}`
			: null;

	return (
		<div className="flex items-start gap-3 py-1.5 px-2 rounded hover:bg-muted/50 text-sm">
			<span className="text-muted-foreground tabular-nums w-12 shrink-0">
				{formatTime(play.time_remaining)}
			</span>
			<span className="flex-1">
				<span className="font-medium">{play.play_type_name ?? play.play_type}</span>
				{play.player_id && play.player_name && (
					<>
						{" — "}
						<PlayerLink playerId={play.player_id}>
							{play.player_name}
						</PlayerLink>
					</>
				)}
				{play.secondary_player_name && (
					<span className="text-muted-foreground">
						{" "}
						({play.secondary_player_name})
					</span>
				)}
				{teamName && (
					<span className="text-muted-foreground"> &middot; {teamName}</span>
				)}
			</span>
			{scoreDisplay && (
				<span className="text-muted-foreground tabular-nums shrink-0">
					{scoreDisplay}
				</span>
			)}
		</div>
	);
}

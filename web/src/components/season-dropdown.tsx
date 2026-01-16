"use client";

import { useQuery } from "@tanstack/react-query";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { useSeasonStore } from "@/lib/stores/season-store";

interface Season {
	id: string;
}

async function fetchSeasons(): Promise<Season[]> {
	const response = await fetch("/api/seasons");
	if (!response.ok) {
		throw new Error("Failed to fetch seasons");
	}
	return response.json();
}

export function SeasonDropdown() {
	const { selectedSeason, setSelectedSeason } = useSeasonStore();

	const { data: seasons, isLoading } = useQuery({
		queryKey: ["seasons"],
		queryFn: fetchSeasons,
	});

	// Set default season to most recent when data loads
	if (seasons && seasons.length > 0 && !selectedSeason) {
		setSelectedSeason(seasons[0].id);
	}

	if (isLoading) {
		return <div className="h-9 w-24 animate-pulse rounded-md bg-muted" />;
	}

	if (!seasons || seasons.length === 0) {
		return null;
	}

	return (
		<Select
			value={selectedSeason || seasons[0].id}
			onValueChange={setSelectedSeason}
		>
			<SelectTrigger className="w-24">
				<SelectValue placeholder="Season" />
			</SelectTrigger>
			<SelectContent>
				{seasons.map((season) => (
					<SelectItem key={season.id} value={season.id}>
						{season.id}
					</SelectItem>
				))}
			</SelectContent>
		</Select>
	);
}

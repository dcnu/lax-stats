"use client";

import { useQueryStates, parseAsString } from "nuqs";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import type { Season } from "@/lib/types";

export function SeasonDivisionSelector({
	seasons,
	currentSeasonId,
}: {
	seasons: Season[];
	currentSeasonId: string;
}) {
	const [params, setParams] = useQueryStates(
		{
			season: parseAsString.withDefault(currentSeasonId),
			division: parseAsString.withDefault("1"),
		},
		{ shallow: false },
	);

	return (
		<div className="flex items-center gap-2">
			<Select
				value={params.season}
				onValueChange={(value) => setParams({ season: value })}
			>
				<SelectTrigger className="w-[120px] h-8">
					<SelectValue />
				</SelectTrigger>
				<SelectContent>
					{seasons.map((s) => (
						<SelectItem key={s.id} value={s.id}>
							{s.id}
						</SelectItem>
					))}
				</SelectContent>
			</Select>
		</div>
	);
}

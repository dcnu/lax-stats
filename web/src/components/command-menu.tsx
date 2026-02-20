"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
	CommandDialog,
	CommandEmpty,
	CommandGroup,
	CommandInput,
	CommandItem,
	CommandList,
} from "@/components/ui/command";

interface PlayerResult {
	player_id: number;
	player_name: string;
	team_name: string;
	season_id: string;
}

interface TeamResult {
	team_id: string;
	team_name: string;
	season_id: string;
}

interface SearchResults {
	players: PlayerResult[];
	teams: TeamResult[];
}

export function CommandMenu() {
	const [open, setOpen] = useState(false);
	const [query, setQuery] = useState("");
	const [results, setResults] = useState<SearchResults>({ players: [], teams: [] });
	const router = useRouter();
	const debounceRef = useRef<ReturnType<typeof setTimeout>>(null);

	useEffect(() => {
		function onKeyDown(e: KeyboardEvent) {
			if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
				e.preventDefault();
				setOpen((prev) => !prev);
			}
		}
		document.addEventListener("keydown", onKeyDown);
		return () => document.removeEventListener("keydown", onKeyDown);
	}, []);

	const search = useCallback((value: string) => {
		setQuery(value);
		if (debounceRef.current) clearTimeout(debounceRef.current);
		if (value.trim().length < 2) {
			setResults({ players: [], teams: [] });
			return;
		}
		debounceRef.current = setTimeout(async () => {
			const res = await fetch(`/api/search?q=${encodeURIComponent(value.trim())}`);
			if (res.ok) {
				setResults(await res.json());
			}
		}, 200);
	}, []);

	function select(url: string) {
		setOpen(false);
		setQuery("");
		setResults({ players: [], teams: [] });
		router.push(url);
	}

	return (
		<CommandDialog
			open={open}
			onOpenChange={setOpen}
			title="Search"
			description="Search for players and teams"
		>
			<CommandInput
				placeholder="Search players and teams..."
				value={query}
				onValueChange={search}
			/>
			<CommandList>
				<CommandEmpty>No results found.</CommandEmpty>
				{results.players.length > 0 && (
					<CommandGroup heading="Players">
						{results.players.map((p) => (
							<CommandItem
								key={`p-${p.player_id}-${p.season_id}`}
								value={`${p.player_name} ${p.team_name} ${p.season_id}`}
								onSelect={() => select(`/players/${p.player_id}`)}
							>
								<span className="flex-1 truncate">
									{p.player_name}
									<span className="text-muted-foreground"> - {p.team_name}</span>
								</span>
								<span className="text-muted-foreground text-xs">{p.season_id}</span>
							</CommandItem>
						))}
					</CommandGroup>
				)}
				{results.teams.length > 0 && (
					<CommandGroup heading="Teams">
						{results.teams.map((t) => (
							<CommandItem
								key={`t-${t.team_id}-${t.season_id}`}
								value={`${t.team_name} ${t.season_id}`}
								onSelect={() => select(`/teams/${t.team_id}?season=${t.season_id}`)}
							>
								<span className="flex-1 truncate">{t.team_name}</span>
								<span className="text-muted-foreground text-xs">{t.season_id}</span>
							</CommandItem>
						))}
					</CommandGroup>
				)}
			</CommandList>
		</CommandDialog>
	);
}

"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import {
	Collapsible,
	CollapsibleContent,
	CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { StatsTable } from "@/components/stats-table";
import { useSeasonStore } from "@/lib/stores/season-store";
import { ChevronDown, Copy, Check, Search } from "lucide-react";

interface QueryResult {
	data: Record<string, unknown>[];
	sql: string;
	description: string;
	columns: string[];
}

async function executeQuery(query: string, seasonId: string): Promise<QueryResult> {
	const response = await fetch("/api/query", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ query, seasonId }),
	});

	if (!response.ok) {
		const error = await response.json();
		throw new Error(error.message || "Query failed");
	}

	return response.json();
}

export function NaturalQueryInput() {
	const [query, setQuery] = useState("");
	const [sqlOpen, setSqlOpen] = useState(false);
	const [copied, setCopied] = useState(false);
	const { selectedSeason } = useSeasonStore();

	const mutation = useMutation({
		mutationFn: (q: string) => executeQuery(q, selectedSeason || "2025"),
	});

	function handleSubmit(e: React.FormEvent) {
		e.preventDefault();
		if (!query.trim()) return;
		mutation.mutate(query);
	}

	function handleCopySQL() {
		if (mutation.data?.sql) {
			navigator.clipboard.writeText(mutation.data.sql);
			setCopied(true);
			setTimeout(() => setCopied(false), 2000);
		}
	}

	return (
		<div className="space-y-6">
			<form onSubmit={handleSubmit} className="space-y-4">
				<Textarea
					placeholder="Ask a question... e.g., 'Who scored the most goals last week?' or 'Show me the top 10 scorers this season'"
					value={query}
					onChange={(e) => setQuery(e.target.value)}
					className="min-h-24 resize-none"
				/>
				<Button type="submit" disabled={mutation.isPending || !query.trim()}>
					<Search className="mr-2 h-4 w-4" />
					{mutation.isPending ? "Searching..." : "Search"}
				</Button>
			</form>

			{mutation.isError && (
				<Alert variant="destructive">
					<AlertDescription>{mutation.error.message}</AlertDescription>
				</Alert>
			)}

			{mutation.isPending && (
				<div className="space-y-4">
					<Skeleton className="h-4 w-3/4" />
					<Skeleton className="h-32 w-full" />
				</div>
			)}

			{mutation.isSuccess && mutation.data && (
				<div className="space-y-4">
					<p className="text-sm text-muted-foreground">
						{mutation.data.description}
					</p>

					<Collapsible open={sqlOpen} onOpenChange={setSqlOpen}>
						<CollapsibleTrigger asChild>
							<Button variant="ghost" size="sm" className="gap-2">
								<ChevronDown
									className={`h-4 w-4 transition-transform ${sqlOpen ? "rotate-180" : ""}`}
								/>
								{sqlOpen ? "Hide SQL" : "Show SQL"}
							</Button>
						</CollapsibleTrigger>
						<CollapsibleContent className="mt-2">
							<div className="relative">
								<pre className="rounded-md bg-muted p-4 text-sm overflow-x-auto">
									<code>{mutation.data.sql}</code>
								</pre>
								<Button
									variant="ghost"
									size="sm"
									className="absolute top-2 right-2"
									onClick={handleCopySQL}
								>
									{copied ? (
										<Check className="h-4 w-4" />
									) : (
										<Copy className="h-4 w-4" />
									)}
								</Button>
							</div>
						</CollapsibleContent>
					</Collapsible>

					{mutation.data.data.length > 0 ? (
						<StatsTable
							data={mutation.data.data}
							columns={mutation.data.columns}
						/>
					) : (
						<p className="text-sm text-muted-foreground">No results found.</p>
					)}
				</div>
			)}
		</div>
	);
}

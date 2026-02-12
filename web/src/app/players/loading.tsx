import { Skeleton } from "@/components/ui/skeleton";

export default function PlayersLoading() {
	return (
		<div className="space-y-6">
			<Skeleton className="h-8 w-48" />
			<div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
				<Skeleton className="h-10 w-64" />
				<div className="flex items-center gap-2">
					<Skeleton className="h-8 w-24" />
					<Skeleton className="h-8 w-24" />
				</div>
			</div>
			<div className="flex flex-wrap gap-2">
				<Skeleton className="h-10 w-[180px]" />
				<Skeleton className="h-10 w-[180px]" />
			</div>
			<div className="rounded-md border">
				<div className="space-y-2 p-4">
					{Array.from({ length: 15 }).map((_, i) => (
						<Skeleton key={i} className="h-8 w-full" />
					))}
				</div>
			</div>
		</div>
	);
}

import { Skeleton } from "@/components/ui/skeleton";

export default function PlayerDetailLoading() {
	return (
		<div className="space-y-6">
			<Skeleton className="h-4 w-48" />
			<div className="space-y-2">
				<Skeleton className="h-8 w-64" />
				<div className="flex gap-4">
					<Skeleton className="h-5 w-20" />
					<Skeleton className="h-5 w-32" />
					<Skeleton className="h-5 w-24" />
				</div>
			</div>
			<div className="space-y-2">
				<Skeleton className="h-6 w-32" />
				<div className="rounded-md border">
					<div className="space-y-2 p-4">
						{Array.from({ length: 4 }).map((_, i) => (
							<Skeleton key={i} className="h-8 w-full" />
						))}
					</div>
				</div>
			</div>
			<div className="space-y-2">
				<Skeleton className="h-6 w-32" />
				<div className="rounded-md border">
					<div className="space-y-2 p-4">
						{Array.from({ length: 10 }).map((_, i) => (
							<Skeleton key={i} className="h-8 w-full" />
						))}
					</div>
				</div>
			</div>
		</div>
	);
}

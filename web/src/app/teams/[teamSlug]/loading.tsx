import { Skeleton } from "@/components/ui/skeleton";

export default function TeamDetailLoading() {
	return (
		<div>
			<Skeleton className="h-4 w-48 mb-4" />
			<Skeleton className="h-8 w-64 mb-2" />
			<Skeleton className="h-5 w-24 mb-6" />
			<Skeleton className="h-9 w-72 mb-4" />
			<Skeleton className="h-96 w-full rounded-md" />
		</div>
	);
}

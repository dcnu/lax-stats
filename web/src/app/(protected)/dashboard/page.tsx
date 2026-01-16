import { NaturalQueryInput } from "@/components/natural-query-input";
import { DataPreview } from "@/components/data-preview";
import { Separator } from "@/components/ui/separator";

export default function DashboardPage() {
	return (
		<div className="container mx-auto px-4 py-8">
			<div className="max-w-6xl mx-auto space-y-8">
				<div className="space-y-2">
					<h2 className="text-2xl font-semibold tracking-tight">
						Query Statistics
					</h2>
					<p className="text-muted-foreground">
						Ask questions about NCAA lacrosse statistics in natural language
					</p>
				</div>
				<NaturalQueryInput />

				<Separator />

				<DataPreview />
			</div>
		</div>
	);
}

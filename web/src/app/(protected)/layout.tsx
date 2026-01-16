import { Navigation } from "@/components/navigation";

export default function ProtectedLayout({
	children,
}: {
	children: React.ReactNode;
}) {
	return (
		<div className="min-h-screen flex flex-col">
			<Navigation />
			<main className="flex-1">{children}</main>
		</div>
	);
}

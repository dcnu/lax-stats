import { redirect } from "next/navigation";

export default function Home() {
	// Go straight to dashboard (no auth for now)
	redirect("/dashboard");
}

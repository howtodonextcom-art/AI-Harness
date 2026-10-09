import { redirect } from "next/navigation";

/** The home page is the trading desk. The old research dashboard lives at /legacy. */
export default function Home() {
  redirect("/trade");
}

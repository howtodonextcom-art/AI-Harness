import type { Metadata } from "next";
import { JournalView } from "@/components/trade/JournalView";

export const metadata: Metadata = {
  title: "XAU EDGE — Journal (PAPER)",
};

export default function Page() {
  return <JournalView />;
}

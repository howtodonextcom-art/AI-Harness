import type { Metadata } from "next";
import { HypothesesView } from "@/components/research/HypothesesView";

export const metadata: Metadata = {
  title: "XAU EDGE — Giả thuyết",
};

export default function Page() {
  return <HypothesesView />;
}

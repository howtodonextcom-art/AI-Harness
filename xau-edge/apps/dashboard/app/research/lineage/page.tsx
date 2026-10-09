import type { Metadata } from "next";
import { LineageView } from "@/components/research/LineageView";

export const metadata: Metadata = {
  title: "XAU EDGE — Lineage",
};

export default function Page() {
  return <LineageView />;
}

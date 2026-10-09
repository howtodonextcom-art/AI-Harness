import type { Metadata } from "next";
import { OverviewView } from "@/components/research/OverviewView";

export const metadata: Metadata = {
  title: "XAU EDGE — Research Console",
};

export default function Page() {
  return <OverviewView />;
}

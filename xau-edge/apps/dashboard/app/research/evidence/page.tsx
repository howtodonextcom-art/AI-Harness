import type { Metadata } from "next";
import { EvidenceView } from "@/components/research/EvidenceView";

export const metadata: Metadata = {
  title: "XAU EDGE — Bằng chứng",
};

export default function Page() {
  return <EvidenceView />;
}

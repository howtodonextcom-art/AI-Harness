import type { Metadata } from "next";
import { CandidatesView } from "@/components/research/CandidatesView";

export const metadata: Metadata = {
  title: "XAU EDGE — Ứng viên",
};

export default function Page() {
  return <CandidatesView />;
}

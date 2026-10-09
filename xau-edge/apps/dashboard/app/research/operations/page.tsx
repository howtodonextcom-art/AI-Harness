import type { Metadata } from "next";
import { OperationsView } from "@/components/research/OperationsView";

export const metadata: Metadata = {
  title: "XAU EDGE — Vận hành",
};

export default function Page() {
  return <OperationsView />;
}

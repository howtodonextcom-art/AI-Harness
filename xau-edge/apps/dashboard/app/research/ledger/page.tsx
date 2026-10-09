import type { Metadata } from "next";
import { LedgerView } from "@/components/research/LedgerView";

export const metadata: Metadata = {
  title: "XAU EDGE — Ledger & K",
};

export default function Page() {
  return <LedgerView />;
}

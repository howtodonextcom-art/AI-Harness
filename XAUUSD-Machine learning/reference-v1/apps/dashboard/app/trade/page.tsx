import type { Metadata } from "next";
import { TerminalView } from "@/components/terminal/TerminalView";

export const metadata: Metadata = {
  title: "XAU EDGE — Terminal giao dịch PAPER (XAUUSD)",
};

export default function Page() {
  return <TerminalView />;
}

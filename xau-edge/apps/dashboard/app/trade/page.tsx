import type { Metadata } from "next";
import { TradeView } from "@/components/trade/TradeView";

export const metadata: Metadata = {
  title: "XAU EDGE — Trade (PAPER, FTMO DEMO data)",
};

export default function Page() {
  return <TradeView />;
}

import type { Metadata } from "next";
import { MarketView } from "@/components/market/MarketView";

export const metadata: Metadata = {
  title: "XAU EDGE — Market (FTMO MT5)",
};

export default function Page() {
  return <MarketView />;
}

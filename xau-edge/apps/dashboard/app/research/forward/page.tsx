import type { Metadata } from "next";
import { ForwardView } from "@/components/research/ForwardView";

export const metadata: Metadata = {
  title: "XAU EDGE — Forward & vòng đời",
};

export default function Page() {
  return <ForwardView />;
}

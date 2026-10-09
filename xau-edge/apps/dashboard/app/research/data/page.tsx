import type { Metadata } from "next";
import { DataView } from "@/components/research/DataView";

export const metadata: Metadata = {
  title: "XAU EDGE — Dữ liệu & khóa",
};

export default function Page() {
  return <DataView />;
}

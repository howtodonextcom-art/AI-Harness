import type { Metadata } from "next";
import { ControlPanel } from "@/components/ControlPanel";

export const metadata: Metadata = {
  title: "XAU EDGE — Điều khiển",
};

export default function ControlPage() {
  return <ControlPanel />;
}

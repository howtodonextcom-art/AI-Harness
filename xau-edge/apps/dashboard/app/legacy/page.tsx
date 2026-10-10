import type { Metadata } from "next";
import { Dashboard } from "@/components/Dashboard";

export const metadata: Metadata = {
  title: "XAU EDGE — Legacy research dashboard (deprecated)",
};

/** The old probability dashboard: it reads the legacy research store (data/raw), NOT live data. */
export default function Page() {
  return (
    <>
      <div role="alert" data-testid="legacy-banner" className="border-b border-amber-600 bg-amber-500/15 px-4 py-2 text-sm text-amber-800 dark:text-amber-200">
        LEGACY / NOT ACTIVE — trang cũ (deprecated): bot DEMO cũ bị KHÓA, dữ liệu lấy từ kho nghiên cứu data/raw, có thể đã cũ nhiều tháng. Đừng dùng để giao dịch — hãy dùng <a href="/trade" className="underline">/trade</a>.
      </div>
      <Dashboard />
    </>
  );
}

import { EVIDENCE_CLASSES, type EvidenceClass } from "@/lib/research";

/**
 * The ONE component that shows an evidence class. Colour AND the text label carry the meaning, and
 * no class uses green: SCREENING (dashed amber) is a first filter, never a pass.
 */
const STYLE: Record<EvidenceClass, { cls: string; hint: string }> = {
  DESCRIPTIVE: {
    cls: "border-slate-500 bg-slate-500/10 text-slate-800 dark:text-slate-200",
    hint: "Mô tả dữ liệu, không kiểm định giả thuyết",
  },
  EXPLORATORY: {
    cls: "border-violet-600 bg-violet-500/10 text-violet-900 dark:text-violet-200",
    hint: "Khám phá: tạo giả thuyết, chưa phải bằng chứng",
  },
  SCREENING: {
    cls: "border-amber-600 border-dashed bg-amber-500/15 text-amber-900 dark:text-amber-200",
    hint: "Sàng lọc bước đầu (Stage 1): KHÔNG phải bằng chứng, không phải PASS",
  },
  VALIDATION: {
    cls: "border-sky-600 bg-sky-500/10 text-sky-900 dark:text-sky-200",
    hint: "Kiểm định trên dữ liệu validation đã đăng ký trước",
  },
  CONFIRMATORY: {
    cls: "border-indigo-600 bg-indigo-500/10 text-indigo-900 dark:text-indigo-200",
    hint: "Xác nhận trên Test-H (chạy một lần)",
  },
  HOLDOUT: {
    cls: "border-fuchsia-600 bg-fuchsia-500/10 text-fuchsia-900 dark:text-fuchsia-200",
    hint: "Holdout cuối cùng (chạy một lần)",
  },
  PROSPECTIVE: {
    cls: "border-teal-600 bg-teal-500/10 text-teal-900 dark:text-teal-200",
    hint: "Tiền cứu: tín hiệu niêm phong trước kết quả",
  },
  EXECUTION: {
    cls: "border-orange-600 bg-orange-500/10 text-orange-900 dark:text-orange-200",
    hint: "Thực thi: chi phí và độ trễ thật, không phải edge",
  },
};

const GLYPH: Record<EvidenceClass, string> = {
  DESCRIPTIVE: "◇",
  EXPLORATORY: "◈",
  SCREENING: "▽",
  VALIDATION: "◆",
  CONFIRMATORY: "■",
  HOLDOUT: "▣",
  PROSPECTIVE: "▷",
  EXECUTION: "⚙",
};

export function EvidenceBadge({ cls }: { cls: string | null | undefined }) {
  const known = (EVIDENCE_CLASSES as string[]).includes(cls ?? "");
  if (!known) {
    return (
      <span
        data-evidence-class="UNKNOWN"
        title="Lớp bằng chứng không rõ"
        className="inline-block max-w-full rounded border border-dashed border-amber-500 bg-amber-500/10 px-1.5 py-0.5 text-xs font-semibold text-amber-900 dark:text-amber-200"
      >
        KHÔNG RÕ (lớp bằng chứng)
      </span>
    );
  }
  const c = cls as EvidenceClass;
  return (
    <span
      data-evidence-class={c}
      title={STYLE[c].hint}
      className={`inline-flex max-w-full items-center gap-1 whitespace-nowrap rounded border-2 px-1.5 py-0.5 text-xs font-bold tracking-wide ${STYLE[c].cls}`}
    >
      <span aria-hidden="true">{GLYPH[c]}</span>
      <span>{c}</span>
      <span className="sr-only"> — {STYLE[c].hint}</span>
    </span>
  );
}

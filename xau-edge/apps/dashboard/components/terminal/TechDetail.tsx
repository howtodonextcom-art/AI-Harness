/** The internal code behind a human sentence: available, never in front. */
export function TechDetail({ code, children }: { code: string; children?: React.ReactNode }) {
  return (
    <details data-testid="tech-detail" className="mt-0.5 text-xs">
      <summary className="inline cursor-pointer text-slate-600 underline decoration-dotted dark:text-slate-400">Chi tiết kỹ thuật</summary>
      <span className="ml-2 font-mono">{code}</span>
      {children}
    </details>
  );
}

/** "12 giây" / "4 phút" / "3 giờ" / "2 ngày" from seconds. */
export function ago(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return "không rõ";
  const s = Math.max(0, Math.round(seconds));
  if (s < 90) return `${s} giây`;
  if (s < 5400) return `${Math.round(s / 60)} phút`;
  if (s < 129600) return `${Math.round(s / 3600)} giờ`;
  return `${Math.round(s / 86400)} ngày`;
}

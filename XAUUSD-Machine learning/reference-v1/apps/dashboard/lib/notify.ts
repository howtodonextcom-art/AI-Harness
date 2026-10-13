/**
 * "A setup is ready" signal for the trader who is not staring at the page: the tab title, a browser
 * notification (when permitted) and an optional short beep. It only informs; it never trades.
 */

export const BASE_TITLE = "XAU EDGE — Terminal giao dịch PAPER (XAUUSD)";

export function readyTitle(side: "BUY" | "SELL", entry: number | null): string {
  return `${side === "BUY" ? "▲ MUA" : "▼ BÁN"} SẴN SÀNG${entry === null ? "" : ` @ ${entry.toFixed(2)}`} · XAUUSD`;
}

/** True only for a setup this page has not announced yet (one announcement per setup, per page load). */
export function isNewSetup(seen: Set<string>, setupId: string): boolean {
  if (seen.has(setupId)) return false;
  seen.add(setupId);
  return true;
}

export function beep(): void {
  try {
    const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.frequency.value = 880;
    gain.gain.value = 0.08;
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.25);
    osc.onended = () => void ctx.close();
  } catch {
    /* audio unavailable: the title and the notification are enough */
  }
}

export function systemNotify(title: string, body: string): void {
  try {
    if ("Notification" in window && Notification.permission === "granted") new Notification(title, { body });
  } catch {
    /* optional */
  }
}

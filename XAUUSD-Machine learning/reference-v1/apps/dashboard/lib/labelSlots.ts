/**
 * Label slot allocator for the system trade-plan overlay.
 *
 * Pure and always terminating: every label is tried at its own height, then at growing offsets below and above it
 * (inside [lo, hi]); a label with no free slot is dropped (its line stays). Labels are placed best-priority first, so
 * the plan's Entry/SL/TP1 keep their text and the weaker ones move or yield. `maxShift` bounds how far from its own
 * height a label may sit.
 */
export interface SlotRequest {
  id: string;
  y: number;
  /** lower number = placed first = keeps its slot */
  priority: number;
}

export function allocateLabelSlots(
  requests: SlotRequest[],
  lo: number,
  hi: number,
  gap = 16,
  maxShift = Number.POSITIVE_INFINITY,
): Map<string, number> {
  const out = new Map<string, number>();
  if (!(hi >= lo) || !(gap > 0)) return out;
  const taken: number[] = [];
  const free = (y: number) => y >= lo && y <= hi && taken.every((t) => Math.abs(t - y) >= gap);
  const ordered = [...requests].sort((a, b) => a.priority - b.priority || a.y - b.y);
  const maxSteps = Math.ceil((hi - lo) / gap) + 1;
  for (const r of ordered) {
    if (!Number.isFinite(r.y)) continue;
    const start = Math.min(hi, Math.max(lo, r.y));
    let placed: number | null = null;
    for (let step = 0; step <= maxSteps && placed === null; step++) {
      const candidates = step === 0 ? [start] : [start + step * gap, start - step * gap];
      // a label that has to move far from its line would name the wrong place: it yields instead
      placed = candidates.find((y) => Math.abs(y - start) <= maxShift && free(y)) ?? null;
    }
    if (placed !== null) {
      taken.push(placed);
      out.set(r.id, placed);
    }
  }
  return out;
}

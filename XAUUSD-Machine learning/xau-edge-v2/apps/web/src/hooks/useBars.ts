import { useCallback, useEffect, useRef, useState } from "react";
import { fetchBars } from "../api/client";
import { type ChartBar, type Tf, mergeBars, toChartBar } from "../chart/bars";

const FIRST_PAGE = 500;
const OLDER_PAGE = 1000;

export interface BarsState {
  /** Closed bars, strictly increasing, no duplicates. */
  bars: ChartBar[];
  hasMoreBefore: boolean;
  loading: boolean;
  error: string | null;
  /** Bumped when the first page of a (new) timeframe is in: the chart refits itself. */
  generation: number;
  oldest: string | null;
  newest: string | null;
  loadOlder: () => void;
}

/**
 * History of one timeframe. The first page is the newest bars; `loadOlder` fetches the page before
 * the oldest loaded bar (`before=`), so scrolling left reaches the start of the store, 1000 bars at
 * a time. A response for a timeframe the user already left is discarded.
 */
export function useBars(timeframe: Tf, dataVersion: string | null): BarsState {
  const [state, setState] = useState<Omit<BarsState, "loadOlder">>({
    bars: [], hasMoreBefore: false, loading: true, error: null, generation: 0, oldest: null, newest: null,
  });
  const token = useRef(0);
  const current = useRef(state);
  current.current = state;

  useEffect(() => {
    const mine = ++token.current;
    const abort = new AbortController();
    setState((s) => ({ ...s, bars: [], loading: true, error: null, hasMoreBefore: false }));
    fetchBars(timeframe, FIRST_PAGE, null, abort.signal)
      .then((page) => {
        if (mine !== token.current) return;
        const bars = mergeBars([], page.bars.map(toChartBar));
        setState((s) => ({
          bars, hasMoreBefore: page.has_more_before, loading: false, error: null,
          generation: s.generation + 1, oldest: page.oldest_available ?? null, newest: page.newest_available ?? null,
        }));
      })
      .catch((e: unknown) => {
        if (abort.signal.aborted || mine !== token.current) return;
        setState((s) => ({ ...s, loading: false, error: e instanceof Error ? e.message : String(e) }));
      });
    return () => abort.abort();
  }, [timeframe]);

  // a stored bar was added: merge the newest few bars, keep everything the user scrolled to
  const seen = useRef<string | null>(dataVersion);
  useEffect(() => {
    if (dataVersion === null || seen.current === dataVersion) return;
    const first = seen.current === null; // the first version we hear of is the one we loaded with
    seen.current = dataVersion;
    if (first) return;
    const mine = token.current;
    fetchBars(timeframe, 10, null)
      .then((page) => {
        if (mine !== token.current) return;
        setState((s) => ({
          ...s,
          bars: mergeBars(s.bars, page.bars.map(toChartBar)),
          newest: page.newest_available ?? s.newest,
        }));
      })
      .catch(() => undefined); // the next event retries; the chart keeps what it has
  }, [timeframe, dataVersion]);

  const loadOlder = useCallback(() => {
    const now = current.current;
    const first = now.bars[0];
    if (now.loading || !now.hasMoreBefore || first === undefined) return;
    const mine = token.current;
    setState((s) => ({ ...s, loading: true }));
    fetchBars(timeframe, OLDER_PAGE, new Date(first.time * 1000).toISOString())
      .then((page) => {
        if (mine !== token.current) return;
        setState((s) => ({
          ...s,
          bars: mergeBars(s.bars, page.bars.map(toChartBar)),
          hasMoreBefore: page.has_more_before && page.bars.length > 0,
          loading: false,
          error: null,
        }));
      })
      .catch((e: unknown) => {
        if (mine !== token.current) return;
        setState((s) => ({ ...s, loading: false, error: e instanceof Error ? e.message : String(e) }));
      });
  }, [timeframe]);

  return { ...state, loadOlder };
}

import { useCallback, useEffect, useRef, useState } from "react";
import {
  type FormingBar,
  type Intelligence,
  type PaperPosition,
  type PaperSummary,
  type Health,
  type Quote,
  type State,
  type WsEvent,
  fetchForming,
  fetchIntelligence,
  fetchPaperPositions,
  fetchPaperSummary,
  fetchHealth,
  fetchState,
} from "../api/client";

export type WsStatus = "connecting" | "open" | "retrying";

export interface Live {
  state: State | null;
  /** Market description, scenarios and the layered reason the strategy waits (authority NONE). */
  intel: Intelligence | null;
  health: Health | null;
  error: string | null;
  ws: WsStatus;
  retries: number;
  gaps: number;
  quote: Quote | null;
  /** Still-open bar per timeframe, from the collector (empty until the first live event). */
  forming: Record<string, FormingBar["bar"]>;
  /** Changes whenever a stored bar is added; the chart refetches its newest bars on change. */
  dataVersion: string | null;
  paper: PaperSummary | null;
  positions: PaperPosition[];
  /** Bumped whenever the server says a paper position opened or closed. */
  paperRevision: number;
  /** Bumped whenever the server says a human decision was recorded. */
  humanRevision: number;
  /** Refetch everything now (after a paper action). */
  reload: () => void;
}

const formingMap = (bars: readonly FormingBar[]): Record<string, FormingBar["bar"]> =>
  Object.fromEntries(bars.map((b) => [b.timeframe, b.bar]));

const HEALTH_REFRESH_MS = 15_000;
const INTEL_REFRESH_MS = 4_000;
const BACKOFF_MS = [1000, 2000, 4000, 8000, 15000, 30000];

/** State + health over REST, kept fresh by a WebSocket whose `seq` reveals any missed event. */
export function useLive(): Live {
  const [live, setLive] = useState<Live>({
    state: null, intel: null, health: null, error: null, ws: "connecting", retries: 0, gaps: 0,
    quote: null, forming: {}, dataVersion: null, paper: null, positions: [], paperRevision: 0, humanRevision: 0, reload: () => undefined,
  });
  const lastSeq = useRef<number | null>(null);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    try {
      const [state, health] = await Promise.all([fetchState(signal), fetchHealth(signal)]);
      setLive((l) => ({ ...l, state, health, error: null }));
      void Promise.all([fetchPaperSummary(signal), fetchPaperPositions(signal)])
        .then(([paper, list]) => setLive((l) => ({ ...l, paper, positions: list.positions })))
        .catch(() => undefined); // paper numbers are shown when available, never invented
      void fetchIntelligence(signal)
        .then((intel) => setLive((l) => ({ ...l, intel })))
        .catch(() => undefined); // the description is extra; the strategy state is the truth
      void fetchForming(signal)
        .then((f) => setLive((l) => ({ ...l, forming: formingMap(f.bars) })))
        .catch(() => undefined); // the forming bar is a nicety; the closed history is the truth
    } catch (e) {
      if (signal?.aborted) return;
      setLive((l) => ({ ...l, error: e instanceof Error ? e.message : String(e) }));
    }
  }, []);

  useEffect(() => {
    const abort = new AbortController();
    void refresh(abort.signal);
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") void refresh();
    }, HEALTH_REFRESH_MS);
    const intelTimer = setInterval(() => {
      if (document.visibilityState !== "visible") return;
      void fetchIntelligence()
        .then((intel) => setLive((l) => ({ ...l, intel })))
        .catch(() => undefined);
    }, INTEL_REFRESH_MS);
    return () => {
      abort.abort();
      clearInterval(timer);
      clearInterval(intelTimer);
    };
  }, [refresh]);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;
    let closed = false;

    const connect = () => {
      const scheme = location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${scheme}://${location.host}/ws`);
      socket.onmessage = (message: MessageEvent<string>) => {
        const event = JSON.parse(message.data) as WsEvent;
        setLive((l) => (l.dataVersion === event.data_version ? l : { ...l, dataVersion: event.data_version }));
        if (event.type === "hello") {
          attempts = 0;
          lastSeq.current = event.seq;
          setLive((l) => ({ ...l, ws: "open", retries: 0 }));
          void refresh(); // (re)connected: never trust what was missed meanwhile
          return;
        }
        const expected = (lastSeq.current ?? event.seq - 1) + 1;
        lastSeq.current = event.seq;
        if (event.seq !== expected) {
          setLive((l) => ({ ...l, gaps: l.gaps + 1 }));
          void refresh();
          return;
        }
        if (event.type === "live") {
          setLive((l) => ({ ...l, quote: event.quote ?? l.quote, forming: formingMap(event.forming ?? []) }));
        } else if (event.type === "paper") {
          setLive((l) => ({ ...l, paperRevision: l.paperRevision + 1 }));
          void refresh();
        } else if (event.type === "human") {
          setLive((l) => ({ ...l, humanRevision: l.humanRevision + 1 }));
          void refresh();
        } else if (event.type === "state") {
          void refresh(); // the decision changed on the server: fetch it
        }
      };
      socket.onclose = () => {
        if (closed) return;
        const wait = BACKOFF_MS[Math.min(attempts, BACKOFF_MS.length - 1)] ?? 30000;
        attempts += 1;
        setLive((l) => ({ ...l, ws: "retrying", retries: attempts }));
        retry = setTimeout(connect, wait);
      };
    };
    connect();
    return () => {
      closed = true;
      clearTimeout(retry);
      socket?.close();
    };
  }, [refresh]);

  const reload = useCallback(() => void refresh(), [refresh]);
  return { ...live, reload };
}

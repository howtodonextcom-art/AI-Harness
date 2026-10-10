/**
 * Compile-time half of the backend <-> frontend contract. Each golden is a REAL serialization from
 * the backend (see `scripts/generate_trade_goldens.py`); `satisfies` fails `tsc` when a field that
 * `lib/trade.ts` requires is missing from it (a renamed or dropped backend field). The Python test
 * `tests/unit/trading/test_contract_goldens.py` covers the other direction (backend vs golden).
 */

import type { JournalResponse, TradeView } from "@/lib/trade";
import buy from "./golden/buy.json";
import closedPaper from "./golden/closed_paper.json";
import journalClosed from "./golden/journal_closed.json";
import openPaper from "./golden/open_paper.json";
import sell from "./golden/sell.json";
import wait from "./golden/wait.json";

/** What JSON can say about T: string unions become string, everything else keeps its shape. */
type Json<T> = T extends string
  ? string
  : T extends number
    ? number
    : T extends boolean
      ? boolean
      : T extends null | undefined
        ? T
        : T extends readonly (infer U)[]
          ? Json<U>[]
          : T extends object
            ? { [K in keyof T]: Json<T[K]> }
            : T;

export const GOLDEN_VIEWS = {
  wait: wait satisfies Json<TradeView>,
  buy: buy satisfies Json<TradeView>,
  sell: sell satisfies Json<TradeView>,
  openPaper: openPaper satisfies Json<TradeView>,
  closedPaper: closedPaper satisfies Json<TradeView>,
};
export const GOLDEN_JOURNAL = journalClosed satisfies Json<JournalResponse>;

import { ChartPanel } from "./components/ChartPanel";
import { AutoPaperStrip } from "./components/AutoPaperStrip";
import { Drawers } from "./components/Drawers";
import { HumanPanel } from "./components/HumanPanel";
import { MtfStrip } from "./components/MtfStrip";
import { SystemPanel } from "./components/SystemPanel";
import { TopBar } from "./components/TopBar";
import { useLive } from "./hooks/useLive";

export function App() {
  const live = useLive();
  return (
    <div className="app">
      <div className="head">
        <TopBar live={live} />
        {live.error && (
          <p className="banner" role="alert" data-testid="api-error">
            Không đọc được API: {live.error}
          </p>
        )}
      </div>
      <main className="main">
        <div className="left" data-testid="left-col">
        <ChartPanel
          state={live.state}
          quote={live.quote}
          forming={live.forming}
          dataVersion={live.dataVersion}
          positions={live.positions}
        />
        <AutoPaperStrip paper={live.paper} positions={live.positions} />
        </div>
        <aside className="stack" aria-label="Hệ thống và quyết định của bạn">
          <SystemPanel state={live.state} intel={live.intel} />
          <HumanPanel state={live.state} onChanged={live.reload} />
        </aside>
      </main>
      <MtfStrip health={live.health} state={live.state} />
      <Drawers
        state={live.state}
        intel={live.intel}
        health={live.health}
        paper={live.paper}
        positions={live.positions}
        paperRevision={live.paperRevision}
        humanRevision={live.humanRevision}
        onPaperChanged={live.reload}
      />
    </div>
  );
}

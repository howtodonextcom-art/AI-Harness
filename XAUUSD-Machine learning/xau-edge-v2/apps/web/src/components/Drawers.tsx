import type { Health, PaperPosition, PaperSummary, State } from "../api/client";
import { EvidencePanel } from "./EvidencePanel";
import { ModelPanel } from "./ModelPanel";
import { PaperJournal } from "./PaperJournal";
import { DRAWERS, type Drawer, useDrawer } from "../hooks/useHash";

const TITLE: Record<Drawer, string> = {
  journal: "Nhật ký",
  evidence: "Bằng chứng",
  data: "Sức khỏe dữ liệu",
  model: "Mô hình",
};

function DataHealth({ health }: { health: Health | null }) {
  if (!health) return <p className="muted">Đang tải…</p>;
  return (
    <div>
      <p data-testid="health-status">
        Trạng thái: <strong>{health.status}</strong> · chạy được {Math.round(health.uptime_s)} giây · phiên bản{" "}
        {health.version}
      </p>
      <ul className="checks">
        {health.checks.map((c) => (
          <li key={c.id} data-state={c.state}>
            <strong>{c.label}</strong>: {c.state} · {c.detail}
          </li>
        ))}
      </ul>
    </div>
  );
}

interface Props {
  state: State | null;
  health: Health | null;
  paper: PaperSummary | null;
  positions: PaperPosition[];
  paperRevision: number;
  humanRevision: number;
  onPaperChanged: () => void;
}

export function Drawers({ state, health, paper, positions, paperRevision, humanRevision, onPaperChanged }: Props) {
  const [open, setOpen] = useDrawer();
  return (
    <section className="drawers" aria-label="Ngăn kéo thông tin" data-testid="drawers">
      <div role="tablist" aria-label="Ngăn kéo">
        {DRAWERS.map((d) => (
          <button
            key={d}
            role="tab"
            id={`tab-${d}`}
            aria-selected={open === d}
            aria-controls={`panel-${d}`}
            onClick={() => setOpen(open === d ? null : d)}
          >
            {TITLE[d]}
          </button>
        ))}
      </div>
      {open && (
        <div role="tabpanel" id={`panel-${open}`} aria-labelledby={`tab-${open}`} className="panel" data-testid="drawer-panel">
          {open === "journal" && (
            <PaperJournal
              summary={paper}
              positions={positions}
              state={state}
              revision={paperRevision}
              humanRevision={humanRevision}
              onChanged={onPaperChanged}
            />
          )}
          {open === "evidence" && <EvidencePanel state={state} revision={paperRevision} />}
          {open === "data" && <DataHealth health={health} />}
          {open === "model" && <ModelPanel />}
        </div>
      )}
    </section>
  );
}

# Luồng chạy từ dữ liệu đến lệnh (end-to-end)

> Trạng thái tại 2026-10-08. Nút đỏ là chỗ chuỗi bị đứt. Nút cam là phần mới làm một nửa, hoặc mới chỉ test bằng fake/mock.

```mermaid
flowchart TD
 A["MT5 DEMO terminal - bars M5 M15 H1 H4"] --> B["refresh_market_data - closed bars only"]
 B --> C["RawStore + DatasetCatalog + validate_bars"]
 C --> D["Features, structure, regime, pattern analogues"]
 D --> E["Outcome stats - uncalibrated frequencies"]
 N["News calendar CSV - CHUA CO DU LIEU"] -.-> F
 R["Experiment registry - Baseline C FAIL"] -.-> G
 E --> F["decide - 12 refusal reasons"]
 G["Evidence gate - bound to Baseline C"] --> F
 F -->|"luon WAIT hien tai"| H["SignalBridge - kill switch, idempotency, RiskEngine, ExecutionSafety"]
 S["DemoReader snapshot + Reconciler"] --> H
 H --> I["OrderIntent - entry = bid close, SL TP chua lam tron"]
 I --> J["Mt5DemoExecutor - gates, order_check, order_send"]
 J -.->|"chua tung chay that"| K["MT5 DEMO account"]
 J --> L["state.sqlite, journal.jsonl, cycles.jsonl"]
 L --> M["status.json, heartbeat.json"]
 M --> P["check_health.py - chi ghi file va exit code"]
 M --> Q["Read-only API /bot + Dashboard"]
 P -.-> T["Push alert, supervisor, auto-restart - CHUA CO"]
 LIVE["Live account"] -.-x J

 classDef broken fill:#ffd6d6,stroke:#c00,color:#000
 classDef partial fill:#fff1cc,stroke:#d90,color:#000
 class N,R,T,LIVE broken
 class G,I,J,K,P partial
```

## Trạng thái từng mắt xích

| Mắt xích | Trạng thái | Bằng chứng |
|---|---|---|
| Dữ liệu tới tín hiệu | Chạy trên dữ liệu thật | `data/execution/cycles.jsonl` có 8 dòng, `data_age` từ 0,33 đến 8 phút |
| Tín hiệu tới bridge | Bị chặn: mọi chu kỳ đều `WAIT` | Lý do trong journal: `NO_VALIDATED_EDGE`, `NEWS_UNKNOWN` |
| Tin tức | Đứt: không có dữ liệu | `.env` không có `XAU_EDGE_NEWS_CALENDAR_PATH`; `news/calendar.py:1-6` |
| Executor tới MT5 | Chỉ test với fake | `docs/reports/demo-bot-status.md:25-29`; `.env` không có `MT5_TRADE_PASSWORD` |
| Live | Chặn có chủ đích | `config.py:49-58`; `brokers/mt5_demo/reader.py:89-91` |
| Giám sát | Chỉ ghi file | `scripts/check_health.py:44-49` |

## Các lỗi nằm trên luồng

- **Evidence gate** bị gắn cứng vào Baseline C, chiến lược đã trượt tiêu chí (`signals/engine.py:53-57`).
- **OrderIntent** lấy giá vào lệnh là giá close M15 (bid), trong khi executor so với ask và chỉ cho lệch 30 point, nhỏ hơn spread trung vị 31 point. Vì vậy lệnh BUY gần như luôn bị từ chối (`executor.py:288-293`).
- **SL/TP** không được làm tròn theo `digits` (`decision.py:166-167`).
- **Vòng lặp** không bắt `RuntimeError` khi mất kết nối MT5, nên tiến trình thoát hẳn (`scripts/demo_trader.py`).

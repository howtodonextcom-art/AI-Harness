# Rubrics — cố định TRƯỚC khi chấm (2026-10-11 09:35 GMT+7)

Bản gốc: `%TEMP%\xau_cons\rubrics.md`. Check-in để santa có thể kiểm S3.

Scale 1..5. Weighted = sum(w*s). Nhãn A/B/C và P/Q/R xáo; reviewer không biết bản nào là hiện tại / được ưa.

## (a) Two-brain
A1 0.25 single source · A2 0.25 safety · A3 0.20 evidence · A4 0.15 cost · A5 0.15 reversibility.
PASS: weighted ≥ 3.5 AND A2 ≥ 4.

## (b) Data store
B1 0.30 one store · B2 0.25 reproducibility · B3 0.20 PIT · B4 0.15 cost · B5 0.10 reversibility.
PASS: ≥ 3.5 AND B2 ≥ 4.

## (c) TradingSignal
C1 0.30 coverage · C2 0.25 executor as-is · C3 0.20 compat · C4 0.15 testable · C5 0.10 cost.
PASS: ≥ 3.5 AND C2 ≥ 4.

## (d) /trade 5-second
D1 0.30 P0 count · D2 0.20 honesty · D3 0.15 clarity · D4 0.15 noise · D5 0.10 cost · D6 0.10 no redesign.
PASS: ≥ 3.5 AND D2 ≥ 4.

## (e) Hypothesis families
E1 0.30 Dev evidence · E2 0.25 testable/K · E3 0.20 leakage · E4 0.15 econ · E5 0.10 cost.
Keep only if weighted ≥ 3.5 AND E1 ≥ 3.

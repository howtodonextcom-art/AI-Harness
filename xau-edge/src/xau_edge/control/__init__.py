"""Local web control plane (ADR-0023): preflight, bot lifecycle, DRY-RUN/DEMO mode, smoke, flatten.

Nothing in this package can select FUNDED or LIVE, reset the kill switch, edit ``.env`` or take
order parameters. Order sending reuses the demo executor (``brokers/mt5_demo``) unchanged.
"""

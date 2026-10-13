# Autostart tasks removed on 2026-10-14

The owner asked to stop programs that start by themselves when Windows opens. Three Task Scheduler tasks were deleted (no XML backup was written: the export step failed on a path error before the deletion ran; the definitions below come from a read before deleting).

| Task | Trigger | Action |
|---|---|---|
| XAU-EDGE Market Stack | at logon | powershell start_market_stack.ps1 -WaitSeconds 30 -Dashboard (xau-edge) |
| XAU-EDGE-V2-Service | at logon | powershell scripts\service\run_v2.ps1 (xau-edge-v2) |
| XAU-EDGE-V2-Watchdog | time trigger (interval not recorded) | pythonw scripts\external_watchdog.py (xau-edge-v2) |

To bring them back, run the project's own installers (they recreate the tasks): `scripts\install_market_autostart.ps1` in xau-edge, `scripts\service\install_autostart.ps1` in xau-edge-v2.

The FTMO MT5 Terminal was also uninstalled at the owner's request. Nothing in the repo registers an autostart for it any more.

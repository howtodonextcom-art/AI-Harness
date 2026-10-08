"""The NSSM installer must parse and keep its safety switches (it is never executed here)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "install_services.ps1"
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")

PARSE = (
    "$e=$null;$t=$null;"
    "[void][System.Management.Automation.Language.Parser]::ParseFile($env:PS1_UNDER_TEST,[ref]$t,[ref]$e);"
    "if($e.Count){$e|ForEach-Object{$_.Message};exit 1}"
)


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is not installed")
def test_script_parses_without_errors() -> None:
    assert POWERSHELL is not None
    done = subprocess.run(  # noqa: S603 - fixed argv, parse only, the script is never run
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", PARSE],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "PS1_UNDER_TEST": str(SCRIPT)},
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr


def test_script_keeps_its_safety_switches() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "SupportsShouldProcess" in text  # -WhatIf dry run
    assert "[switch]$Uninstall" in text
    assert "SERVICE_DELAYED_AUTO_START" in text
    assert "AppExit" in text
    assert "AppRotateFiles" in text

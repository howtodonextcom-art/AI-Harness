# A1: start the SEPARATE portable FTMO terminal (a copy of the program folder, its own empty data folder).
# It never touches the terminal that runs the collector. Manual steps (the account is the owner's):
#   1. File > Login to Trade Account > choose server FTMO-Demo > enter the demo login.   (NOT stored by any script)
#   2. Tools > Options > Charts > Max bars in chart = Unlimited > OK, then restart this portable terminal.
#   3. run:  <V1>\.venv\Scripts\python.exe scripts\research\a1_probe.py --terminal D:\XAU-EDGE-V2-A1\ftmo-portable\terminal64.exe
$exe = 'D:\XAU-EDGE-V2-A1\ftmo-portable\terminal64.exe'
if (-not (Test-Path $exe)) { throw "portable copy missing: $exe" }
Start-Process -FilePath $exe -ArgumentList '/portable'

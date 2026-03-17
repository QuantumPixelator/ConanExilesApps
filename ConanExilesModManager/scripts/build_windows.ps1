<#
Usage: .\scripts\build_windows.ps1
#>
Set-StrictMode -Version Latest
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

python -m pip install --upgrade pip
pip install pyinstaller
if (Test-Path requirements.txt) { pip install -r requirements.txt }

pyinstaller --onefile --noconsole --name ConanExilesModManager main.pyw

Write-Host "Built files in: $PWD\dist"

$ErrorActionPreference = "Stop"

# Single Windows entry point for the MVP automation flow.
# Edit the values in the configuration block below for your machine, then run:
#   powershell -ExecutionPolicy Bypass -File .\automation\run.ps1

$RepoRoot = Split-Path -Parent $PSScriptRoot

# --- Local machine configuration ---
$PythonExe = "python"
$SerialPort = "COM3"
$SerialBaud = 115200
$SerialTimeoutSeconds = 20
$CarrierFreqHz = 2450000000

$EnableBuild = $true
$EnableFlash = $true
$Repeats = 5
$PayloadSize = 14

$PicotoolPath = "C:\Users\16143\.pico-sdk\picotool\2.2.0-a4\picotool\picotool.exe"
$AutoHotkeyExe = "AutoHotkey.exe"

$PlanCsv = Join-Path $RepoRoot "automation\config\scan_plan.csv"
$ReceiverAhkScript = Join-Path $RepoRoot "automation\gui\smartrf_mvp.ahk"
$ReceiverCoordsIni = Join-Path $RepoRoot "automation\gui\smartrf_coords.ini"
$ResultsDir = Join-Path $RepoRoot "automation\results"
$StopFlag = Join-Path $RepoRoot "automation\stop.flag"
$MainC = Join-Path $RepoRoot "carrier-receiver-baseband\main.c"
$ProjectDir = Join-Path $RepoRoot "carrier-receiver-baseband"
$BuildDir = Join-Path $RepoRoot "carrier-receiver-baseband\build"

$Args = @(
    "automation/scripts/run_scan.py",
    "--plan-csv", $PlanCsv,
    "--serial-port", $SerialPort,
    "--serial-baud", $SerialBaud,
    "--serial-timeout-s", $SerialTimeoutSeconds,
    "--carrier-freq-hz", $CarrierFreqHz,
    "--main-c", $MainC,
    "--project-dir", $ProjectDir,
    "--build-dir", $BuildDir,
    "--picotool-path", $PicotoolPath,
    "--receiver-ahk-exe", $AutoHotkeyExe,
    "--receiver-ahk-script", $ReceiverAhkScript,
    "--receiver-coords-ini", $ReceiverCoordsIni,
    "--results-dir", $ResultsDir,
    "--stop-flag", $StopFlag,
    "--repeats", $Repeats,
    "--payload-size", $PayloadSize
)

if ($EnableBuild) {
    $Args += "--enable-build"
}

if ($EnableFlash) {
    $Args += "--enable-flash"
}

Push-Location $RepoRoot
try {
    if (Test-Path -LiteralPath $StopFlag) {
        Remove-Item -LiteralPath $StopFlag -Force
    }
    & $PythonExe @Args
}
finally {
    Pop-Location
}

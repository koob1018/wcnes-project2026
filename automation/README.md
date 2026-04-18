# Automation MVP

This folder contains the Windows-first experiment automation path for the
backscatter setup.

## One input, one runner, minimal outputs

The intended workflow is:

1. Set up the carrier manually before automation starts.
2. Edit `automation/config/scan_plan.csv`.
3. Adjust local machine settings in `automation/run.ps1`.
4. Run `automation/run.ps1`.
5. The runner will:
   - patch tag parameters in `carrier-receiver-baseband/main.c`
   - optionally build and flash the tag
   - read tag serial output
   - parse receiver settings from the final `set rx ...` lines
   - launch SmartRF Studio GUI automation
   - save raw logs only

Outputs are intentionally limited to:

- `automation/results/<session_id>/manifest.csv`
- `automation/results/<session_id>/raw/*_tag_serial.txt`
- `automation/results/<session_id>/raw/*_receiver_raw.txt`

No per-run JSON bridge files are generated.

## Parameter input

Use only `automation/config/scan_plan.csv`.

Required CSV columns:

- `run_id`
- `clock_div0`
- `clock_div1`
- `desired_baud`

Optional CSV columns:

- `target_packets`
- `receiver_timeout_s`
- `enabled`
- `notes`

Example:

```csv
run_id,clock_div0,clock_div1,desired_baud,target_packets,receiver_timeout_s,enabled,notes
d20_d18_b100k,20,18,100000,200,120,1,baseline
d22_d20_b100k,22,20,100000,200,120,1,candidate
```

## Run on Windows

Use the single entry script:

```powershell
powershell -ExecutionPolicy Bypass -File .\automation\run.ps1
```

Before the first run, open `automation/run.ps1` and set:

- `SerialPort`
- `PicotoolPath`
- `AutoHotkeyExe`
- `EnableBuild`
- `EnableFlash`

The Python runner is still available if you need it, but the intended daily
entry point is now `automation/run.ps1`.

## Stop the run

Two stop paths are supported:

- Press `Ctrl+C` in the PowerShell window running `automation/run.ps1`
- Create `automation/stop.flag`

The runner checks stop requests before each safe step and the SmartRF GUI helper
also watches the same stop flag during RX capture, so receiver collection can
stop cleanly instead of forcing the whole process down.

Assumptions:

- SmartRF Studio is already open on the Packet RX page.
- `automation/gui/smartrf_coords.ini` matches the current GUI layout.
- AutoHotkey is installed and available as `AutoHotkey.exe`, or passed via
  `--receiver-ahk-exe`.

## File responsibilities

- `config/scan_plan.csv`: the only experiment parameter table
- `run.ps1`: the only Windows entry script you should run manually
- `scripts/run_scan.py`: the main experiment runner
- `scripts/tag_pipeline.py`: tag patch/build/flash/serial helpers
- `gui/smartrf_mvp.ahk`: SmartRF Studio GUI automation
- `gui/smartrf_coords.ini`: machine-specific GUI coordinates
- `results/`: raw experiment outputs

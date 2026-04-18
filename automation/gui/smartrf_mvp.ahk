; SmartRF MVP capture helper
; Usage:
;   AutoHotkey.exe smartrf_mvp.ahk <coords_ini> <base_freq_hz> <data_rate_baud> <deviation_hz> <rx_bw_hz> <save_path> <timeout_s> <target_packets> <stop_flag>
;
; Assumptions:
; - SmartRF is already open and on the Packet RX page.
; - Fields are editable via mouse click + Ctrl+A + typing.
; - Packet count field is selectable/copyable.

#NoEnv
#SingleInstance Force
SetTitleMatchMode, 2
SendMode Input
SetKeyDelay, 30, 30
CoordMode, Mouse, Client

if (A_Args.Length() < 9) {
    MsgBox, 16, Error, Missing args.`nExpected: ini base_freq data_rate deviation rx_bw save_path timeout target_packets stop_flag
    ExitApp
}

iniPath := A_Args[1]
baseFreq := A_Args[2]
dataRate := A_Args[3]
deviation := A_Args[4]
rxBw := A_Args[5]
savePath := A_Args[6]
timeoutS := A_Args[7] + 0
targetPackets := A_Args[8] + 0
stopFlagPath := A_Args[9]

IniRead, titleContains, %iniPath%, window, title_contains,
IniRead, baseFreqX, %iniPath%, coords, base_freq_x
IniRead, baseFreqY, %iniPath%, coords, base_freq_y
IniRead, dataRateX, %iniPath%, coords, data_rate_x
IniRead, dataRateY, %iniPath%, coords, data_rate_y
IniRead, deviationX, %iniPath%, coords, deviation_x
IniRead, deviationY, %iniPath%, coords, deviation_y
IniRead, rxBwX, %iniPath%, coords, rx_bw_x
IniRead, rxBwY, %iniPath%, coords, rx_bw_y
IniRead, startX, %iniPath%, coords, start_button_x
IniRead, startY, %iniPath%, coords, start_button_y
IniRead, stopX, %iniPath%, coords, stop_button_x
IniRead, stopY, %iniPath%, coords, stop_button_y
IniRead, dumpPathX, %iniPath%, coords, dump_path_x, ERROR
IniRead, dumpPathY, %iniPath%, coords, dump_path_y, ERROR
IniRead, saveMode, %iniPath%, save, mode, dump_field
IniRead, rxBwControl, %iniPath%, rx_bw, control, dropdown
IniRead, rxBwOptions, %iniPath%, rx_bw, options_khz,

if (titleContains != "") {
    WinActivate, %titleContains%
    WinWaitActive, %titleContains%,, 3
}

if !WinActive("A") {
    MsgBox, 16, Error, No active window found for automation.
    ExitApp
}

ScrollToBottom()

baseFreqDisplay := ToDisplay(baseFreq, 1000000, 6)   ; Hz -> MHz
dataRateDisplay := ToDisplay(dataRate, 1000, 4)      ; Baud -> kBaud
deviationDisplay := ToDisplay(deviation, 1000, 3)    ; Hz -> kHz
rxBwDisplay := ToDisplay(rxBw, 1000, 3)              ; Hz -> kHz

SetField(baseFreqX, baseFreqY, baseFreqDisplay)
SetField(dataRateX, dataRateY, dataRateDisplay)
SetField(deviationX, deviationY, deviationDisplay)

if (rxBwControl = "dropdown") {
    if (rxBwOptions != "") {
        rxBwIndex := PickCeilingIndex(rxBwDisplay + 0, rxBwOptions)
        SetDropdownValueByIndex(rxBwX, rxBwY, rxBwIndex)
    } else {
        SetDropdownValue(rxBwX, rxBwY, rxBwDisplay)
    }
} else {
    SetField(rxBwX, rxBwY, rxBwDisplay)
}

if (dumpPathX != "ERROR" and dumpPathY != "ERROR") {
    SetFieldPaste(dumpPathX, dumpPathY, savePath)
}

startLineCount := GetFileLineCount(savePath)

; Start RX
ClickAt(startX, startY)
startTick := A_TickCount

loop {
    elapsedS := (A_TickCount - startTick) / 1000.0
    if (elapsedS >= timeoutS) {
        break
    }
    if (stopFlagPath != "" and FileExist(stopFlagPath)) {
        break
    }

    currentLineCount := GetFileLineCount(savePath)
    if ((currentLineCount - startLineCount) >= targetPackets) {
        break
    }
    Sleep, 700
}

; Stop RX
ClickAt(stopX, stopY)
Sleep, 300

if (saveMode = "ctrl_s") {
    SaveByCtrlS(savePath)
}

ExitApp

SetField(x, y, value) {
    ClickAt(x, y)
    Sleep, 100
    Send, ^a
    Sleep, 80
    SendRaw, %value%
    Sleep, 120
}

SetDropdownValue(x, y, value) {
    ClickAt(x, y)
    Sleep, 100
    Send, {Home}
    Sleep, 80
    SendRaw, %value%
    Sleep, 100
    Send, {Enter}
    Sleep, 120
}

SetDropdownValueByIndex(x, y, index) {
    if (index < 1) {
        index := 1
    }
    downCount := index - 1
    ClickAt(x, y)
    Sleep, 100
    ; Deterministic navigation for non-standard combo controls:
    ; force to top with keyboard Up, then move Down by fixed steps.
    Loop, 50 {
        Send, {Up}
        Sleep, 30
    }
    Sleep, 80
    Loop, % downCount {
        Send, {Down}
        Sleep, 30
    }
    Send, {Enter}
    Sleep, 120
}

SetFieldPaste(x, y, value) {
    ClickAt(x, y)
    Sleep, 120
    Send, ^a
    Sleep, 80
    Clipboard := value
    ClipWait, 1
    Send, ^v
    Sleep, 120
}

SaveByCtrlS(path) {
    Send, ^s
    Sleep, 500
    Clipboard := path
    ClipWait, 1
    Send, ^a
    Sleep, 80
    Send, ^v
    Sleep, 80
    Send, {Enter}
    Sleep, 200
}

ClickAt(x, y) {
    MouseMove, %x%, %y%, 15
    Sleep, 120
    Click
}


ScrollToBottom() {
    MouseMove, 1200, 700, 15
    Sleep, 120
    Click
    Sleep, 120
    Loop, 10 {
        Send, {WheelDown 6}
        Sleep, 80
    }
    Sleep, 120
}

ToDisplay(value, scale, digits) {
    raw := value + 0
    if (raw > scale * 2) {
        converted := raw / scale
    } else {
        converted := raw
    }
    fmt := "{:." . digits . "f}"
    return Format(fmt, converted)
}

PickCeilingIndex(target, optionsCsv) {
    bestIndex := 1
    bestValue := 1000000000
    idx := 0
    Loop, Parse, optionsCsv, `,
    {
        opt := Trim(A_LoopField)
        if (opt = "") {
            continue
        }
        idx++
        optValue := opt + 0
        if (optValue >= target and optValue < bestValue) {
            bestValue := optValue
            bestIndex := idx
        }
    }
    if (bestValue != 1000000000) {
        return bestIndex
    }

    idx := 0
    bestValue := -1000000000
    Loop, Parse, optionsCsv, `,
    {
        opt := Trim(A_LoopField)
        if (opt = "") {
            continue
        }
        idx++
        optValue := opt + 0
        if (optValue > bestValue) {
            bestValue := optValue
            bestIndex := idx
        }
    }
    return bestIndex
}

GetFileLineCount(path) {
    if !FileExist(path) {
        return 0
    }
    count := 0
    Loop, Read, %path%
    {
        count++
    }
    return count
}


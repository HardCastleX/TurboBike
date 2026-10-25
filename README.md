# TurboBike

**English** | [Español](README.es.md)

External macro for GTA San Andreas (1.0 US) that automates the NRG-500 speed glitch: it taps `Up Arrow` while you hold `W`.

## How it works

The tap is **locked to the game's frame**, not to a millisecond interval. GTA SA samples the keyboard once per frame and the glitch rewards the *press edge*, so the theoretical maximum is one edge every two frames. A fixed ms interval cannot reach that: if it is shorter than a frame, the tap falls between samples and the whole boost is lost; if it is longer, frames are wasted.

To know when a frame starts, the script reads `CTimer::m_snTimeInMilliseconds` (`0xB7CB84`), which advances once per frame. That makes the cadence **optimal by construction and immune to FPS variations**, and the delta between reads also gives the real FPS, which is shown in the console. At 90 FPS that is ~45 edges per second, versus ~11 in the previous version based on random delays.

Keystrokes are sent with `SendInput` by scancode (the path DirectInput games read) and the `W` state is queried with `GetAsyncKeyState`, all directly through `ctypes`.

> **Note:** the script **reads the game process memory** (read-only, it never writes). It does not modify anything, but `OpenProcess`/`ReadProcessMemory` on `gta_sa.exe` is detectable by SA-MP and MTA anti-cheat systems. It is intended for single-player.

## Requirements

- Windows + Python 3
- GTA San Andreas 1.0 US (`gta_sa.exe`)

## Installation and usage

1. Open GTA San Andreas.
2. Run `ejecutar.bat` (installs dependencies and starts the macro).

Or manually:

```bat
pip install -r requirements.txt
python gta_sa_turbo.py
```

### Do I need administrator rights?

Normally **no**: neither the global keyboard hook, nor `SendInput`, nor reading the memory of a process owned by the same user requires elevation. You only need it if you launch GTA SA as administrator (common with mods or Windows compatibility options): in that case UIPI blocks keystroke injection from a process with lower privileges than the target window, and the game will not respond even though the macro seems to work. The rule is that the script must run at the same privilege level as the game, or higher.

## Controls

| Key | Action |
|-----|--------|
| `F11` | Enable turbo mode |
| `F12` | Disable turbo mode |
| `W` (hold) | Runs the macro while accelerating on a bike |
| `END` | Close the script |

## Failure diagnostics

If the script exits on its own, the reason is always written to `error.log` and
to the console, and `ejecutar.bat` distinguishes a clean exit from an error.

The script watches the two threads `keyboard` uses in the background (the Windows
hook listener and the one that invokes the hotkey callbacks). If either one dies,
all hotkeys stop working —including `END`— so the script would otherwise wait
forever: it detects this within a couple of seconds and exits with a message
explaining what happened.

`END` is detected by checking that it does not come from the numeric keypad. GTA SA
uses the numpad for the camera and **numpad 1** shares a scan code with `END`:
without that check, pressing numpad 1 would close the script mid-game.

## Files

- `gta_sa_turbo.py` — main script
- `requirements.txt` / `ejecutar.bat` — dependency installation

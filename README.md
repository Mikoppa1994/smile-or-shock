# Smile or Suffer — BDSM Predicament Trainer

Keep a smile… or get punished.

Smile or Suffer is a webcam-based predicament game. It tracks your face and expects you to keep smiling. 
If you stop, it triggers shocks over serial. You can set session length, cooldowns, and intensity ranges and let it run.

## Highlights
- Smile predicament: stop smiling → shocks
- Session length, cooldowns, intensity ranges
- Channel A/B with randomized bursts
- Tease mode + Challenge (super-smile) mode
- Tested with **Estim System 2B**

## Setup
1. Install Python 3.10+
2. Install deps:
   ```bash
   python setup.py
   ```
3. Run:
   ```bash
   python Smile_or_shock.py
   ```

## How it works
1. Open **Options** and set your session rules.
2. Pick a COM port and connect.
3. Press `S` to set your smile baseline.
4. Keep smiling to drain the timer. Stop smiling and it ramps up.

## Modes
- **Tease mode**: low intensity pulses while you *are* smiling.
- **Challenge mode**: random super-smile holds. Failure = bigger punishment.

## Controls
- `S` = set smile baseline (starts warm-up)
- `Q` = quit

## Debug
Set `DEBUG = 1` in `config.py` to show the live ratio, thresholds, and last serial messages.

## Inspired by
- mistress_and_pup
- Deviant-Designs

If you want to Support me: https://buymeacoffee.com/bdsmbytes

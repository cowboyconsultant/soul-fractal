# Soul Fractal Intoxication Simulation (Prototype)

This repository now contains a **cross-platform Python prototype** for simulating how mixed intoxicants may alter visible behavior over time in a street setting.

## What it does

- Lets you set person-specific inputs (height, weight, sleep, hydration, tolerance).
- Supports multiple substances and alcohol subtypes.
- Supports incremental dosing over time (`--event key:dose:minute`).
- Simulates timeline effects plus social interactions every 15 minutes.
- Outputs either human-readable text or JSON for game/app integrations.

## Important limits

This model is educational and narrative-oriented. It is **not** a medical model and cannot exactly predict real physiology or outcomes.

## Quick start

```bash
python3 simulator.py --list
```

Example mixed simulation:

```bash
python3 simulator.py \
  --name "Street Sim" \
  --height-cm 180 --weight-kg 82 --sleep-hours 5.5 \
  --event beer:2:0 \
  --event cannabis:1.5:30 \
  --event cocaine:0.8:75 \
  --duration-min 360
```

JSON mode:

```bash
python3 simulator.py --event wine:3:0 --event benzodiazepine:1:50 --json
```

## Cross-platform notes

- Works on macOS, Linux, and Windows with Python 3.10+.
- For app integration, call `simulator.py --json` and parse the returned timeline/interactions.

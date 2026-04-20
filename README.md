# Soul Fractal: Smallville-Style Social Simulation

This project is a local-first social simulation inspired by Stanford's *Smallville* architecture, now with all major upgrade tracks included:

- **LLM-backed planning and reflection** (optional)
- **Memory retrieval** for context-aware decisions
- **Trust/reputation dynamics** that influence interactions and behavior
- **Minimal web timeline viewer** for replay and inspection

## 1) Run the simulation (heuristic mode)

```bash
python3 simulation.py --days 2 --seed 42 --verbose
```

You will get JSONL output in `events.jsonl`.

## 2) Run with LLM planning + reflection

```bash
export OPENAI_API_KEY="your_key_here"
python3 simulation.py --days 2 --planner llm --reflector llm --openai-model gpt-4o-mini
```

If no API key is provided, the simulation safely falls back to heuristic behavior.

## 3) Open the timeline viewer

```bash
python3 timeline_viewer.py --events events.jsonl --port 8000
```

Then open `http://127.0.0.1:8000` in your browser.

## CLI reference

### `simulation.py`
- `--days` number of simulated days
- `--seed` RNG seed for reproducibility
- `--output` JSONL output path
- `--verbose` print events as they happen
- `--planner {heuristic,llm}`
- `--reflector {heuristic,llm}`
- `--openai-api-key` optional API key override
- `--openai-model` model used by planner/reflector

### `timeline_viewer.py`
- `--events` path to JSONL file
- `--host` bind host (default `127.0.0.1`)
- `--port` bind port (default `8000`)

## Architecture summary

- **Agents** have role, traits, goals, energy/social needs, memories, relationships, and trust.
- **Memory retrieval** ranks memories by salience + token overlap + light recency.
- **Trust/reputation** modifies relationship drift and social behavior.
- **Event stream** (`action`, `interaction`, `reflection`) is persisted as JSONL.
- **Viewer** reads events via a tiny local HTTP API and offers filtering/search.

## Suggested next upgrades

1. Add larger populations + map topology.
2. Introduce jobs, schedules, and tasks with deadlines.
3. Add scenario files (YAML/JSON) for repeatable experiments.
4. Build metrics dashboards (e.g., loneliness, trust variance, cohesion).

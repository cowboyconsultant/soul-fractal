# Soul Fractal: Smallville-Style Social Simulation Starter

This repository now contains a lightweight, local-first simulation inspired by Stanford's *Smallville* idea: autonomous agents with:

- **Profiles and goals**
- **Daily planning**
- **Memory (recent + long-term summaries)**
- **Social interactions**
- **A shared world map of locations**

It is intentionally simple and fully deterministic by default so you can iterate fast.

## Quickstart

```bash
python3 simulation.py --days 2 --seed 42
```

Optional verbose logs:

```bash
python3 simulation.py --days 1 --seed 42 --verbose
```

## What this gives you

- A ticking clock (`hour` granularity)
- Agents choosing actions based on needs, commitments, and relationships
- Memory entries generated from observations/interactions
- End-of-day reflection that updates each agent's long-term notes
- JSONL event log output you can reuse for analytics/visualization

## Suggested next upgrades

1. Replace heuristic decision-making with an LLM policy function.
2. Add retrieval over memory using embeddings.
3. Introduce reputation/trust dynamics.
4. Add asynchronous events and interruptions.
5. Build a web UI for timeline playback.

If you want, I can do the next step and add:
- OpenAI-powered planning + reflection prompts
- Vector memory retrieval
- A browser visualization

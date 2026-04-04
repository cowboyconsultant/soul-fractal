#!/usr/bin/env python3
"""
Smallville-style social simulation starter.

Run:
    python3 simulation.py --days 2 --seed 42 --verbose
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

HOURS = list(range(8, 22))  # 08:00 to 21:00


@dataclass
class Memory:
    hour: int
    text: str
    salience: float


@dataclass
class Location:
    name: str
    tags: List[str]


@dataclass
class Agent:
    name: str
    role: str
    home: str
    work: str
    traits: List[str]
    goals: List[str]
    relationships: Dict[str, float] = field(default_factory=dict)
    location: Optional[str] = None
    energy: float = 1.0
    social_need: float = 0.5
    recent_memories: List[Memory] = field(default_factory=list)
    reflections: List[str] = field(default_factory=list)

    def plan_for_hour(self, hour: int) -> str:
        if hour in (9, 10, 11, 13, 14, 15):
            return "work"
        if self.energy < 0.35:
            return "rest"
        if self.social_need > 0.65:
            return "socialize"
        if hour in (18, 19):
            return "socialize"
        return "personal_project"

    def apply_action_effects(self, action: str) -> None:
        if action == "work":
            self.energy -= 0.12
            self.social_need += 0.05
        elif action == "rest":
            self.energy += 0.2
            self.social_need += 0.02
        elif action == "socialize":
            self.energy -= 0.07
            self.social_need -= 0.25
        elif action == "personal_project":
            self.energy -= 0.1
            self.social_need += 0.03

        self.energy = max(0.0, min(1.0, self.energy))
        self.social_need = max(0.0, min(1.0, self.social_need))

    def remember(self, hour: int, text: str, salience: float) -> None:
        self.recent_memories.append(Memory(hour=hour, text=text, salience=salience))
        self.recent_memories = sorted(self.recent_memories, key=lambda m: m.salience, reverse=True)[:30]

    def reflect(self) -> str:
        if not self.recent_memories:
            summary = f"{self.name} had a quiet day and wants to pursue {self.goals[0]}."
            self.reflections.append(summary)
            return summary

        top = self.recent_memories[:3]
        memory_blurb = "; ".join(m.text for m in top)
        summary = (
            f"{self.name} reflects: key moments were {memory_blurb}. "
            f"Tomorrow they will focus on {self.goals[0]}."
        )
        self.reflections.append(summary)
        return summary


class Simulation:
    def __init__(self, seed: int = 42, verbose: bool = False, output_path: str = "events.jsonl") -> None:
        random.seed(seed)
        self.verbose = verbose
        self.day = 1
        self.locations = {
            "Town Square": Location("Town Square", ["public", "social"]),
            "Cafe": Location("Cafe", ["food", "social"]),
            "Library": Location("Library", ["quiet", "study"]),
            "Workshop": Location("Workshop", ["work", "craft"]),
            "Homes": Location("Homes", ["private", "rest"]),
        }
        self.agents = self._create_agents()
        self.output_path = Path(output_path)
        if self.output_path.exists():
            self.output_path.unlink()

    def _create_agents(self) -> List[Agent]:
        ava = Agent(
            name="Ava",
            role="maker",
            home="Homes",
            work="Workshop",
            traits=["curious", "helpful"],
            goals=["finish a new kinetic sculpture", "mentor local students"],
        )
        ben = Agent(
            name="Ben",
            role="barista",
            home="Homes",
            work="Cafe",
            traits=["friendly", "observant"],
            goals=["grow cafe community nights", "write short stories"],
        )
        cleo = Agent(
            name="Cleo",
            role="research assistant",
            home="Homes",
            work="Library",
            traits=["analytical", "reserved"],
            goals=["publish a local history zine", "build stronger friendships"],
        )

        names = [a.name for a in (ava, ben, cleo)]
        for agent in (ava, ben, cleo):
            agent.relationships = {other: (0.5 if other != agent.name else 1.0) for other in names}

        return [ava, ben, cleo]

    def log_event(self, day: int, hour: int, event_type: str, payload: Dict) -> None:
        item = {"day": day, "hour": hour, "type": event_type, "payload": payload}
        with self.output_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(item) + "\n")
        if self.verbose:
            print(f"[D{day} {hour:02d}:00] {event_type} | {payload}")

    def choose_location(self, agent: Agent, action: str) -> str:
        if action == "work":
            return agent.work
        if action == "rest":
            return agent.home
        if action == "socialize":
            return random.choice(["Town Square", "Cafe"])
        return random.choice(["Library", "Workshop", "Homes"])

    def run_hour(self, hour: int) -> None:
        # Step 1: each agent picks an action and moves.
        actions: Dict[str, str] = {}
        for agent in self.agents:
            action = agent.plan_for_hour(hour)
            actions[agent.name] = action
            agent.location = self.choose_location(agent, action)
            agent.apply_action_effects(action)
            self.log_event(
                self.day,
                hour,
                "action",
                {
                    "agent": agent.name,
                    "action": action,
                    "location": agent.location,
                    "energy": round(agent.energy, 2),
                    "social_need": round(agent.social_need, 2),
                },
            )

        # Step 2: interactions for co-located agents.
        by_location: Dict[str, List[Agent]] = {}
        for agent in self.agents:
            by_location.setdefault(agent.location or "Unknown", []).append(agent)

        for loc_name, group in by_location.items():
            if len(group) < 2:
                continue
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]
                    warmth = round((a.relationships[b.name] + b.relationships[a.name]) / 2, 2)
                    interaction = f"{a.name} chatted with {b.name} at {loc_name}"
                    salience = 0.6 + (0.4 * warmth)
                    a.remember(hour, interaction, salience)
                    b.remember(hour, interaction, salience)

                    # Tiny relationship drift.
                    delta = random.uniform(-0.03, 0.06)
                    a.relationships[b.name] = max(0.0, min(1.0, a.relationships[b.name] + delta))
                    b.relationships[a.name] = max(0.0, min(1.0, b.relationships[a.name] + delta))

                    self.log_event(
                        self.day,
                        hour,
                        "interaction",
                        {
                            "a": a.name,
                            "b": b.name,
                            "location": loc_name,
                            "warmth": warmth,
                            "relationship_delta": round(delta, 3),
                        },
                    )

    def end_day(self) -> None:
        for agent in self.agents:
            reflection = agent.reflect()
            self.log_event(self.day, 22, "reflection", {"agent": agent.name, "text": reflection})

            # Light reset for next day.
            agent.energy = min(1.0, agent.energy + 0.35)
            agent.social_need = max(0.0, agent.social_need - 0.1)

    def run(self, days: int = 2) -> None:
        for _ in range(days):
            for hour in HOURS:
                self.run_hour(hour)
            self.end_day()
            self.day += 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smallville-style simulation starter")
    parser.add_argument("--days", type=int, default=2, help="Number of simulated days")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--output", type=str, default="events.jsonl", help="Path for JSONL event logs")
    parser.add_argument("--verbose", action="store_true", help="Print events as they happen")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sim = Simulation(seed=args.seed, verbose=args.verbose, output_path=args.output)
    sim.run(days=args.days)
    print(f"Simulation complete. Events written to: {args.output}")


if __name__ == "__main__":
    main()

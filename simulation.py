#!/usr/bin/env python3
"""
Smallville-style social simulation with optional LLM planning,
memory retrieval, trust/reputation dynamics, and JSONL logging.

Examples:
    python3 simulation.py --days 2 --seed 42 --verbose
    OPENAI_API_KEY=... python3 simulation.py --planner llm --reflector llm
"""

from __future__ import annotations

import argparse
import os
import json
import random
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

HOURS = list(range(8, 22))  # 08:00 to 21:00
STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "in",
    "on",
    "for",
    "with",
    "at",
    "is",
    "are",
    "was",
    "were",
    "be",
    "by",
    "it",
    "this",
    "that",
    "from",
}


@dataclass
class Memory:
    day: int
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
    trust: Dict[str, float] = field(default_factory=dict)
    location: Optional[str] = None
    energy: float = 1.0
    social_need: float = 0.5
    recent_memories: List[Memory] = field(default_factory=list)
    reflections: List[str] = field(default_factory=list)

    def heuristic_plan(self, hour: int) -> str:
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

    def remember(self, day: int, hour: int, text: str, salience: float) -> None:
        self.recent_memories.append(Memory(day=day, hour=hour, text=text, salience=salience))
        self.recent_memories = sorted(self.recent_memories, key=lambda m: m.salience, reverse=True)[:60]

    def retrieve_memories(self, query: str, k: int = 6) -> List[Memory]:
        query_tokens = _tokenize(query)
        if not self.recent_memories:
            return []

        scored: List[Tuple[float, Memory]] = []
        for m in self.recent_memories:
            mem_tokens = _tokenize(m.text)
            overlap = len(query_tokens.intersection(mem_tokens))
            recency_bonus = 0.15 if m.day == self.recent_memories[-1].day else 0.0
            score = m.salience + (0.2 * overlap) + recency_bonus
            scored.append((score, m))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:k]]


def _tokenize(text: str) -> set:
    tokens = set(re.findall(r"[a-zA-Z]+", text.lower()))
    return {t for t in tokens if t not in STOPWORDS and len(t) > 2}


class OpenAIPlanner:
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def _chat(self, system_prompt: str, user_prompt: str, max_tokens: int = 90) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            method="POST",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return ""

        choices = body.get("choices", [])
        if not choices:
            return ""
        return choices[0].get("message", {}).get("content", "").strip()

    def choose_action(self, agent: Agent, hour: int, retrieved: Sequence[Memory]) -> str:
        memory_block = "\n".join(
            f"- (day {m.day}, {m.hour:02d}:00, salience={m.salience:.2f}) {m.text}" for m in retrieved[:5]
        ) or "- no relevant memories"
        prompt = (
            f"Agent: {agent.name} ({agent.role})\n"
            f"Traits: {', '.join(agent.traits)}\n"
            f"Goals: {', '.join(agent.goals)}\n"
            f"Hour: {hour}:00\n"
            f"Energy: {agent.energy:.2f}, SocialNeed: {agent.social_need:.2f}\n"
            f"Relevant memories:\n{memory_block}\n\n"
            "Choose ONE action from exactly this set: work, rest, socialize, personal_project. "
            "Return only the action word."
        )
        result = self._chat(
            "You are a concise simulation policy. Output only one valid action token.",
            prompt,
            max_tokens=6,
        ).lower().strip()
        if result in {"work", "rest", "socialize", "personal_project"}:
            return result
        return agent.heuristic_plan(hour)

    def reflect(self, agent: Agent, retrieved: Sequence[Memory]) -> str:
        memory_block = "\n".join(f"- {m.text}" for m in retrieved[:6]) or "- no memories"
        prompt = (
            f"Agent: {agent.name}\n"
            f"Goals: {', '.join(agent.goals)}\n"
            f"Memories:\n{memory_block}\n\n"
            "Write 1 short reflection sentence and 1 short next-step sentence."
        )
        result = self._chat(
            "You generate realistic but concise in-character reflections for simulation agents.",
            prompt,
            max_tokens=80,
        )
        return result or f"{agent.name} reflects on the day and plans to continue {agent.goals[0]}."


class Simulation:
    def __init__(
        self,
        seed: int = 42,
        verbose: bool = False,
        output_path: str = "events.jsonl",
        planner_mode: str = "heuristic",
        reflector_mode: str = "heuristic",
        openai_api_key: str = "",
        openai_model: str = "gpt-4o-mini",
    ) -> None:
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
        self.reputation: Dict[str, float] = {a.name: 0.5 for a in self.agents}
        self.output_path = Path(output_path)
        if self.output_path.exists():
            self.output_path.unlink()

        self.planner_mode = planner_mode
        self.reflector_mode = reflector_mode
        self.llm: Optional[OpenAIPlanner] = None
        if openai_api_key and (planner_mode == "llm" or reflector_mode == "llm"):
            self.llm = OpenAIPlanner(api_key=openai_api_key, model=openai_model)

    def _create_agents(self) -> List[Agent]:
        agents = [
            Agent(
                name="Ava",
                role="maker",
                home="Homes",
                work="Workshop",
                traits=["curious", "helpful"],
                goals=["finish a new kinetic sculpture", "mentor local students"],
            ),
            Agent(
                name="Ben",
                role="barista",
                home="Homes",
                work="Cafe",
                traits=["friendly", "observant"],
                goals=["grow cafe community nights", "write short stories"],
            ),
            Agent(
                name="Cleo",
                role="research assistant",
                home="Homes",
                work="Library",
                traits=["analytical", "reserved"],
                goals=["publish a local history zine", "build stronger friendships"],
            ),
        ]

        names = [a.name for a in agents]
        for agent in agents:
            agent.relationships = {other: (0.5 if other != agent.name else 1.0) for other in names}
            agent.trust = {other: (0.5 if other != agent.name else 1.0) for other in names}
        return agents

    def log_event(self, day: int, hour: int, event_type: str, payload: Dict) -> None:
        item = {"day": day, "hour": hour, "type": event_type, "payload": payload}
        with self.output_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(item) + "\n")
        if self.verbose:
            print(f"[D{day} {hour:02d}:00] {event_type} | {payload}")

    def choose_action(self, agent: Agent, hour: int) -> str:
        query = f"hour {hour} goals {' '.join(agent.goals)} social {agent.social_need:.2f}"
        retrieved = agent.retrieve_memories(query, k=6)

        if self.planner_mode == "llm" and self.llm is not None:
            return self.llm.choose_action(agent, hour, retrieved)

        # Heuristic + trust gating.
        heuristic = agent.heuristic_plan(hour)
        if heuristic == "socialize":
            avg_trust = (
                sum(v for k, v in agent.trust.items() if k != agent.name) / max(1, len(agent.trust) - 1)
            )
            if avg_trust < 0.35 and agent.social_need < 0.85:
                return "personal_project"
        return heuristic

    def choose_location(self, agent: Agent, action: str) -> str:
        if action == "work":
            return agent.work
        if action == "rest":
            return agent.home
        if action == "socialize":
            # Higher trust in Ben biases agents toward cafe gatherings.
            ben_trust = agent.trust.get("Ben", 0.5)
            return "Cafe" if random.random() < ben_trust else "Town Square"
        return random.choice(["Library", "Workshop", "Homes"])

    def interaction_delta(self, a: Agent, b: Agent) -> float:
        base = random.uniform(-0.03, 0.06)
        trust_bonus = ((a.trust[b.name] + b.trust[a.name]) / 2 - 0.5) * 0.08
        rep_bonus = ((self.reputation[a.name] + self.reputation[b.name]) / 2 - 0.5) * 0.05
        return base + trust_bonus + rep_bonus

    def run_hour(self, hour: int) -> None:
        for agent in self.agents:
            action = self.choose_action(agent, hour)
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
                    a.remember(self.day, hour, interaction, salience)
                    b.remember(self.day, hour, interaction, salience)

                    delta = self.interaction_delta(a, b)
                    a.relationships[b.name] = max(0.0, min(1.0, a.relationships[b.name] + delta))
                    b.relationships[a.name] = max(0.0, min(1.0, b.relationships[a.name] + delta))
                    a.trust[b.name] = max(0.0, min(1.0, a.trust[b.name] + (delta * 0.8)))
                    b.trust[a.name] = max(0.0, min(1.0, b.trust[a.name] + (delta * 0.8)))
                    self.reputation[a.name] = max(0.0, min(1.0, self.reputation[a.name] + (delta * 0.25)))
                    self.reputation[b.name] = max(0.0, min(1.0, self.reputation[b.name] + (delta * 0.25)))

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
                            "a_trust_b": round(a.trust[b.name], 3),
                            "b_trust_a": round(b.trust[a.name], 3),
                            "a_reputation": round(self.reputation[a.name], 3),
                            "b_reputation": round(self.reputation[b.name], 3),
                        },
                    )

    def end_day(self) -> None:
        for agent in self.agents:
            query = f"day {self.day} reflection {' '.join(agent.goals)}"
            retrieved = agent.retrieve_memories(query, k=8)

            if self.reflector_mode == "llm" and self.llm is not None:
                reflection = self.llm.reflect(agent, retrieved)
            else:
                if not retrieved:
                    reflection = f"{agent.name} had a quiet day and wants to pursue {agent.goals[0]}."
                else:
                    top = "; ".join(m.text for m in retrieved[:3])
                    reflection = (
                        f"{agent.name} reflects: key moments were {top}. "
                        f"Tomorrow they will focus on {agent.goals[0]}."
                    )
            agent.reflections.append(reflection)
            self.log_event(self.day, 22, "reflection", {"agent": agent.name, "text": reflection})

            agent.energy = min(1.0, agent.energy + 0.35)
            agent.social_need = max(0.0, agent.social_need - 0.1)

    def run(self, days: int = 2) -> None:
        for _ in range(days):
            for hour in HOURS:
                self.run_hour(hour)
            self.end_day()
            self.day += 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smallville-style simulation")
    parser.add_argument("--days", type=int, default=2, help="Number of simulated days")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--output", type=str, default="events.jsonl", help="Path for JSONL event logs")
    parser.add_argument("--verbose", action="store_true", help="Print events as they happen")
    parser.add_argument("--planner", choices=["heuristic", "llm"], default="heuristic")
    parser.add_argument("--reflector", choices=["heuristic", "llm"], default="heuristic")
    parser.add_argument("--openai-api-key", default="", help="OpenAI API key (or set OPENAI_API_KEY env var)")
    parser.add_argument("--openai-model", default="gpt-4o-mini", help="OpenAI model for llm planner/reflector")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    api_key = args.openai_api_key
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY", "")

    sim = Simulation(
        seed=args.seed,
        verbose=args.verbose,
        output_path=args.output,
        planner_mode=args.planner,
        reflector_mode=args.reflector,
        openai_api_key=api_key,
        openai_model=args.openai_model,
    )
    sim.run(days=args.days)
    print(f"Simulation complete. Events written to: {args.output}")


if __name__ == "__main__":
    main()

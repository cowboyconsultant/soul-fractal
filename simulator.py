from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class PersonProfile:
    name: str
    age: int
    sex: str
    height_cm: float
    weight_kg: float
    sleep_hours: float
    tolerance: float  # 0.0 (none) to 1.0 (high)
    hydration: float  # 0.0 (dehydrated) to 1.0 (well hydrated)


@dataclass
class Substance:
    key: str
    display_name: str
    category: str
    potency: float
    onset_min: int
    half_life_hr: float
    stimulant: float
    depressant: float
    hallucinogenic: float
    disinhibiting: float


@dataclass
class ConsumptionEvent:
    substance_key: str
    dose_units: float  # abstract units for simulation only
    minute: int


@dataclass
class StateVector:
    alertness: float = 0.0
    motor_control: float = 0.0
    inhibition: float = 0.0
    perception_distortion: float = 0.0
    anxiety: float = 0.0


@dataclass
class InteractionOutcome:
    minute: int
    actor: str
    event: str


@dataclass
class SimulationResult:
    timeline: List[Dict[str, float]]
    interactions: List[InteractionOutcome]


SUBSTANCES: Dict[str, Substance] = {
    # Alcohol (dose units are standard drinks)
    "beer": Substance("beer", "Alcohol: Beer", "alcohol", 1.0, 20, 3.0, 0.0, 0.9, 0.0, 0.7),
    "wine": Substance("wine", "Alcohol: Wine", "alcohol", 1.1, 20, 3.0, 0.0, 1.0, 0.0, 0.8),
    "spirits": Substance("spirits", "Alcohol: Spirits", "alcohol", 1.3, 15, 3.0, 0.0, 1.2, 0.0, 1.0),
    # Stimulants
    "cocaine": Substance("cocaine", "Cocaine", "stimulant", 1.7, 10, 1.2, 1.6, 0.2, 0.0, 0.7),
    "amphetamine": Substance("amphetamine", "Amphetamine", "stimulant", 1.6, 30, 10.0, 1.5, 0.1, 0.0, 0.5),
    # Cannabinoids
    "cannabis": Substance("cannabis", "Cannabis (THC)", "cannabinoid", 1.1, 15, 4.0, 0.1, 0.6, 0.6, 0.4),
    # Opioids
    "opioid": Substance("opioid", "Opioids (generic)", "opioid", 2.2, 12, 6.0, 0.0, 2.0, 0.1, 0.5),
    "heroin": Substance("heroin", "Heroin", "opioid", 2.5, 6, 3.0, 0.0, 2.3, 0.1, 0.7),
    # Sedatives
    "benzodiazepine": Substance(
        "benzodiazepine", "Benzodiazepines", "sedative", 2.0, 25, 20.0, 0.0, 1.8, 0.0, 0.8
    ),
    # Psychedelics
    "lsd": Substance("lsd", "LSD", "psychedelic", 1.8, 40, 9.0, 0.3, 0.2, 2.0, 0.4),
    "psilocybin": Substance("psilocybin", "Psilocybin", "psychedelic", 1.6, 30, 6.0, 0.2, 0.2, 1.8, 0.3),
    # Dissociatives
    "ketamine": Substance("ketamine", "Ketamine", "dissociative", 1.9, 8, 3.0, 0.2, 1.1, 1.5, 0.4),
    # Nicotine/caffeine for comparison
    "nicotine": Substance("nicotine", "Nicotine", "stimulant", 0.8, 5, 2.0, 0.6, 0.0, 0.0, 0.1),
    "caffeine": Substance("caffeine", "Caffeine", "stimulant", 0.6, 20, 5.0, 0.5, 0.0, 0.0, 0.0),
}


def print_catalog() -> None:
    print("Available intoxicants / psychoactives (simulation only):")
    for s in SUBSTANCES.values():
        print(f"- {s.key:14} | {s.display_name:26} | category={s.category}")


def parse_events(raw_events: List[str]) -> List[ConsumptionEvent]:
    events: List[ConsumptionEvent] = []
    for item in raw_events:
        try:
            key, dose, minute = item.split(":")
            events.append(ConsumptionEvent(substance_key=key, dose_units=float(dose), minute=int(minute)))
        except ValueError as err:
            raise ValueError(f"Invalid --event format: '{item}' expected key:dose:minute") from err
    return events


def absorption_curve(minutes_since_dose: int, onset_min: int) -> float:
    if minutes_since_dose < 0:
        return 0.0
    ramp = 1 / (1 + math.exp(-(minutes_since_dose - onset_min) / 10))
    return ramp


def elimination_curve(minutes_since_dose: int, half_life_hr: float) -> float:
    if minutes_since_dose < 0:
        return 0.0
    half_life_min = half_life_hr * 60
    return 0.5 ** (minutes_since_dose / half_life_min)


def body_modifier(profile: PersonProfile) -> float:
    bmi = profile.weight_kg / ((profile.height_cm / 100) ** 2)
    body_mass_factor = max(0.7, min(1.3, 75 / max(45, profile.weight_kg)))
    fatigue_factor = max(0.8, min(1.3, 1.2 - (profile.sleep_hours - 7) * 0.05))
    hydration_factor = max(0.85, min(1.2, 1.1 - profile.hydration * 0.2))
    tolerance_factor = max(0.7, min(1.3, 1.2 - profile.tolerance * 0.5))
    bmi_factor = max(0.9, min(1.1, 1.0 + (22 - bmi) * 0.01))
    return body_mass_factor * fatigue_factor * hydration_factor * tolerance_factor * bmi_factor


def state_at_minute(profile: PersonProfile, events: List[ConsumptionEvent], minute: int) -> StateVector:
    m = body_modifier(profile)
    s = StateVector(alertness=0.1)

    for ev in events:
        drug = SUBSTANCES.get(ev.substance_key)
        if not drug:
            continue
        dt = minute - ev.minute
        exposure = ev.dose_units * drug.potency * absorption_curve(dt, drug.onset_min) * elimination_curve(dt, drug.half_life_hr) * m
        s.alertness += exposure * drug.stimulant
        s.alertness -= exposure * drug.depressant * 0.7
        s.motor_control -= exposure * (drug.depressant * 0.8 + drug.hallucinogenic * 0.5)
        s.inhibition -= exposure * drug.disinhibiting
        s.perception_distortion += exposure * (drug.hallucinogenic + 0.3 * drug.depressant)
        s.anxiety += exposure * max(0, drug.stimulant - drug.depressant * 0.3) * 0.4

    # Poly-substance interaction penalties
    active_classes = {
        SUBSTANCES[e.substance_key].category
        for e in events
        if e.substance_key in SUBSTANCES and minute >= e.minute
    }
    if len(active_classes) >= 2:
        mix_penalty = 0.2 * (len(active_classes) - 1)
        s.motor_control -= mix_penalty
        s.perception_distortion += mix_penalty * 0.6
    if "alcohol" in active_classes and ("opioid" in active_classes or "sedative" in active_classes):
        s.motor_control -= 0.8
        s.alertness -= 0.7

    return s


def interaction_for_state(minute: int, state: StateVector) -> InteractionOutcome:
    npcs = ["shop owner", "pedestrian", "cyclist", "street vendor", "friend", "security guard"]
    actor = random.choice(npcs)

    gait = max(0, -state.motor_control)
    confusion = max(0, state.perception_distortion)
    disinhibition = max(0, -state.inhibition)

    if gait > 2.4:
        event = f"stumbles near a {actor}; speech is slurred and movement is unsteady"
    elif confusion > 2.0:
        event = f"appears disoriented while talking to a {actor}; misreads social cues"
    elif disinhibition > 1.8:
        event = f"overshares with a {actor} and behaves unusually impulsive"
    elif state.alertness > 2.2:
        event = f"talks rapidly to a {actor} and paces restlessly"
    else:
        event = f"has a brief, mostly normal interaction with a {actor}"

    return InteractionOutcome(minute=minute, actor=actor, event=event)


def run_simulation(profile: PersonProfile, events: List[ConsumptionEvent], duration_min: int = 720) -> SimulationResult:
    timeline: List[Dict[str, float]] = []
    interactions: List[InteractionOutcome] = []

    for minute in range(0, duration_min + 1, 15):
        state = state_at_minute(profile, events, minute)
        timeline.append(
            {
                "minute": minute,
                "alertness": round(state.alertness, 3),
                "motor_control": round(state.motor_control, 3),
                "inhibition": round(state.inhibition, 3),
                "perception_distortion": round(state.perception_distortion, 3),
                "anxiety": round(state.anxiety, 3),
            }
        )
        interactions.append(interaction_for_state(minute, state))

    return SimulationResult(timeline=timeline, interactions=interactions)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cross-drug intoxication behavior simulator (educational, not medical).")
    parser.add_argument("--name", default="Subject A")
    parser.add_argument("--age", type=int, default=30)
    parser.add_argument("--sex", default="unspecified")
    parser.add_argument("--height-cm", type=float, default=175)
    parser.add_argument("--weight-kg", type=float, default=78)
    parser.add_argument("--sleep-hours", type=float, default=7)
    parser.add_argument("--tolerance", type=float, default=0.3)
    parser.add_argument("--hydration", type=float, default=0.7)
    parser.add_argument("--duration-min", type=int, default=720)
    parser.add_argument("--event", action="append", default=[], help="Format: key:dose:minute")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list:
        print_catalog()
        return

    random.seed(args.seed)
    profile = PersonProfile(
        name=args.name,
        age=args.age,
        sex=args.sex,
        height_cm=args.height_cm,
        weight_kg=args.weight_kg,
        sleep_hours=args.sleep_hours,
        tolerance=max(0.0, min(1.0, args.tolerance)),
        hydration=max(0.0, min(1.0, args.hydration)),
    )
    events = parse_events(args.event)

    result = run_simulation(profile, events, duration_min=args.duration_min)
    payload = {
        "profile": profile.__dict__,
        "events": [e.__dict__ for e in events],
        "timeline": result.timeline,
        "interactions": [i.__dict__ for i in result.interactions],
        "disclaimer": "This is a simplified educational model. It does not predict real human outcomes.",
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Simulation for {profile.name} ({profile.height_cm} cm, {profile.weight_kg} kg)")
        print(payload["disclaimer"])
        print("\nTop interactions:")
        for item in result.interactions[:10]:
            h = item.minute // 60
            m = item.minute % 60
            print(f" {h:02}:{m:02} - {item.event}")


if __name__ == "__main__":
    main()

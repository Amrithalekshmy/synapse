"""
RL Priority Queue — SYNAPSE
Amritha's module extension.

A lightweight contextual bandit that learns to rank events in the
reviewer's queue by project impact rather than by match confidence alone.

Why this is RL (not just sorting):
  - The policy (weight vector) updates online after every reviewer action.
  - The reward encodes project value: approving a high-risk, high-cascade
    event is worth more than approving a low-stakes one.
  - Over a session the queue visibly reorders — the system learns what
    the reviewer cares about from their behaviour.

Feature vector (5 dimensions):
  [0] match_confidence       — how sure the engine is (0-1)
  [1] schedule_risk_score    — risk level of matched activity (0-1)
  [2] cascade_fan_out_norm   — downstream activities / max_fan_out (0-1)
  [3] hours_in_queue_norm    — hours waiting / 24, capped at 1.0
  [4] discipline_delay_rate  — historical delay rate for this discipline (0-1)

Reward when reviewer acts:
  +2.0 if approved AND HIGH risk activity
  +1.0 if approved AND MEDIUM risk
  +0.5 if approved AND LOW risk
  -1.0 if rejected
  +0.3 * hours_in_queue_norm  (urgency bonus — acts on stale items)

Update rule (online gradient descent / policy gradient):
  w ← w + α * reward * features

Weights are persisted to data/rl_weights.json so the policy survives
server restarts and can be shared via git for cross-device consistency.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


_WEIGHT_DIM = 5
_DEFAULT_WEIGHTS = [0.40, 0.30, 0.15, 0.10, 0.05]  # initial: confidence-heavy
_LEARNING_RATE = 0.05
_RISK_SCORES = {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.1, "": 0.0}

# Historical delay rates per discipline (from knowledge base domain knowledge)
_DISCIPLINE_DELAY_RATES = {
    "piping": 0.68,
    "electrical": 0.42,
    "civil": 0.38,
    "instrumentation": 0.55,
    "mechanical": 0.50,
}


class RLPriorityQueue:
    """
    Online contextual bandit for review-queue prioritisation.

    Usage
    -----
    rl = RLPriorityQueue()
    rl.load("data/rl_weights.json")          # load persisted weights

    score = rl.priority_score(features)      # rank events
    rl.update(features, reward)              # call after each review
    rl.save("data/rl_weights.json")          # persist after update
    """

    def __init__(self) -> None:
        self.weights: list[float] = list(_DEFAULT_WEIGHTS)
        self.update_count: int = 0
        self._max_fan_out: int = 1           # updated as events arrive

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self, path: str) -> None:
        try:
            with open(path) as f:
                data = json.load(f)
            self.weights = data.get("weights", list(_DEFAULT_WEIGHTS))
            self.update_count = data.get("update_count", 0)
            self._max_fan_out = data.get("max_fan_out", 1)
        except (FileNotFoundError, json.JSONDecodeError):
            self.weights = list(_DEFAULT_WEIGHTS)

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(
                {
                    "weights": self.weights,
                    "update_count": self.update_count,
                    "max_fan_out": self._max_fan_out,
                    "feature_names": [
                        "match_confidence",
                        "schedule_risk_score",
                        "cascade_fan_out_norm",
                        "hours_in_queue_norm",
                        "discipline_delay_rate",
                    ],
                    "learning_rate": _LEARNING_RATE,
                    "saved_at": datetime.now(timezone.utc).isoformat(),
                },
                f,
                indent=2,
            )

    # ------------------------------------------------------------------
    # Feature extraction
    # ------------------------------------------------------------------

    def extract_features(
        self,
        match_confidence: float,
        schedule_risk: str,
        cascade_fan_out: int,
        ingested_at: str,
        discipline: Optional[str],
    ) -> list[float]:
        """Build the 5-dim feature vector for one queued event."""
        # Update running max for normalisation
        if cascade_fan_out > self._max_fan_out:
            self._max_fan_out = cascade_fan_out

        hours = 0.0
        try:
            ingested = datetime.fromisoformat(ingested_at.replace("Z", "+00:00"))
            delta = datetime.now(timezone.utc) - ingested
            hours = delta.total_seconds() / 3600
        except Exception:
            pass

        return [
            float(match_confidence),
            _RISK_SCORES.get(schedule_risk, 0.0),
            min(cascade_fan_out / max(self._max_fan_out, 1), 1.0),
            min(hours / 24.0, 1.0),
            _DISCIPLINE_DELAY_RATES.get((discipline or "").lower(), 0.3),
        ]

    # ------------------------------------------------------------------
    # Scoring and update
    # ------------------------------------------------------------------

    def priority_score(self, features: list[float]) -> float:
        """Dot product of weights and features — higher = more urgent."""
        return sum(w * f for w, f in zip(self.weights, features))

    def compute_reward(
        self,
        approved: bool,
        schedule_risk: str,
        hours_in_queue: float,
    ) -> float:
        if not approved:
            return -1.0
        risk_reward = {"HIGH": 2.0, "MEDIUM": 1.0, "LOW": 0.5}.get(schedule_risk, 0.3)
        urgency_bonus = 0.3 * min(hours_in_queue / 24.0, 1.0)
        return risk_reward + urgency_bonus

    def update(self, features: list[float], reward: float) -> None:
        """Online gradient ascent: w ← w + α * reward * features."""
        for i in range(_WEIGHT_DIM):
            self.weights[i] += _LEARNING_RATE * reward * features[i]
        # Clip to keep weights positive and bounded
        self.weights = [max(0.01, min(w, 5.0)) for w in self.weights]
        self.update_count += 1

    def explain_priority(
        self, features: list[float], score: float
    ) -> dict:
        """Return which features drove the priority score."""
        names = [
            "match confidence",
            "schedule risk",
            "cascade impact",
            "time in queue",
            "discipline delay rate",
        ]
        contributions = [
            {"factor": name, "weight": round(self.weights[i], 3),
             "value": round(features[i], 3),
             "contribution": round(self.weights[i] * features[i], 3)}
            for i, name in enumerate(names)
        ]
        contributions.sort(key=lambda x: x["contribution"], reverse=True)
        top = contributions[0]["factor"] if contributions else "—"
        return {
            "score": round(score, 3),
            "top_driver": top,
            "contributions": contributions,
            "updates_so_far": self.update_count,
        }

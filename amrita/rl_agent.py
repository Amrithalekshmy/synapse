"""
RL Decision Agent — SYNAPSE
Amritha's module extension.

Replaces hardcoded confidence thresholds with a learned action-selection
policy that decides, for each incoming event, whether to:

  0  auto_link         — link directly to the top candidate (no human needed)
  1  ask_clarification — send a clarifying question to the site supervisor
  2  send_to_planner   — put in the human review queue

State (8-dim feature vector):
  [0] match_confidence       top candidate score from 7-layer matcher (0–1)
  [1] score_gap              rank-1 minus rank-2 score (0–1); high = unambiguous
  [2] schedule_risk_score    HIGH=1.0, MEDIUM=0.5, LOW=0.1
  [3] cascade_fan_out_norm   downstream activities / max observed (0–1)
  [4] discipline_delay_rate  historical delay rate for this discipline (0–1)
  [5] has_identifier         explicit asset ID present in event text (0 or 1)
  [6] candidate_count_norm   viable candidates (score ≥ 0.50) / 5 (0–1)
  [7] is_vague               event text ≤ 6 words (0 or 1)

Policy:  linear Q-function per action
         q(s, a) = W[a] · s

Decision: argmax_a q(s, a)  with ε-greedy exploration

Update:  policy-gradient style (REINFORCE)
         W[a_chosen] += α * reward * features
         weights clipped to [−10, 10]

Initial weights are calibrated to approximate current threshold behaviour:
  auto_link favours high confidence + clear identifier + large score gap
  ask_clarification favours vague text + very close candidate scores
  send_to_planner   favours moderate confidence + high risk + cascade impact

Weights persisted to data/rl_agent_weights.json so the policy survives
restarts and can be shared across devices via git.
"""

from __future__ import annotations

import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── constants ────────────────────────────────────────────────────────────────

N_ACTIONS = 3
N_FEATURES = 8

ACTION_AUTO_LINK = 0
ACTION_CLARIFY   = 1
ACTION_PLANNER   = 2
ACTION_NAMES     = ["auto_link", "ask_clarification", "send_to_planner"]

FEATURE_NAMES = [
    "match_confidence",
    "score_gap",
    "schedule_risk_score",
    "cascade_fan_out_norm",
    "discipline_delay_rate",
    "has_identifier",
    "candidate_count_norm",
    "is_vague",
]

_RISK_SCORES = {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.1, "": 0.0}

_DISCIPLINE_DELAY_RATES = {
    "piping":           0.68,
    "electrical":       0.42,
    "civil":            0.38,
    "instrumentation":  0.55,
    "mechanical":       0.50,
}

_IDENTIFIER_RE = re.compile(
    r"\b[A-Z]+-\d+\b|\bLine\s+\d+\b|\bUnit\s+\d+\b|\bArea\s+[A-Z]\b",
    re.IGNORECASE,
)

# Calibrated initial weights — approximate current threshold routing so the
# agent starts with sensible behaviour before any learning happens.
#
# Verification (three canonical cases):
#   high-conf (0.90) + identifier + large gap  → auto_link  scores 3.77
#   vague (0.70) + tiny gap + no identifier    → clarify    scores 2.21
#   medium (0.75) + risk HIGH + cascade        → planner    scores 1.93
_DEFAULT_WEIGHTS: list[list[float]] = [
    # conf   gap   risk  casc  disc  has_id cand_n vague
    [ 2.5,  1.5, -0.3,  0.0,  0.0,  1.2, -0.5, -1.5],  # auto_link
    [ 0.0, -3.0,  0.0,  0.0,  0.0, -2.0,  0.5,  2.0],  # ask_clarification
    [ 0.8,  0.5,  1.2,  0.7,  0.4,  0.0,  0.3,  0.0],  # send_to_planner
]

_LEARNING_RATE  = 0.05
_EPSILON_START  = 0.10   # 10 % random exploration initially
_EPSILON_MIN    = 0.02   # floor — never fully deterministic
_EPSILON_DECAY  = 0.99   # per update


# ── agent ────────────────────────────────────────────────────────────────────

class DecisionAgent:
    """
    Online contextual bandit for SYNAPSE routing decisions.

    Usage
    -----
    agent = DecisionAgent()
    agent.load("data/rl_agent_weights.json")

    features = agent.extract_features(...)
    action_name, action_idx, q_values = agent.decide(features)

    # after human review:
    reward = agent.compute_reward(action_idx, approved, confidence, reassigned)
    agent.update(features, action_idx, reward)
    agent.save("data/rl_agent_weights.json")
    """

    def __init__(self) -> None:
        self.weights: list[list[float]] = [list(row) for row in _DEFAULT_WEIGHTS]
        self.update_count: int = 0
        self._max_fan_out: int = 1

    # ── persistence ──────────────────────────────────────────────────────────

    def load(self, path: str) -> None:
        try:
            with open(path) as f:
                data = json.load(f)
            self.weights      = data.get("weights",      [list(r) for r in _DEFAULT_WEIGHTS])
            self.update_count = data.get("update_count", 0)
            self._max_fan_out = data.get("max_fan_out",  1)
        except (FileNotFoundError, json.JSONDecodeError):
            self.weights = [list(r) for r in _DEFAULT_WEIGHTS]

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(
                {
                    "weights":       self.weights,
                    "update_count":  self.update_count,
                    "max_fan_out":   self._max_fan_out,
                    "action_names":  ACTION_NAMES,
                    "feature_names": FEATURE_NAMES,
                    "learning_rate": _LEARNING_RATE,
                    "epsilon":       round(self._epsilon, 4),
                    "saved_at":      datetime.now(timezone.utc).isoformat(),
                },
                f,
                indent=2,
            )

    # ── feature extraction ───────────────────────────────────────────────────

    def extract_features(
        self,
        match_confidence: float,
        candidates: list[dict],
        schedule_risk: str,
        cascade_fan_out: int,
        discipline: Optional[str],
        event_text: str,
    ) -> list[float]:
        """Build the 8-dim state feature vector for one incoming event."""
        # Score gap between best and second-best candidate
        scores = sorted(
            [c.get("score", 0.0) for c in (candidates or [])], reverse=True
        )
        if len(scores) >= 2:
            gap = scores[0] - scores[1]
        elif scores:
            gap = scores[0]
        else:
            gap = 0.0

        # Running max for cascade normalisation
        if cascade_fan_out > self._max_fan_out:
            self._max_fan_out = cascade_fan_out
        cascade_norm = min(cascade_fan_out / max(self._max_fan_out, 1), 1.0)

        word_count    = len(event_text.strip().split())
        is_vague      = 1.0 if word_count <= 6 else 0.0
        has_identifier = 1.0 if _IDENTIFIER_RE.search(event_text) else 0.0

        viable = sum(1 for c in (candidates or []) if c.get("score", 0.0) >= 0.50)
        candidate_count_norm = min(viable / 5.0, 1.0)

        return [
            float(min(max(match_confidence, 0.0), 1.0)),
            float(min(max(gap, 0.0), 1.0)),
            _RISK_SCORES.get(schedule_risk, 0.0),
            cascade_norm,
            _DISCIPLINE_DELAY_RATES.get((discipline or "").lower(), 0.3),
            has_identifier,
            candidate_count_norm,
            is_vague,
        ]

    # ── policy ───────────────────────────────────────────────────────────────

    @property
    def _epsilon(self) -> float:
        return max(_EPSILON_MIN, _EPSILON_START * (_EPSILON_DECAY ** self.update_count))

    def decide(
        self, features: list[float], explore: bool = True
    ) -> tuple[str, int, list[float]]:
        """
        Returns (action_name, action_index, q_values).
        Greedy w.r.t. Q unless ε-greedy exploration fires.
        """
        q_values = [
            sum(self.weights[a][i] * features[i] for i in range(N_FEATURES))
            for a in range(N_ACTIONS)
        ]
        if explore and random.random() < self._epsilon:
            action_idx = random.randint(0, N_ACTIONS - 1)
        else:
            action_idx = q_values.index(max(q_values))

        return ACTION_NAMES[action_idx], action_idx, [round(q, 4) for q in q_values]

    # ── reward and update ────────────────────────────────────────────────────

    def compute_reward(
        self,
        action_idx: int,
        approved: bool,
        match_confidence: float,
        was_reassigned: bool,
    ) -> float:
        """
        Reward signal derived from the human reviewer's decision.

        send_to_planner:
          reassigned (wrong top match)  → +2.0  right call, saved an error
          rejected                      → +1.5  right call
          approved, confidence < 0.80   → +1.0  borderline, right to escalate
          approved, confidence ≥ 0.80   → -0.5  could have auto-linked; wasted effort

        ask_clarification:
          approved after clarification  → +0.8  question helped
          rejected                      → -0.3  clarification didn't help

        auto_link (reached review — means it was wrong):
          any outcome                   → -2.0  agent was overconfident
        """
        if action_idx == ACTION_PLANNER:
            if was_reassigned:
                return +2.0
            if not approved:
                return +1.5
            return +1.0 if match_confidence < 0.80 else -0.5

        if action_idx == ACTION_CLARIFY:
            return +0.8 if approved else -0.3

        # ACTION_AUTO_LINK that ended up in review queue — shouldn't happen normally
        return -2.0

    def update(self, features: list[float], action_idx: int, reward: float) -> None:
        """REINFORCE gradient step on the chosen action's weight vector."""
        for i in range(N_FEATURES):
            self.weights[action_idx][i] += _LEARNING_RATE * reward * features[i]
        # Clip to keep weights bounded
        for i in range(N_FEATURES):
            self.weights[action_idx][i] = max(-10.0, min(10.0, self.weights[action_idx][i]))
        self.update_count += 1

    # ── explainability ───────────────────────────────────────────────────────

    def explain(
        self,
        features: list[float],
        action_name: str,
        action_idx: int,
        q_values: list[float],
    ) -> dict:
        contributions = [
            {
                "factor":       FEATURE_NAMES[i],
                "weight":       round(self.weights[action_idx][i], 3),
                "value":        round(features[i], 3),
                "contribution": round(self.weights[action_idx][i] * features[i], 3),
            }
            for i in range(N_FEATURES)
        ]
        contributions.sort(key=lambda x: abs(x["contribution"]), reverse=True)
        return {
            "action":        action_name,
            "q_values":      {ACTION_NAMES[i]: q_values[i] for i in range(N_ACTIONS)},
            "top_driver":    contributions[0]["factor"] if contributions else "—",
            "contributions": contributions,
            "epsilon":       round(self._epsilon, 3),
            "updates_so_far": self.update_count,
        }

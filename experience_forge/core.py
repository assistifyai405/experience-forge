"""Declarative program search, independent evaluation, and persisted skill versions.

No model calls, arbitrary code execution, or model weight updates occur here.
"""

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Any


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint(value: Any) -> str:
    return sha256(canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class Input:
    value: str | None
    delimiter: str
    source: str


@dataclass(frozen=True)
class Case:
    id: str
    input: Input
    expected_cents: int | None


def input_key(item: Input) -> str:
    # Source names are metadata, never a learned feature. Changing that name must
    # not hide repeated inputs or contradictory supervision.
    return fingerprint({"value": item.value, "delimiter": item.delimiter})


# These are predefined language primitives, not conclusions discovered by the demo.
# Search can select a rule but cannot invent features outside this bounded language.
FEATURES = {
    "always": (0, "always use comma-decimal parsing"),
    "semicolon": (1, "use comma-decimal parsing when the delimiter is a semicolon"),
    "contains_comma": (1, "use comma-decimal parsing when the value contains a comma"),
    "comma_fraction": (2, "use comma-decimal parsing for a final comma and 1–2 digits"),
}


def applies(feature: str, item: Input) -> bool:
    if feature == "baseline":
        return False
    if feature == "always":
        return True
    if feature == "semicolon":
        return item.delimiter == ";"
    if feature == "contains_comma":
        return "," in (item.value or "")
    if feature == "comma_fraction":
        return bool(re.search(r",[0-9]{1,2}$", (item.value or "").strip()))
    raise ValueError(f"Unknown rule: {feature}")


def parse_cents(value: str | None, comma_decimal: bool) -> int | None:
    if not isinstance(value, str) or len(value) > 128:
        return None
    value = value.strip()
    # Restricted demonstration domain: ASCII decimal literals, signs and grouping.
    # Unsupported values abstain; this is not a general financial/CSV parser.
    if not re.fullmatch(r"[+-]?[0-9][0-9.,]*", value):
        return None
    normalized = value.replace(".", "").replace(",", ".") if comma_decimal else value.replace(",", "")
    try:
        with localcontext() as context:
            context.prec = 160
            cents = Decimal(normalized) * 100
            if not cents.is_finite() or cents != cents.to_integral_value():
                return None
            return int(cents)
    except (InvalidOperation, ValueError):
        return None


@dataclass(frozen=True)
class Skill:
    feature: str = "baseline"

    def __post_init__(self) -> None:
        if self.feature not in {"baseline", *FEATURES}:
            raise ValueError("Skill is outside the allowed language")

    def run(self, item: Input) -> int | None:
        return parse_cents(item.value, applies(self.feature, item))

    @property
    def description(self) -> str:
        return "use dot-decimal parsing" if self.feature == "baseline" else FEATURES[self.feature][1] + "; otherwise retain dot-decimal parsing"


def evaluate(skill: Skill, cases: list[Case]) -> dict[str, Any]:
    rows = []
    for case in cases:
        predicted = skill.run(case.input)
        rows.append({"id": case.id, "input": asdict(case.input), "expected_cents": case.expected_cents,
                     "predicted_cents": predicted, "passed": predicted == case.expected_cents})
    return {"correct": sum(row["passed"] for row in rows), "total": len(rows), "rows": rows}


def propose(experiences: list[Case]) -> list[Skill]:
    """Search the fixed DSL using training feedback only; never receives test labels."""
    if not experiences:
        raise ValueError("Learning requires observed, labelled experiences")
    seen = {}
    for case in experiences:
        key = input_key(case.input)
        if key in seen and seen[key] != case.expected_cents:
            raise ValueError("Conflicting feedback: resolve labels before learning")
        seen[key] = case.expected_cents
    ranked = []
    for name, (complexity, _) in FEATURES.items():
        skill = Skill(name)
        result = evaluate(skill, experiences)
        ranked.append((len(experiences) - result["correct"], complexity, name, skill))
    ranked.sort(key=lambda entry: entry[:3])
    # Proposals must strictly improve the observed experiences over the baseline.
    before = evaluate(Skill(), experiences)["correct"]
    return [entry[3] for entry in ranked if len(experiences) - entry[0] > before]


def qualify(candidate: Skill, current: Skill, retention: list[Case], qualification: list[Case]) -> dict[str, Any]:
    """Reject any individual regression, including those masked by aggregate gains."""
    if not retention or not qualification:
        raise ValueError("Both retention and qualification evidence are required")
    old_retention, new_retention = evaluate(current, retention), evaluate(candidate, retention)
    old_qualification, new_qualification = evaluate(current, qualification), evaluate(candidate, qualification)
    regressions = []
    for old, new in ((old_retention, new_retention), (old_qualification, new_qualification)):
        regressions.extend(b["id"] for a, b in zip(old["rows"], new["rows"], strict=True) if a["passed"] and not b["passed"])
    gain = new_qualification["correct"] - old_qualification["correct"]
    accepted = not regressions and gain > 0
    return {"candidate": candidate.feature, "accepted": accepted, "gain": gain,
            "regressions": regressions, "retention": new_retention, "qualification": new_qualification,
            "reason": "improvement without observed regression" if accepted else "regression" if regressions else "no new improvement"}


def assert_disjoint(splits: dict[str, list[Case]]) -> None:
    ids, inputs = set(), set()
    for name, cases in splits.items():
        if not cases:
            raise ValueError(f"Empty split: {name}")
        for case in cases:
            key = input_key(case.input)
            if case.id in ids or key in inputs:
                raise ValueError("Duplicate case or input across splits")
            ids.add(case.id)
            inputs.add(key)


class Store:
    """Local episode journal and transactional active skill version."""

    def __init__(self, path: Path):
        self.connection = sqlite3.connect(path)
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS skills (version INTEGER PRIMARY KEY, feature TEXT NOT NULL, gate_event INTEGER,
                FOREIGN KEY(gate_event) REFERENCES events(id));
            CREATE TABLE IF NOT EXISTS active (singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL,
                FOREIGN KEY(version) REFERENCES skills(version));
            INSERT OR IGNORE INTO skills VALUES (0, 'baseline', NULL);
            INSERT OR IGNORE INTO active VALUES (1, 0);
        """)

    def close(self) -> None:
        self.connection.close()

    def event(self, kind: str, payload: Any) -> int:
        cursor = self.connection.execute("INSERT INTO events(kind, payload) VALUES (?, ?)", (kind, canonical(payload)))
        return int(cursor.lastrowid)

    def active(self) -> tuple[int, Skill]:
        row = self.connection.execute("SELECT s.version, s.feature FROM skills s JOIN active a ON a.version=s.version").fetchone()
        return row[0], Skill(row[1])

    def record_experiences(self, cases: list[Case]) -> None:
        with self.connection:
            for case in cases:
                self.event("experience", asdict(case))

    def attempt(self, candidate: Skill, retention: list[Case], qualification: list[Case]) -> dict[str, Any]:
        # Serialize evaluation and promotion: a concurrent update cannot stale the gate.
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            version, current = self.active()
            gate = qualify(candidate, current, retention, qualification)
            event = self.event("qualification", gate)
            if gate["accepted"]:
                next_version = self.connection.execute("SELECT MAX(version)+1 FROM skills").fetchone()[0]
                self.connection.execute("INSERT INTO skills VALUES (?, ?, ?)", (next_version, candidate.feature, event))
                self.connection.execute("UPDATE active SET version=? WHERE singleton=1", (next_version,))
                self.event("promotion", {"from": version, "to": next_version, "feature": candidate.feature})
            self.connection.commit()
            return gate
        except Exception:
            self.connection.rollback()
            raise

    def rollback(self, version: int) -> None:
        with self.connection:
            if not self.connection.execute("SELECT 1 FROM skills WHERE version=?", (version,)).fetchone():
                raise ValueError("Unknown skill version")
            old, _ = self.active()
            self.connection.execute("UPDATE active SET version=? WHERE singleton=1", (version,))
            self.event("rollback", {"from": old, "to": version})

    def journal(self) -> list[dict[str, Any]]:
        return [{"id": row[0], "kind": row[1], "payload": json.loads(row[2])}
                for row in self.connection.execute("SELECT id, kind, payload FROM events ORDER BY id")]

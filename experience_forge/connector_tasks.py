"""Synthetic, opaque connector calibration tasks with independent state grading."""
from dataclasses import asdict, dataclass
import random
import sqlite3

from .core import fingerprint


@dataclass(frozen=True)
class ConnectorCase:
    id: str
    source: str
    revision: str
    raw: int | None
    examples: tuple[tuple[int, int], ...]
    expected: int | None
    category: str = "known-contract"

    def public(self) -> dict:
        return {"case_id": self.id, "source": self.source, "revision": self.revision,
                "encoded_quantity": self.raw}


def make_connector_splits(seed: int) -> dict[str, list[ConnectorCase]]:
    rng = random.Random(seed)
    source_names = [f"sensor-{rng.getrandbits(32):08x}" for _ in range(2)]
    contracts = [(source, "r1", rng.randint(2, 9), rng.randint(-25, 35)) for source in source_names]
    splits = {name: [] for name in ("training", "qualification", "transfer")}
    for source, revision, scale, offset in contracts:
        used = {0, 10}
        examples = ((offset, 0), (10 * scale + offset, 10))
        for partition, count in (("training", 1), ("qualification", 2), ("transfer", 3)):
            for index in range(count):
                target = rng.randint(11, 99)
                while target in used:
                    target = rng.randint(11, 99)
                used.add(target)
                splits[partition].append(ConnectorCase(f"{seed}-{partition}-{source}-{index}", source,
                    revision, target * scale + offset, examples, target))
    # An unseen revision requires fresh calibration rather than reusing r1 memory.
    source, _, old_scale, old_offset = contracts[0]
    scale, offset = old_scale + 3, old_offset - 9
    target = rng.randint(100, 140)
    splits["transfer"].append(ConnectorCase(f"{seed}-revision-change", source, "r2", target * scale + offset,
        ((offset, 0), (10 * scale + offset, 10)), target, "unseen-revision"))
    splits["transfer"].append(ConnectorCase(f"{seed}-missing", source_names[1], "r1", None,
        contracts_to_examples(contracts[1]), None, "missing-input"))
    assert_connector_disjoint(splits)
    return splits


def contracts_to_examples(contract: tuple) -> tuple[tuple[int, int], ...]:
    _, _, scale, offset = contract
    return ((offset, 0), (10 * scale + offset, 10))


def assert_connector_disjoint(splits: dict[str, list[ConnectorCase]]) -> None:
    seen_ids, seen_inputs = set(), set()
    for cases in splits.values():
        if not cases:
            raise ValueError("Empty connector partition")
        for case in cases:
            key = fingerprint({"source": case.source, "revision": case.revision, "raw": case.raw})
            if key in seen_inputs or case.id in seen_ids:
                raise ValueError("Connector input overlaps between partitions")
            seen_inputs.add(key)
            seen_ids.add(case.id)


@dataclass(frozen=True)
class AffineRule:
    source: str
    revision: str
    scale: int
    offset: int

    def __post_init__(self):
        if not isinstance(self.source, str) or not 1 <= len(self.source) <= 80:
            raise ValueError("Invalid rule source")
        if not isinstance(self.revision, str) or not 1 <= len(self.revision) <= 30:
            raise ValueError("Invalid rule revision")
        if type(self.scale) is not int or not 1 <= self.scale <= 1000:
            raise ValueError("Invalid rule scale")
        if type(self.offset) is not int or abs(self.offset) > 100000:
            raise ValueError("Invalid rule offset")

    def apply(self, case: ConnectorCase) -> int | None:
        if (case.source, case.revision) != (self.source, self.revision) or case.raw is None:
            return None
        numerator = case.raw - self.offset
        return numerator // self.scale if numerator % self.scale == 0 else None


def qualify_rule(rule: AffineRule, qualification: list[ConnectorCase], retained: list[tuple[AffineRule, ConnectorCase]]) -> dict:
    scoped = [case for case in qualification if (case.source, case.revision) == (rule.source, rule.revision)]
    if len(scoped) < 2 or len({case.raw for case in scoped}) < 2 or any(case.expected is None for case in scoped):
        return {"accepted": False, "reason": "insufficient independent evidence", "rows": [], "regressions": []}
    rows = [{"id": case.id, "expected": case.expected, "prediction": rule.apply(case),
             "passed": rule.apply(case) == case.expected} for case in scoped]
    regressions = []
    for old, case in retained:
        replacement = rule if (case.source, case.revision) == (rule.source, rule.revision) else old
        if old.apply(case) == case.expected and replacement.apply(case) != case.expected:
            regressions.append(case.id)
    passed = all(row["passed"] for row in rows) and not regressions
    return {"accepted": passed, "reason": "independent cases passed" if passed else "failed independent evidence or regression",
            "rows": rows, "regressions": regressions}


TOOLS = [
    {"type": "function", "function": {"name": "read_calibration", "description": "Read two calibration examples for this exact source/revision. Use them to infer encoded = scale * quantity + offset.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}},
    {"type": "function", "function": {"name": "normalize_quantity", "description": "Calculate quantity from this task's encoded value using your chosen integer scale and offset. Does not save.",
        "parameters": {"type": "object", "properties": {"scale": {"type": "integer"}, "offset": {"type": "integer"}}, "required": ["scale", "offset"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "save_quantity", "description": "Save the normalized integer quantity once. Only call after determining a supported quantity; missing input must not be saved.",
        "parameters": {"type": "object", "properties": {"quantity": {"type": "integer"}}, "required": ["quantity"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "read_saved_quantity", "description": "Read the actual saved quantity to verify the write before reporting completion.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}},
]


class ConnectorWorld:
    """Each rollout owns a fresh SQLite state. Gold labels never reach tools."""
    def __init__(self, case: ConnectorCase):
        self.case = case
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE saved (quantity INTEGER NOT NULL)")
        self.events = []
        self.write_attempts = 0

    def execute(self, name: str, args: dict) -> dict:
        try:
            if not isinstance(args, dict):
                raise ValueError("Tool arguments must be an object")
            required = {"read_calibration": set(), "read_saved_quantity": set(),
                        "normalize_quantity": {"scale", "offset"}, "save_quantity": {"quantity"}}
            if name not in required or set(args) != required[name]:
                raise ValueError("Unknown tool or invalid argument keys")
            if name == "read_calibration":
                result = {"source": self.case.source, "revision": self.case.revision,
                          "examples": [{"encoded": encoded, "quantity": quantity} for encoded, quantity in self.case.examples]}
            elif name == "normalize_quantity":
                rule = AffineRule(self.case.source, self.case.revision, args["scale"], args["offset"])
                quantity = rule.apply(self.case)
                result = {"quantity": quantity, "supported": quantity is not None}
            elif name == "save_quantity":
                self.write_attempts += 1
                if self.write_attempts != 1 or self.case.raw is None:
                    raise ValueError("Repeated or missing-input write is prohibited")
                quantity = args["quantity"]
                if type(quantity) is not int or abs(quantity) > 1000000:
                    raise ValueError("Expected a bounded integer")
                self.db.execute("INSERT INTO saved VALUES (?)", (quantity,))
                result = {"saved": True}
            else:
                row = self.db.execute("SELECT quantity FROM saved").fetchone()
                result = {"saved_quantity": None if row is None else row[0]}
        except (ValueError, TypeError) as error:
            result = {"error": str(error)}
        self.events.append({"tool": name, "arguments": args, "result": result})
        return result

    def grade(self, finished: bool) -> dict:
        row = self.db.execute("SELECT quantity FROM saved").fetchone()
        actual = None if row is None else row[0]
        verified = any(event["tool"] == "read_saved_quantity" and not event["result"].get("error")
            and event["result"].get("saved_quantity") == self.case.expected for event in self.events)
        if self.case.expected is None:
            passed = finished and actual is None and self.write_attempts == 0
        else:
            passed = finished and actual == self.case.expected and self.write_attempts == 1 and verified
        return {"passed": passed, "expected": self.case.expected, "actual": actual,
                "verified": verified, "write_attempts": self.write_attempts,
                "calibration_reads": sum(event["tool"] == "read_calibration" for event in self.events)}

    def close(self):
        self.db.close()

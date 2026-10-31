"""Load and validate host/channel_plan.yaml (API-3, AIR-5)."""
from pathlib import Path

import yaml

PATH = Path(__file__).with_name("channel_plan.yaml")
GAPS = [(2423, 2426), (2448, 2451), (2473, 2480)]  # 2 MHz carriers clear of Wi-Fi 1/6/11 (sim/loss/RESULTS.md s2)


def _gap(f):
    return any(lo <= f <= hi for lo, hi in GAPS)


def validate(plan):
    packs = plan.get("packs") if isinstance(plan, dict) else None
    if not isinstance(packs, dict) or sorted(packs) != list(range(1, 9)):
        raise ValueError("plan must define packs 1..8")
    freqs, load = [], {}
    for pid, p in packs.items():
        a, b = p["fA"], p["fB"]
        if not (2402 <= a <= 2440):
            raise ValueError(f"pack {pid}: fA {a} outside 2402-2440")
        if b < a + 40 or b > 2480:
            raise ValueError(f"pack {pid}: fB {b} must be in [fA+40, 2480]")
        if _gap(a) + _gap(b) != 1:
            raise ValueError(f"pack {pid}: needs exactly one gap carrier")
        freqs += [a, b]
        for f in (a, b):
            if not _gap(f):
                ch = min((2412, 2437, 2462), key=lambda c: abs(f - c))  # nearest Wi-Fi 1/6/11
                load[ch] = load.get(ch, 0) + 1
    if max(load.values()) > 4:
        raise ValueError(f"more than 4 in-band carriers under one Wi-Fi channel: {load}")
    freqs.sort()
    if any(y - x < 2 for x, y in zip(freqs, freqs[1:])):
        raise ValueError("carriers must be distinct and >= 2 MHz apart")
    return {int(k): (v["fA"], v["fB"]) for k, v in packs.items()}


def load(path=PATH):
    return validate(yaml.safe_load(Path(path).read_text()))

"""Load and validate host/channel_plan.yaml (API-3, AIR-5, ADR-0015)."""
from pathlib import Path

import yaml

PATH = Path(__file__).with_name("channel_plan.yaml")        # UK, the default region (ADR-0015)
PATH_US = Path(__file__).with_name("channel_plan_us.yaml")  # US: no 2482, pack 1 in-band (ADR-0016)
REGIONS = ("UK", "US")  # SYS-5 / AIR-6 power limit; ADR-0015
GAPS = [(2423, 2426), (2448, 2451), (2473, 2482)]  # carriers clear of Wi-Fi 1/6/11 (sim/loss/RESULTS.md s2)
# Highest carrier by region (ADR-0016): under EN 300 328 a 2482 MHz BLE-2M carrier keeps its 99 % OBW inside
# 2400-2483.5 and its OOB under the 4.3.2.8 mask (audit.py Audit 5); US stops at 2480 (15.205 restricted band).
FB_MAX = {"UK": 2482, "US": 2480}
WIFI = (2412, 2437, 2462)                            # Wi-Fi 1/6/11 centres
WIFI_13 = 2472                                       # UK only: Wi-Fi 13, occupied ~2463-2481
MIN_SPACING = 3   # MHz between any two carriers: 2 MHz neighbours collide at 2 Mbit GFSK (bsim, #76)
NEAR_SPACING = 5  # MHz from a pack next to an antenna (20 dB stronger) for a carrier to survive (bsim, #76)
GAP_PACKS = {"UK": 8, "US": 7}  # gap carriers at 3 MHz: 2+2+4 up to 2482 (UK); 2+2+3 up to 2480 (US, one pack has none)


def _gap(f):
    return any(lo <= f <= hi for lo, hi in GAPS)


def _far(f, others, d=NEAR_SPACING):
    return all(abs(f - g) >= d for g in others)


def validate(plan):
    packs = plan.get("packs") if isinstance(plan, dict) else None
    if not isinstance(packs, dict) or sorted(packs) != list(range(1, 9)):
        raise ValueError("plan must define packs 1..8")
    if plan.get("region") not in REGIONS:
        raise ValueError(f"region must be one of {REGIONS}")
    reg = plan["region"]
    pairs = {int(k): (v["fA"], v["fB"]) for k, v in packs.items()}
    for k, v in packs.items():
        if not isinstance(v.get("td", False), bool):
            raise ValueError(f"pack {k}: td must be true or false (ADR-0017)")
    freqs, load, gapped = [], {}, 0
    for pid, (a, b) in pairs.items():
        if not (2402 <= a <= 2440):
            raise ValueError(f"pack {pid}: fA {a} outside 2402-2440")
        if b < a + 40 or b > FB_MAX[reg]:
            raise ValueError(f"pack {pid}: fB {b} must be in [fA+40, {FB_MAX[reg]}] ({reg})")
        n = _gap(a) + _gap(b)
        if n > 1:
            raise ValueError(f"pack {pid}: two gap carriers")
        gapped += n
        freqs += [a, b]
        for f in (a, b):
            if not _gap(f):
                ch = min(WIFI, key=lambda c: abs(f - c))
                load[ch] = load.get(ch, 0) + 1
    if gapped < GAP_PACKS[reg]:
        raise ValueError(f"only {gapped} packs have a gap carrier, need {GAP_PACKS[reg]} ({reg})")
    if max(load.values()) > 4:
        raise ValueError(f"more than 4 in-band carriers under one Wi-Fi channel: {load}")
    freqs.sort()
    if any(y - x < MIN_SPACING for x, y in zip(freqs, freqs[1:])):
        raise ValueError(f"carriers must be distinct and >= {MIN_SPACING} MHz apart (#76)")
    for near, nf in pairs.items():
        for pid, pf in pairs.items():
            if pid == near:
                continue
            if not any(_far(f, nf) for f in pf):
                raise ValueError(f"pack {pid} loses both copies when pack {near} is near an antenna")
            if not (_gap(nf[0]) or _gap(nf[1])) and not all(_far(f, nf) for f in pf):
                raise ValueError(f"pack {pid}: carrier < {NEAR_SPACING} MHz from no-gap pack {near}")
    return pairs


def gap_lost_to_wifi13(pairs):
    """UK: packs whose gap carrier sits under Wi-Fi 13 if a venue uses it: within 10 MHz of 2472. 2482 is 10 MHz
    from it, as 2402 is from Wi-Fi 1, and would need 18.4 dB of isolation (audit.py Audit 4), so it counts as lost."""
    return sorted(k for k, ab in pairs.items() if any(_gap(f) and abs(f - WIFI_13) <= 10 for f in ab))


def td(path=PATH):
    """Packs with time diversity on (optional `td: true` per pack, default off, ADR-0017). The booth pushes it to
    the receiver (`td on|off`) on pair; the pack itself is set over USB (`td on`) at configuration time."""
    plan = yaml.safe_load(Path(path).read_text())
    validate(plan)
    return {int(k) for k, v in plan["packs"].items() if v.get("td", False)}


def region(path=PATH):
    return yaml.safe_load(Path(path).read_text())["region"]


def load(path=PATH):
    return validate(yaml.safe_load(Path(path).read_text()))

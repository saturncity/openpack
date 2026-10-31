import pathlib

import yaml

P = yaml.safe_load((pathlib.Path(__file__).parent / "bsim" / "wlan_params.yaml").read_text())
RANGE = {"busy_fraction": (0.01, 0.9), "mean_burst_frames": (1, 10), "DataRate": (1, 54),
         "pr": (0, 1), "sigma": (0, 100), "power": (0, 30), "ConfigSet": (5, 100)}


def test_sets():
    assert P["scenario"]["wifi_channels"] == [1, 6, 11]
    for s in P["sets"].values():
        for group in s.values():
            for k, v in group.items():
                assert v["source"] and isinstance(v["estimate"], bool), k
                if k in RANGE:
                    assert RANGE[k][0] <= v["value"] <= RANGE[k][1], k

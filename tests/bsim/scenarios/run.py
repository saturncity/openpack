#!/usr/bin/env python3
"""G2 bsim scenarios (a)-(e) (#27; PLAN.md Phase 2, SPEC.md section 9). One runner for CI and local.

usage: run.py [--long] [--only abcde] [--build DIR] [--no-build] [--out DIR] [--jobs N] [--keep]
needs BSIM_OUT_PATH, BSIM_COMPONENTS_PATH and a west workspace (ZEPHYR_BASE, Zephyr SDK) for the builds.

Builds 5 images (pack, receiver, pack that goes silent after 3 s, and both at the time-diversity packet
length) once; every pack id and carrier pair comes from host/channel_plan.yaml through the bsim-only
-op_pack_id/-op_ch_a/-op_ch_b options (CONFIG_OP_TEST_BSIM_ARGS). Each scenario launches the 2G4 phy
(multiatt channel, BLE_simple modem) + N packs + N receivers + optional 3 WLAN_actmod interferers on
Wi-Fi 1/6/11, every process under `timeout` with -sim_length, all killed on exit (hands-off.md).

Geometry (ADR-0003, as tests/bsim/probe/run.sh): pack +20 dBm EIRP at 10 m = 0 dBm radio + 40.2 dB to the
rack; Wi-Fi at 2 m = 46.2 dB; the near pack in (c) is at -20 dBm at the rack (20 dB). Wi-Fi sets are the
calibrated ones in tests/bsim/wlan_params.yaml (10 % and 40 % from #18, 25 % from #27).

Evidence per frame comes from the phy dumps: a copy counts if the receiver's Rx dump has a status-OK
reception of it (sync within 20-30 us of the pack's Tx start, the pack's access address). Time diversity
(TD, AIR-3/RX-4, ADR-0001) is not in firmware yet (#26): TD runs use 81 B packets (OP_TEST_FRAME_LEN) so
the per-copy loss is measured at the TD air time, and frame n counts as recovered when any copy of
packet n or n+2 arrived. Firmware loss (receiver app core RXAPP lines) is cross-checked against TD off.

Asserted (exit code != 0 on failure), per ADR-0003 / ADR-0010:
  (a) SYS-2 sim latency <= 1.6 ms excl. I2S and ADC/DAC filters; RX-2 lock <= 2 s; 0 lost frames.
  (b) channel-plan pack 8 (fA under Wi-Fi 6, fB in a gap) at 10/25/40 % busy: SYS-3 at 40 % with TD on.
      Both carriers under Wi-Fi (2437/2462) is reported, not asserted (no gap carrier, AIR-5 forbids it).
  (c) 8 packs + 8 receivers, near pack at -20 dBm: no cross-pack copy loss without Wi-Fi; SYS-3 per pack
      at 40 % with TD on (loss <= 0.1 %, <= 2 consecutive lost frames). Events/h reported (ADR-0010).
  (d) +-40 ppm (pack +40, receiver -40): radio tracking holds, 0 lost, 0 seq skips, 0 re-acquire.
      RX-7 (#24): tests/bsim/rx/run.sh d and dn (+-20 ppm each way, check_d.py: 0 slot slips, <= 1
      sample/h), --d-secs long (CI 300 s per PR, 3600 s nightly).
  (e) pack reboot twice: RX-2 re-lock <= 2 s each time, 0 loss while locked (RX-10), tests/bsim/rx/check.py.
Known failures are XFAIL with the issue that explains them (#76: channel plan); they do not fail the run
but keep "G2 gate MET" false.
Region knobs (UK EN 300 328 vs US, see --help): --eirp (pack EIRP, sets the pack -> rack path loss),
--wifi (interferer channels, e.g. 1,5,9,13), --plan (carrier pairs), --inband. (a)/(d)/(e) use the
Kconfig OP_CH_A_MHZ/OP_CH_B_MHZ defaults read from fw/Kconfig.
"""
import argparse
import bisect
import concurrent.futures
import csv
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BOARD = "nrf5340bsim/nrf5340/cpuapp"
TD = ["-Dfw_net_CONFIG_OP_TEST_FRAME_LEN=81"]  # net core only: the app cores keep the v1 42 B frame (codec)
IMAGES = {  # name: west build -- args (sysbuild; fw = app core image, fw_net = net core image)
    "pack": [],
    "rx": ["-DSB_CONFIG_OP_ROLE_RX=y"],
    "pack3s": ["-Dfw_net_CONFIG_OP_PACK_TEST_RUN_MS=3000"],
    # TD length: 2 x 368 us copies + T_GAP leave no room for the AIR-4 RX slot or a +-50 us window.
    "pack_td": TD + ["-Dfw_net_CONFIG_OP_RX_WINDOW_US=0"],
    "rx_td": ["-DSB_CONFIG_OP_ROLE_RX=y"] + TD + ["-Dfw_net_CONFIG_OP_RX_TRACK_WIN_US=10"],
}
PL_10M, ATT_WLAN, ATT_NEAR, ATT_DEFAULT = 60.2, 46.2, 20.0, 60.0  # free space 2.44 GHz: 10 m, 2 m; near
ATT_PACK = PL_10M - 20  # pack radio 0 dBm + att = EIRP - path loss; set from --eirp in main()
WLAN = {  # busy fraction -> actmod args, tests/bsim/wlan_params.yaml
    10: ["-ConfigSet=10", "-power=15"],
    25: ["-ConfigSet=25", "-power=20"],
    40: ["-ConfigSet=50", "-sigma=0.9", "-power=20"],
}
WIFI_CH = [1, 6, 11]  # --wifi


def kconfig_default(sym):
    m = re.search(rf"^config {sym}\n(?:\t.*\n)*?\tdefault (\d+)", (REPO / "fw/Kconfig").read_text(), re.M)
    return int(m[1])
RAMP_TX = 41  # bsim TXEN -> on air, fast ramp-up (tests/bsim/sched/check.py)
RAMP_RX = 40  # RXEN -> RX start
ENC_IPC_US, OUT_SLOT_US = 100, 200  # SPEC section 2: encode + IPC; output deadline = copy B end + 200
I2S_FILTERS_US = 1000 + 170 + 350 + 400  # frame accumulation, DAC DMA block, ADC and DAC filters (SPEC 2)
TD_US = 2000  # time diversity: frame n is played after packet n+2 (SPEC 2)
SYS2_SIM_MAX, LOCK_MAX = 1600, 2.0
SYS3_LOSS, SYS3_RUN = 0.001, 2
XF_PLAN = "#76"  # channel plan: 2 MHz-spaced carriers collide; near pack blocks 3 MHz neighbours


def crowded(links, near):
    """Pack labels with a carrier <= 2 MHz from another pack's, or <= 4 MHz from the near pack's (#76)."""
    hit = set()
    for k, *_, fa, fb in links:
        if str(near) == k:
            continue  # 20 dB stronger than its neighbours
        for j, *_, ga, gb in links:
            lim = 4 if str(near) == j != k else 2
            if j != k and any(abs(f - g) <= lim for f in (fa, fb) for g in (ga, gb)):
                hit.add(k)
    return hit


def plan(path):
    """host/channel_plan.yaml -> {id: (fA, fB)}; tiny parser, the file is flat."""
    out = {}
    for m in re.finditer(r"^\s*(\d+):\s*\{fA:\s*(\d+),\s*fB:\s*(\d+)\}", Path(path).read_text(), re.M):
        out[int(m[1])] = (int(m[2]), int(m[3]))
    assert len(out) == 8, out
    return out


def aa(pack_id):
    return (0x8E89BED6 ^ ((pack_id * 0x9E3779B1) & 0xFFFFFFFF)) & 0xFFFFFFFF


# ---------------------------------------------------------------- builds

def build(names, bdir, jobs, skip):
    exes = {n: bdir / n / "zephyr" / "zephyr.exe" for n in names}
    if skip:
        missing = [n for n, e in exes.items() if not e.exists()]
        assert not missing, f"--no-build but missing images: {missing}"
        return exes

    def one(n):
        t = time.time()
        log = bdir / f"{n}.build.log"
        cmd = ["west", "build", "-p", "auto", "-b", BOARD, str(REPO / "fw"), "-d", str(bdir / n), "--sysbuild",
               "--"] + IMAGES[n]
        with open(log, "w") as f:
            r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
        if r.returncode:
            sys.stdout.write(log.read_text()[-3000:])
            raise SystemExit(f"build {n} failed ({log})")
        return n, time.time() - t

    bdir.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(jobs) as ex:
        for n, dt in ex.map(one, names):
            print(f"built {n} in {dt:.0f} s", flush=True)
    return exes


# ---------------------------------------------------------------- simulation

class Sim:
    """One bsim run: phy + devices. dev(): add a device, run(): launch all, wait, return logs."""

    def __init__(self, name, secs, out):
        self.sid = f"g2_{name}_{os.getpid()}"
        self.name, self.secs, self.out = name, secs, out
        self.devs, self.att = [], []
        self.bsim = Path(os.environ["BSIM_OUT_PATH"])

    def dev(self, exe, args, tag):
        d = len(self.devs)
        self.devs.append(([str(exe), f"-s={self.sid}", f"-d={d}"] + args, tag))
        return d

    def wlan(self, busy, k):
        return self.dev(self.bsim / "bin/bs_device_2G4_WLAN_actmod",
                        [f"-channel={WIFI_CH[k]}", f"-rs={11 + k}"] + WLAN[busy], f"wlan{WIFI_CH[k]}")

    def run(self):
        logs = self.out / self.sid
        logs.mkdir(parents=True, exist_ok=True)
        attf = logs / "att.txt"
        attf.write_text("".join(f"{a} {b} : {v}\n" for a, b, v in self.att))
        wall = int(120 + 40 * self.secs)  # hard cap per process; a hang is a harness bug
        phy = [str(self.bsim / "bin/bs_2G4_phy_v1"), f"-s={self.sid}", f"-D={len(self.devs)}",
               f"-sim_length={int(self.secs * 1e6)}", "-defmodem=BLE_simple", "-channel=multiatt",
               "-argschannel", f"-at={ATT_DEFAULT}", f"-file={attf}"]
        procs = []
        t = time.time()
        try:
            for cmd, tag in [(phy, "phy")] + self.devs:
                f = open(logs / f"{tag}.log", "w")
                procs.append((subprocess.Popen(["timeout", str(wall)] + cmd, cwd=self.bsim / "bin", stdout=f,
                                               stderr=subprocess.STDOUT, start_new_session=True), tag, f))
            rcs = {tag: p.wait() for p, tag, _ in procs}
        finally:
            for p, _, f in procs:
                if p.poll() is None:
                    os.killpg(p.pid, signal.SIGKILL)
                f.close()
        bad = {k: v for k, v in rcs.items() if v}
        print(f"  sim {self.name}: {self.secs:g} s simulated, {len(self.devs)} devices, "
              f"{time.time() - t:.0f} s wall{', exit codes ' + str(bad) if bad else ''}", flush=True)
        self.logs, self.dumps = logs, self.bsim / "results" / self.sid
        return not bad

    def log(self, tag):
        return (self.logs / f"{tag}.log").read_text(errors="replace")

    def cleanup(self, keep):
        if not keep:
            shutil.rmtree(self.dumps, ignore_errors=True)


def tx_frames(path, fa, fb):
    """Pack Tx dump -> list of frames [startA, endA, startB, endB] (us, phy time)."""
    frames = []
    for r in csv.DictReader(open(path)):
        f = round(2400 + float(r["center_freq"]))
        s, e = int(float(r["start_time"])), int(float(r["end_time"]))
        if f == fa:
            frames.append([s, e, None, None])
        elif f == fb and frames and frames[-1][2] is None:
            frames[-1][2:] = [s, e]
    return [x for x in frames if x[2] is not None]


def rx_ok(path, addr):
    """Receiver Rx dump -> ({freq: set(sync end us)} of status-OK receptions of addr, [(freq, rx start)])."""
    ok, starts = {}, []
    want = f"0x{addr:08X}"
    for r in csv.DictReader(open(path)):
        f = round(2400 + float(r["center_freq"]))
        starts.append((f, int(float(r["start_time"]))))
        if r["status"] == "1" and r["phy_address"].upper() == want.upper():
            ok.setdefault(f, set()).add(int(float(r["rx_time_stamp"])))
    return ok, starts


def got(ok, f, s):
    hit = ok.get(f, ())
    return any(s + d in hit for d in range(20, 31))


def runs(lost):
    """Lengths of runs of consecutive lost frames."""
    out, n = [], 0
    for x in lost + [False]:
        if x:
            n += 1
        elif n:
            out.append(n)
            n = 0
    return out


def link(sim, pdev, rdev, pid, fa, fb, t_from):
    """Per-copy outcomes pack pdev -> receiver rdev from the dumps, frames starting after t_from (us)."""
    fr = [x for x in tx_frames(sim.dumps / f"d_2G4_{pdev:02d}.Tx.csv", fa, fb) if x[0] >= t_from]
    ok, _ = rx_ok(sim.dumps / f"d_2G4_{rdev:02d}.Rx.csv", aa(pid))
    a = [got(ok, fa, x[0]) for x in fr]
    b = [got(ok, fb, x[2]) for x in fr]
    n = len(fr) - 3  # frame n needs packet n+2 for TD; drop the tail
    if n <= 0:
        return {"frames": 0}, fr
    off = [not (a[i] or b[i]) for i in range(n)]
    on = [off[i] and not (a[i + 2] or b[i + 2]) for i in range(n)]
    st = {"frames": n, "loss_a": 1 - sum(a[:n]) / n, "loss_b": 1 - sum(b[:n]) / n}
    for k, v in (("off", off), ("on", on)):
        r = runs(v)
        st[f"loss_{k}"] = sum(v) / n
        st[f"run_{k}"] = max(r, default=0)
        st[f"events_{k}"] = sum(x >= 3 for x in r)
        st[f"events_h_{k}"] = st[f"events_{k}"] * 3.6e6 / n
    return st, fr


def fw_stats(text, t_lock):
    """Receiver log -> lock times (s) and RXAPP totals over whole seconds after the first lock."""
    locks = [int(t) / 1e6 for t in re.findall(r"RX lock epoch=\d+ t_us=(\d+)", text)]
    reacq = len(re.findall(r"RX reacquire", text))
    tot = {k: 0 for k in ("frames", "valid", "lost", "skips")}
    for m in re.findall(r"RXAPP (.*)", text):
        x = {k: int(v) for k, v in re.findall(r"(\w+)=(-?\d+)", m)}
        if locks and x["t_ms"] / 1e3 - 1 >= locks[0] + t_lock:
            for k in tot:
                tot[k] += x[k]
    return locks, reacq, tot


# ---------------------------------------------------------------- scenarios

class G2:
    def __init__(self, args, exes):
        self.a, self.exes, self.plan = args, exes, plan(args.plan)
        self.results, self.ok, self.gate = {}, True, True
        self.out = Path(args.out).resolve()

    def check(self, sc, name, cond, value, xfail=None):
        """xfail = issue that explains a known failure: XFAIL does not fail the run, XPASS says remove it."""
        cond = bool(cond)
        res = ("XPASS" if cond else "XFAIL") if xfail else ("PASS" if cond else "FAIL")
        self.results.setdefault(sc, {}).setdefault("checks", []).append(
            {"check": name, "result": res, "value": value, "xfail": xfail})
        self.ok &= cond or bool(xfail)
        self.gate &= cond
        print(f"  [{res}{' ' + xfail if xfail else ''}] {sc}: {name}: {value}", flush=True)

    def report(self, sc, key, value):
        self.results.setdefault(sc, {})[key] = value

    def secs(self, ci, long):
        return long if self.a.long else ci

    def packs(self, sim, ids, td, near=None, offsets=True):
        """Add packs and their receivers (one receiver per pack, rack side). Returns [(pid, pdev, rdev, fa, fb)]."""
        pk, rx = ("pack_td", "rx_td") if td else ("pack", "rx")
        out = []
        for i, k in enumerate(ids):
            plan_id = isinstance(k, int)
            fa, fb = self.plan[k] if plan_id else k
            pid = k - 1 if plan_id else i  # AIR-2 pack id 0-7 = plan id - 1
            lab = str(k) if plan_id else f"{fa}_{fb}"
            ch = [f"-op_pack_id={pid}", f"-op_ch_a={fa}", f"-op_ch_b={fb}"]
            drift = (-20 + 40 * i / max(1, len(ids) - 1)) * 1e-6 if len(ids) > 1 else 20e-6
            off = [f"-start_offset={(i * 7919 + 1301) % 9973}"] if offsets else []  # packs boot unsynchronised
            pdev = sim.dev(self.exes[pk], ch + [f"-xo_drift={drift:.2e}"] + off, f"pack{lab}")
            rdev = sim.dev(self.exes[rx], ch + [f"-xo_drift={-drift / 2 - 10e-6:.2e}"], f"rx{lab}")
            out.append((lab, pid, pdev, rdev, fa, fb))
        for lab, _, pdev, _, _, _ in out:
            for _, _, _, rdev, _, _ in out:
                sim.att.append((pdev, rdev, ATT_NEAR if str(near) == lab else ATT_PACK))
        return out

    def wifi(self, sim, busy, links):
        for j in range(len(WIFI_CH)):
            w = sim.wlan(busy, j)
            for *_, rdev, _, _ in links:
                sim.att.append((w, rdev, ATT_WLAN))

    def measure(self, sim, links, warm=0.3):
        """Per pack: dump statistics + firmware RXAPP cross-check."""
        per = {}
        for k, pid, pdev, rdev, fa, fb in links:
            locks, reacq, tot = fw_stats(sim.log(f"rx{k}"), 0)
            t_from = (locks[0] + warm) * 1e6 if locks else 1e18
            st, _ = link(sim, pdev, rdev, pid, fa, fb, t_from) if locks else ({"frames": 0}, [])
            st.update(lock_s=locks[0] if locks else None, reacquire=reacq, fw_frames=tot["frames"],
                      fw_lost=tot["lost"], fw_skips=tot["skips"],
                      fw_loss=tot["lost"] / tot["frames"] if tot["frames"] else None, fA=fa, fB=fb)
            per[k] = st
        return per

    @staticmethod
    def line(k, s):
        if not s.get("frames"):
            return f"    pack {k}: NO LOCK"
        return (f"    pack {k} {s['fA']}/{s['fB']}: {s['frames']} frames, copy loss A {s['loss_a']:.2%} B {s['loss_b']:.2%}"
                f" | TD off {s['loss_off']:.3%} run {s['run_off']} ev/h {s['events_h_off']:.0f}"
                f" | TD on {s['loss_on']:.3%} run {s['run_on']} ev/h {s['events_h_on']:.0f}"
                f" | fw lost {s['fw_lost']}/{s['fw_frames']} skips {s['fw_skips']} reacq {s['reacquire']}")

    # (a) 1 pack, clean channel: SYS-2 sim latency, RX-2 lock, zero loss; TD-length latency reported.
    def sc_a(self):
        secs = self.secs(5, 30)
        for td in (False, True):
            sim = Sim("a_td" if td else "a", secs if not td else 2, self.out)
            links = self.packs(sim, [(kconfig_default("OP_CH_A_MHZ"), kconfig_default("OP_CH_B_MHZ"))], td,
                               offsets=False)
            assert sim.run(), "sim a failed"
            k, pid, pdev, rdev, fa, fb = links[0]
            per = self.measure(sim, links)[k]
            fr = [x for x in tx_frames(sim.dumps / f"d_2G4_{pdev:02d}.Tx.csv", fa, fb)
                  if per["lock_s"] is not None and x[0] >= (per["lock_s"] + 0.1) * 1e6]
            dl = re.search(r"deadline_us=(\d+)", sim.log(f"rx{k}"))
            _, starts = rx_ok(sim.dumps / f"d_2G4_{rdev:02d}.Rx.csv", aa(pid))
            wa = sorted(s for f, s in starts if f == fa)
            lat, slack = [], []
            for x in fr:
                i = bisect.bisect_right(wa, x[0]) - 1  # window A opened just before copy A
                if i < 0 or x[0] - wa[i] > 150:
                    continue
                deadline = wa[i] - RAMP_RX + int(dl[1])
                t0 = x[0] - RAMP_TX
                lat.append(ENC_IPC_US + (x[3] + OUT_SLOT_US - t0))
                slack.append(x[3] + OUT_SLOT_US - deadline)
            tag = "a_td" if td else "a"
            L = max(lat) if lat else 1e9
            self.report(tag, "link", per)
            self.report(tag, "latency_sim_us", {"max": L, "mean": sum(lat) / max(1, len(lat)), "frames": len(lat),
                                                "merge_deadline_slack_us_min": min(slack, default=None)})
            sys2 = L + I2S_FILTERS_US + (TD_US if td else 0)
            self.report(tag, "sys2_projection_us", sys2)
            print(self.line("a", per))
            if not td:
                self.check("a", "SYS-2 sim latency (enc+IPC 100 + t0 -> copy B end + 200 output slot), excl. I2S/filters <= 1600 us",
                           L <= SYS2_SIM_MAX, f"{L:.0f} us max over {len(lat)} frames")
                self.check("a", "receiver merge deadline inside the output slot (copy B end + 200 us)",
                           slack and min(slack) >= 0, f"min slack {min(slack, default=-1)} us")
                self.check("a", "RX-2 lock <= 2 s", per["lock_s"] is not None and per["lock_s"] <= LOCK_MAX,
                           f"{per['lock_s']} s")
                self.check("a", "clean channel: 0 lost frames (fw), 0 seq skips, both copies every frame",
                           per["fw_lost"] == 0 and per["fw_skips"] == 0 and per["fw_frames"] > 0 and
                           per["loss_a"] == 0 and per["loss_b"] == 0,
                           f"fw lost {per['fw_lost']}/{per['fw_frames']}, copy loss {per['loss_a']:.3%}/{per['loss_b']:.3%}")
                print(f"    SYS-2 projection (+ accumulation, DAC DMA, ADC/DAC filters): {sys2 / 1e3:.2f} ms "
                      f"(target 3.0, hard 5.0)")
            else:
                print(f"    TD length: sim latency {L:.0f} us + TD 2000 -> SYS-2 projection {sys2 / 1e3:.2f} ms "
                      f"(target 3.0, hard 5.0)")
            sim.cleanup(self.a.keep)

    def loss_runs(self, sc, ids, busies, secs, near=None, assert_at=None):
        for busy in busies:
            for td in (False, True) if busy else (False,):
                tag = f"{sc}_{busy}{'_td' if td else ''}"
                sim = Sim(tag, secs, self.out)
                links = self.packs(sim, ids, td, near=near)
                if busy:
                    self.wifi(sim, busy, links)
                assert sim.run(), f"sim {tag} failed"
                per = self.measure(sim, links)
                self.report(sc, f"busy{busy}_{'td_len' if td else 'v1_len'}", per)
                print(f"  {tag}: {'TD-length 81 B' if td else 'v1 42 B'} packets, Wi-Fi {busy} % busy")
                for k, s in per.items():
                    print(self.line(k, s))
                key = "on" if td else "off"
                hit = crowded(links, near)
                if assert_at is not None and busy == assert_at and td:
                    for k, s in per.items():
                        self.check(sc, f"SYS-3 pack {k} at {busy} % Wi-Fi, TD on: loss <= 0.1 %, <= 2 consecutive",
                                   s.get("frames") and s[f"loss_{key}"] <= SYS3_LOSS and s[f"run_{key}"] <= SYS3_RUN,
                                   f"loss {s.get('loss_on', 1):.3%}, max run {s.get('run_on')}, "
                                   f"events/h {s.get('events_h_on', 0):.0f} (reported, ADR-0010)",
                                   xfail=XF_PLAN if k in hit else None)
                if busy == 0:
                    for k, s in per.items():
                        self.check(sc, f"no cross-pack collisions, pack {k} (no Wi-Fi, near pack {near})",
                                   s.get("frames") and s["loss_a"] == 0 and s["loss_b"] == 0 and s["fw_lost"] == 0,
                                   f"copy loss {s.get('loss_a', 1):.3%}/{s.get('loss_b', 1):.3%}, fw lost {s.get('fw_lost')}",
                                   xfail=XF_PLAN if k in hit else None)
                if not td:
                    for k, s in per.items():  # firmware merge agrees with the dump-derived TD-off loss
                        if s.get("frames") and s["fw_frames"]:
                            d = abs(s["fw_loss"] - s["loss_off"])
                            self.check(sc, f"{tag} pack {k}: fw loss matches dumps (within 0.2 % abs or 5 % rel)",
                                       d <= max(0.002, 0.05 * s["loss_off"]), f"fw {s['fw_loss']:.3%} vs dumps {s['loss_off']:.3%}")
                sim.cleanup(self.a.keep)

    # (b) 1 pack, Wi-Fi 1/6/11 at 10/25/40 %.
    def sc_b(self):
        secs = self.secs(10, 120)
        self.loss_runs("b", [8], (10, 25, 40), secs, assert_at=40)
        self.loss_runs("b_inband", [tuple(int(x) for x in self.a.inband.split(","))], (10, 40) if not self.a.long else (10, 25, 40), secs)

    # (c) 8 packs + 8 receivers, Wi-Fi 1/6/11, one pack near the rack at -20 dBm.
    def sc_c(self):
        near = self.a.near
        self.loss_runs("c", list(range(1, 9)), (0,), self.secs(3, 10), near=near)
        self.loss_runs("c", list(range(1, 9)), self.secs((40,), (10, 25, 40)), self.secs(5, 60), near=near, assert_at=40)

    # (d) +-40 ppm radio tracking here; RX-7 clock recovery via tests/bsim/rx/run.sh d / dn (#24).
    def sc_d(self):
        secs = self.secs(20, 600)
        sim = Sim("d", secs, self.out)
        sim.dev(self.exes["pack"], ["-xo_drift=40e-6"], "pack0")
        sim.dev(self.exes["rx"], ["-xo_drift=-40e-6"], "rx0")
        sim.att.append((0, 1, ATT_PACK))
        assert sim.run(), "sim d failed"
        locks, reacq, tot = fw_stats(sim.log("rx0"), 0)
        per_s = tot["frames"] / max(1, (secs - 2 - (locks[0] if locks else 0)))
        self.report("d", "tracking", {"secs": secs, "lock_s": locks[0] if locks else None, **tot, "reacquire": reacq})
        self.check("d", "pack +40 ppm / receiver -40 ppm: 0 lost, 0 seq skips, 0 re-acquire",
                   locks and tot["frames"] > 0 and tot["lost"] == 0 and tot["skips"] == 0 and reacq == 0,
                   f"{tot['frames']} frames over {secs} s, lost {tot['lost']}, skips {tot['skips']}, reacquire {reacq}")
        sim.cleanup(self.a.keep)
        ds = self.a.d_secs or self.secs(300, 3600)
        t = time.time()
        procs = {v: subprocess.Popen(["timeout", str(int(120 + ds)), str(REPO / "tests/bsim/rx/run.sh"),
                                      str(self.exes["pack"]), str(self.exes["rx"]), v, str(ds)],
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                 for v in ("d", "dn")}
        for v, p in procs.items():
            out = p.communicate()[0]
            m = re.search(r"RX_CLOCK_CHECK.*", out)
            line = m[0] if m else out.strip().splitlines()[-1:] or ["no output"]
            self.report("d", f"RX-7_{v}", line)
            self.check("d", f"RX-7 {v} ({'pack +20/rx -20' if v == 'd' else 'pack -20/rx +20'} ppm, {ds} s): "
                       "0 slot slips, rate error <= 1 sample/h", p.returncode == 0 and m and "PASS" in m[0],
                       line if isinstance(line, str) else line[0])
        print(f"  RX-7 runs: {ds} s simulated each, {time.time() - t:.0f} s wall", flush=True)

    # (e) pack reboot mid-show, as tests/bsim/rx/run.sh e.
    def sc_e(self):
        secs = 10
        sim = Sim("e", secs, self.out)
        P = "-xo_drift=20e-6"
        sim.dev(self.exes["pack3s"], [P], "pack0")
        sim.dev(self.exes["rx"], ["-xo_drift=-20e-6"], "rx0")
        sim.dev(self.exes["pack3s"], [P, "-start_offset=3050300"], "pack1")
        sim.dev(self.exes["pack"], [P, "-start_offset=7000700"], "pack2")
        sim.att += [(0, 1, ATT_PACK), (2, 1, ATT_PACK), (3, 1, ATT_PACK)]
        assert sim.run(), "sim e failed"
        r = subprocess.run([sys.executable, str(REPO / "tests/bsim/rx/check.py"), str(sim.logs / "rx0.log"),
                            "0,3.0503,7.0007", f"3,6.0503,{secs}"], capture_output=True, text=True)
        print("    " + r.stdout.strip().replace("\n", "\n    "))
        lk = dict(re.findall(r"(pack\d)_lock_s=([\d.]+)", r.stdout))
        self.report("e", "relock_s", lk)
        self.check("e", "RX-2/RX-10: re-lock <= 2 s after each pack boot, 0 loss while locked",
                   r.returncode == 0, " ".join(f"{k} {v} s" for k, v in lk.items()))
        sim.cleanup(self.a.keep)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--long", action="store_true", help="local mode: minutes of sim time per run")
    ap.add_argument("--only", default="abcde")
    ap.add_argument("--build", default="g2-build", help="build directory (one sub-dir per image)")
    ap.add_argument("--no-build", action="store_true", help="reuse the images in --build")
    ap.add_argument("--out", default="g2-out", help="logs, g2.json, g2.md")
    ap.add_argument("--jobs", type=int, default=max(1, min(4, (os.cpu_count() or 2) // 2)))
    ap.add_argument("--near", type=int, default=1, help="(c) pack id at -20 dBm at the rack")
    ap.add_argument("--eirp", type=float, default=20.0,
                    help="pack EIRP dBm (AIR-6: US max ~+20; UK/EU EN 300 328 +10); 10 m path loss 60.2 dB")
    ap.add_argument("--wifi", default="1,6,11", help="Wi-Fi interferer channels (one actmod each), e.g. 1,5,9,13")
    ap.add_argument("--inband", default="2437,2462", help="(b) carrier pair with both copies under Wi-Fi")
    ap.add_argument("--d-secs", type=int, default=0, help="(d) RX-7 sim seconds (default 300, --long 3600)")
    ap.add_argument("--keep", action="store_true", help="keep the phy dumps")
    ap.add_argument("--plan", default=str(REPO / "host/channel_plan.yaml"), help="channel plan for (b) and (c)")
    a = ap.parse_args()
    global ATT_PACK
    ATT_PACK = PL_10M - a.eirp
    WIFI_CH[:] = [int(x) for x in a.wifi.split(",")]
    need = set()
    for sc in a.only:
        need |= {"a": {"pack", "rx", "pack_td", "rx_td"}, "b": {"pack", "rx", "pack_td", "rx_td"},
                 "c": {"pack", "rx", "pack_td", "rx_td"}, "d": {"pack", "rx"}, "e": {"pack", "rx", "pack3s"}}[sc]
    t = time.time()
    exes = build(sorted(need), Path(a.build).resolve(), a.jobs, a.no_build)
    g = G2(a, exes)
    g.out.mkdir(parents=True, exist_ok=True)
    for sc in a.only:
        print(f"== scenario ({sc})", flush=True)
        getattr(g, f"sc_{sc}")()
    (g.out / "g2.json").write_text(json.dumps(g.results, indent=1, default=str))
    rows = [f"| {sc} | {c['check']} | {c['result'] if c['result'] != 'FAIL' else '**FAIL**'}"
            f"{' ' + c['xfail'] if c['xfail'] else ''} | {c['value']} |"
            for sc, r in g.results.items() for c in r.get("checks", [])]
    (g.out / "g2.md").write_text("### G2 bsim scenarios\n\n| sc | check | result | value |\n|---|---|---|---|\n" +
                                 "\n".join(rows) + f"\n\nPack EIRP {a.eirp:g} dBm, Wi-Fi channels {a.wifi}. G2 gate met: {g.gate}\n")
    g.results["gate_met"] = g.gate
    (g.out / "g2.json").write_text(json.dumps(g.results, indent=1, default=str))
    print(f"G2 gate {'MET' if g.gate else 'NOT MET (see XFAIL)'}; run {'PASS' if g.ok else 'FAIL'} "
          f"({time.time() - t:.0f} s, {'long' if a.long else 'ci'} mode)")
    sys.exit(0 if g.ok else 1)


if __name__ == "__main__":
    main()

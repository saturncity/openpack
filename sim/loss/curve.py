"""ViSQOL vs busy fraction through codec + loss + PLC. Run: python3 sim/loss/curve.py
Writes degraded WAVs to sim/loss/out/ (gitignored); scores them with sim/quality.visqol(ref, deg, fs) if that exists,
else prints how to re-run. Clips: macOS `say` speech (ponytail: synthetic TTS, swap in real speech when available)."""
import os, subprocess, sys, wave
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "codec"), os.path.join(HERE, "..")]
import codec, plc, traces

OUT = os.path.join(HERE, "out")
FS, N = 48000, 48
TEXTS = ["The quick brown fox jumps over the lazy dog, and the crowd roars with laughter.",
         "Please welcome to the stage the cast of tonight's performance, ladies and gentlemen."]
CASES = [("adpcm6", True), ("adpcm6", False), ("adpcm8", False), ("bf8_3", False)]


def clips():
    os.makedirs(OUT, exist_ok=True)
    for i, t in enumerate(TEXTS):
        p = os.path.join(OUT, f"ref{i}.wav")
        if not os.path.exists(p):
            subprocess.run(["say", "-o", p, f"--data-format=LEI16@{FS}", "--channels=1", t], check=True)
    return [os.path.join(OUT, f"ref{i}.wav") for i in range(len(TEXTS))]


def read(p):
    with wave.open(p) as w:
        assert w.getframerate() == FS and w.getsampwidth() == 2 and w.getnchannels() == 1
        x = np.frombuffer(w.readframes(w.getnframes()), "<i2")
    return x[: len(x) // N * N].reshape(-1, N)


def write(p, fr):
    with wave.open(p, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(FS)
        w.writeframes(fr.astype("<i2").tobytes())


def degrade(fr, name, td, busy):
    enc, dec = codec.CODECS[name]
    la, lb = traces.trace(busy, frames=len(fr))
    lost = traces.frame_lost(la, lb, td)
    return plc.apply_plc(np.array([dec(enc(f)) for f in fr]), lost)


def main():
    try:
        import quality
    except ImportError:
        quality = None
    rows = ["| busy % | " + " | ".join(f"{c}{' +TD' if t else ''}" for c, t in CASES) + " |", "|---" * (len(CASES) + 1) + "|"]
    for busy in traces.BUSY:
        cells = []
        for name, td in CASES:
            sc = []
            for p in clips():
                ref = read(p)
                deg = degrade(ref, name, td, busy)
                dp = os.path.join(OUT, f"{os.path.basename(p)[:-4]}_{name}_{'td' if td else 'notd'}_{round(busy * 100)}.wav")
                write(dp, deg)
                if quality:
                    sc.append(quality.visqol(p, dp, FS))
            cells.append(f"{np.mean(sc):.2f}" if sc else "n/a")
        rows.append(f"| {busy:.0%} | " + " | ".join(cells) + " |")
    print("\n".join(rows))
    if not quality:
        print(f"\nsim/quality.py not found: degraded WAVs are in {OUT}; re-run this script once it exists.", file=sys.stderr)


if __name__ == "__main__":
    main()
